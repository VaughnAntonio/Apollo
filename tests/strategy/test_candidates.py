from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from apollo.config import load_symbols
from apollo.strategy.candidates import build_candidates
from apollo.strategy.config import load_trade_config

NY = ZoneInfo("America/New_York")
MNQ = load_symbols()["MNQ"]
CFG = load_trade_config()
V = CFG.variants
TS = pl.Datetime("us", "UTC")


def setup(signal_hour=10, signal_minute=0, protected=100.0, c1_high=110.0, direction="bull"):
    sig = datetime(2026, 11, 3, signal_hour, signal_minute, tzinfo=NY)
    return pl.DataFrame(
        {
            "c2_ts": [datetime(2026, 11, 2, 18, tzinfo=NY)],
            "direction": [direction],
            "c1_high": [c1_high],
            "c1_low": [90.0],
            "after_c2_cisd_ts": [sig],
            "after_c2_protected": [protected],
        },
        schema_overrides={"c2_ts": TS, "after_c2_cisd_ts": TS},
    )


def hourly(ohlc):
    # 09:00 .. 16:00 ET; the 11:00 bar opens at 102
    rows = [(101, 101.5, 100.5, 101), (101, 102, 100.2, 101.8), (102, 103, 101.5, 102.5)]
    rows += [(102.5, 103, 102, 102.8)] * 5
    return ohlc(rows, "2026-11-03 09:00", "1h")


def forecasts(up=6.0, down=6.0, fomc=0.0, p=(0.5, 0.1, 0.2, 0.2)):
    return pl.DataFrame(
        {
            "date": [date(2026, 11, 3)],
            "open": [100.0],
            "p_trend_up": [p[0]],
            "p_trend_down": [p[1]],
            "p_chop": [p[2]],
            "p_normal": [p[3]],
            "up_bound": [up],
            "down_bound": [down],
            "ev_fomc": [fomc],
            "ev_any": [fomc],
        }
    )


NONE = forecasts().clear()


def one(ohlc, s, f, variant, layer: Literal["D-1H", "1H-5m"] = "D-1H"):
    return build_candidates(s, hourly(ohlc), f, MNQ, CFG, V[variant], layer).row(0, named=True)


def test_bull_trade_levels(ohlc):
    c = one(ohlc, setup(), NONE, "plain")
    assert (c["stop"], c["target"], c["rr"]) == (99.75, 110.0, pytest.approx(8 / 2.25))
    assert c["skip"] is None and c["entry"] == 102.0
    assert str(c["entry_ts"]) == "2026-11-03 16:00:00+00:00" and c["session"] == date(2026, 11, 3)


def test_last_bar_of_session_is_outside_window(ohlc):
    assert one(ohlc, setup(signal_hour=15), NONE, "plain")["skip"] == "outside_window"


def test_range_cap_and_room(ohlc):
    capped = one(ohlc, setup(c1_high=106.8), forecasts(), "range")  # edge 106, 0.8 past it
    assert capped["skip"] is None and capped["target"] == 106.0 and capped["target_capped"]
    assert one(ohlc, setup(), forecasts(), "range")["skip"] == "range_room"  # 4 past > 1.2


def test_no_forecast_only_blocks_filtered_variants(ohlc):
    assert one(ohlc, setup(), NONE, "plain")["skip"] is None
    assert one(ohlc, setup(), NONE, "both")["skip"] == "no_forecast"


def test_regime_blocks_bull_on_chop(ohlc):
    f = forecasts(up=20, down=20, p=(0.2, 0.1, 0.6, 0.1))
    assert one(ohlc, setup(), f, "regime")["skip"] == "regime"


def test_rr_and_stop_bounds(ohlc):
    assert one(ohlc, setup(c1_high=105.15), NONE, "plain")["skip"] == "rr"  # 3.15 / 2.25 = 1.4
    tight = setup(protected=101.5)  # stop 101.25: 0.75 = 3 ticks from 102
    assert one(ohlc, tight, NONE, "plain+risk")["skip"] == "stop_too_tight"
    assert one(ohlc, tight, NONE, "plain")["skip"] is None


def test_fomc_cutoff(ohlc):
    f = forecasts(up=20, down=20, fomc=1.0)
    assert one(ohlc, setup(signal_hour=12, signal_minute=30), f, "both+risk+fomc")["skip"] is None
    late = setup(signal_hour=13)  # entry bar 14:00 ET, after 13:30
    assert one(ohlc, late, f, "both+risk+fomc")["skip"] == "fomc_cutoff"
    assert one(ohlc, late, f, "both+risk")["skip"] is None


def test_event_half_size(ohlc):
    f = forecasts(up=20, down=20, fomc=1.0)
    assert one(ohlc, setup(), f, "both+risk+event")["half_size"] is True
    assert one(ohlc, setup(), f, "both+risk")["half_size"] is False


def deferred_setup(signal: datetime, window_end: datetime):
    s = setup().with_columns(
        after_c2_cisd_ts=pl.lit(signal).cast(TS), window_end=pl.lit(window_end).cast(TS)
    )
    return s


def two_sessions(ohlc, overnight_low=101.0, overnight_high=103.0):
    """16:00 ET on Nov 3, the Globex evening and night, then Nov 4 09:00-15:00 (opens at 102)."""
    evening = ohlc([(102, 102.5, 101.5, 102)] * 1, "2026-11-03 16:00", "1h")
    night = ohlc(
        [(102, overnight_high, overnight_low, 102)] * 15, "2026-11-03 18:00", "1h"
    )  # 18:00-08:00
    day = ohlc([(102, 103, 101.5, 102.5)] * 7, "2026-11-04 09:00", "1h")
    return pl.concat([evening, night, day])


def test_overnight_cisd_enters_at_next_session_open(ohlc):
    sig = datetime(2026, 11, 3, 16, tzinfo=NY)  # confirms as C2 closes at 17:00
    s = deferred_setup(sig, datetime(2026, 11, 4, 17, tzinfo=NY))
    c = build_candidates(s, two_sessions(ohlc), NONE, MNQ, CFG, V["plain"], "D-1H").row(
        0, named=True
    )
    assert c["skip"] is None and str(c["entry_ts"]) == "2026-11-04 14:00:00+00:00"  # 09:00 ET
    assert c["session"] == date(2026, 11, 4) and c["entry"] == 102.0


def test_overnight_touch_of_stop_invalidates(ohlc):
    sig = datetime(2026, 11, 3, 16, tzinfo=NY)
    s = deferred_setup(sig, datetime(2026, 11, 4, 17, tzinfo=NY))
    bars = two_sessions(ohlc, overnight_low=99.5)  # trades through the 99.75 stop overnight
    assert build_candidates(s, bars, NONE, MNQ, CFG, V["plain"], "D-1H")["skip"][0] == "invalidated"


def test_no_deferral_past_the_setup_window(ohlc):
    sig = datetime(2026, 11, 3, 16, tzinfo=NY)
    s = deferred_setup(sig, datetime(2026, 11, 3, 17, tzinfo=NY))  # C3 already over at 17:00
    assert (
        build_candidates(s, two_sessions(ohlc), NONE, MNQ, CFG, V["plain"], "D-1H")["skip"][0]
        == "outside_window"
    )
