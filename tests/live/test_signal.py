from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import polars as pl

from apollo.live.signal import current_signal

NY = ZoneInfo("America/New_York")
TS = pl.Datetime("us", "UTC")
NOW = datetime(2026, 11, 4, 9, 52, tzinfo=NY)  # Wednesday morning


def setups(rows):
    cols = {
        "direction": pl.Utf8,
        "c2_ts": TS,
        "c2_close": TS,
        "c3_closed": pl.Boolean,
        "after_c2_cisd_ts": TS,
        "after_c2_cisd_confirmed_at": TS,
        "after_c2_cisd_level": pl.Float64,
        "after_c2_protected": pl.Float64,
        "c1_high": pl.Float64,
        "c1_low": pl.Float64,
        "window_end": TS,
        "ltf_missing": pl.Boolean,
    }
    return pl.DataFrame(rows, schema=cols)


def daily_bull():
    c2 = datetime(2026, 11, 2, 18, tzinfo=NY)  # the Globex day ending Tue 17:00
    cisd = datetime(2026, 11, 3, 16, tzinfo=NY)
    return {
        "direction": "bull",
        "c2_ts": c2,
        "c2_close": c2 + timedelta(hours=23),
        "c3_closed": None,
        "after_c2_cisd_ts": cisd,
        "after_c2_cisd_confirmed_at": cisd + timedelta(hours=1),
        "after_c2_cisd_level": 101.0,
        "after_c2_protected": 100.0,
        "c1_high": 120.0,
        "c1_low": 90.0,
        "window_end": datetime(2026, 11, 4, 17, tzinfo=NY),
        "ltf_missing": False,
    }


def four_hour_bull(cisd=True):
    c2 = datetime(2026, 11, 4, 2, tzinfo=NY)
    t = datetime(2026, 11, 4, 5, 15, tzinfo=NY)
    return {
        "direction": "bull",
        "c2_ts": c2,
        "c2_close": c2 + timedelta(hours=4),
        "c3_closed": None,
        "after_c2_cisd_ts": t if cisd else None,
        "after_c2_cisd_confirmed_at": t + timedelta(minutes=15) if cisd else None,
        "after_c2_cisd_level": 101.0,
        "after_c2_protected": 100.0,
        "c1_high": 120.0,
        "c1_low": 90.0,
        "window_end": c2 + timedelta(hours=8),
        "ltf_missing": False,
    }


def one_hour_bull():
    c2 = datetime(2026, 11, 4, 8, tzinfo=NY)
    t = datetime(2026, 11, 4, 9, 45, tzinfo=NY)
    return {
        "direction": "bull",
        "c2_ts": c2,
        "c2_close": c2 + timedelta(hours=1),
        "c3_closed": None,
        "after_c2_cisd_ts": t,
        "after_c2_cisd_confirmed_at": t + timedelta(minutes=5),
        "after_c2_cisd_level": 101.0,
        "after_c2_protected": 100.0,
        "c1_high": 110.0,
        "c1_low": 90.0,
        "window_end": c2 + timedelta(hours=2),
        "ltf_missing": False,
    }


def frames(ohlc, daily=(), four=(), one=()):
    bars = ohlc(
        [(101, 101.5, 100.5, 101.2)] * 4 + [(102, 102.5, 101.8, 102.2)] * 3,
        "2026-11-04 09:30",
        "5m",
    )
    return {
        "D-1H": setups(list(daily)),
        "4H-15m": setups(list(four)),
        "1H-5m": setups(list(one)),
        "bars_5m": bars,
        "forecasts": pl.DataFrame(),
    }


def steps(sig):
    return {row["step"]: row["status"] for row in sig["checklist"]}


def test_no_setup_is_flat(ohlc):
    s = current_signal(None, "MNQ", NOW, frames=frames(ohlc))
    assert s["status"] == "flat" and steps(s)["daily_bias"] == "fail" and s["research_only"] is True


def test_bias_then_waiting(ohlc):
    s = current_signal(None, "MNQ", NOW, frames=frames(ohlc, daily=[daily_bull()]))
    assert s["status"] == "waiting" and s["direction"] == "bull"
    assert steps(s) == {
        "daily_bias": "pass",
        "4h": "wait",
        "1h": "pass",
        "15m": "wait",
        "5m_trigger": "wait",
    }


def test_full_trigger_levels(ohlc):
    f = frames(ohlc, daily=[daily_bull()], four=[four_hour_bull()], one=[one_hour_bull()])
    s = current_signal(None, "MNQ", NOW, frames=f)
    assert s["status"] == "trigger" and set(steps(s).values()) == {"pass"}
    assert (s["entry"], s["stop"], s["target"]) == (102.0, 99.75, 110.0)
    assert s["contracts"] == 111 and round(s["risk_of_limit"], 4) == round(111 * 2.25 * 2 / 2500, 4)


def test_symbol_without_model(ohlc):
    s = current_signal(None, "NVDA", NOW, frames=frames(ohlc))
    assert s["status"] == "no_model" and s["research_only"] is True
