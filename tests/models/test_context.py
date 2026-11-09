from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from apollo.models.context import CONTEXT_FEATURES, context_features

NY = ZoneInfo("America/New_York")
EMPTY_VOL = pl.DataFrame(
    schema={"date": pl.Date, "vix": pl.Float64, "vix3m": pl.Float64, "vxn": pl.Float64}
)
EMPTY_EVENTS = pl.DataFrame(schema={"date": pl.Date, "kind": pl.Utf8, "event": pl.Utf8})


def sessions(*days: date) -> pl.DataFrame:
    at = [datetime.combine(d, time(8), tzinfo=NY) for d in days]
    return pl.DataFrame({"date": list(days), "forecast_at": at})


def test_monday_uses_friday_close():
    vol = pl.DataFrame(
        {
            "date": [date(2026, 11, 5), date(2026, 11, 6), date(2026, 11, 9)],
            "vix": [20.0, 25.0, 99.0],  # Monday's own close (99) must not be used
            "vix3m": [22.0, 20.0, 1.0],
            "vxn": [24.0, 30.0, 1.0],
        }
    )
    f = context_features(sessions(date(2026, 11, 9)), vol, EMPTY_EVENTS)
    assert f.columns == ["date", *CONTEXT_FEATURES]
    row = f.row(0, named=True)
    assert row["vix"] == 25.0 and row["vix_term"] == pytest.approx(1.25)
    assert row["vxn_vix"] == pytest.approx(1.2) and row["vix_chg5"] is None  # fewer than 6 closes


def test_vix_change_over_five_closes():
    days = [date(2026, 10, d) for d in (26, 27, 28, 29, 30)] + [date(2026, 11, 2)]
    vol = pl.DataFrame(
        {"date": days, "vix": [10.0, 11, 12, 13, 14, 20.0], "vix3m": [1.0] * 6, "vxn": [1.0] * 6}
    )
    row = context_features(sessions(date(2026, 11, 3)), vol, EMPTY_EVENTS).row(0, named=True)
    assert row["vix_chg5"] == pytest.approx(__import__("math").log(20 / 10))


def test_event_flags_on_the_day_only():
    ev = pl.DataFrame(
        {
            "date": [date(2026, 11, 2), date(2026, 11, 10), date(2026, 11, 10)],  # covers Nov 2-10
            "kind": ["other", "cpi", "other"],
            "event": ["ISM Manufacturing PMI", "CPI", "GDP"],
        }
    )
    f = context_features(sessions(date(2026, 11, 9), date(2026, 11, 10)), EMPTY_VOL, ev)
    assert f["ev_cpi"].to_list() == [0.0, 1.0] and f["ev_other"].to_list() == [0.0, 1.0]
    assert f["ev_any"].to_list() == [0.0, 1.0] and f["ev_fomc"].to_list() == [0.0, 0.0]
    assert f["vix"].is_null().all()


def test_old_vix_is_unknown_not_reused():
    vol = pl.DataFrame({"date": [date(2026, 11, 6)], "vix": [25.0], "vix3m": [20.0], "vxn": [30.0]})
    f = context_features(sessions(date(2026, 11, 9), date(2026, 11, 20)), vol, EMPTY_EVENTS)
    assert f["vix"].to_list() == [25.0, None]  # Friday's close serves Monday, not two weeks later


def test_events_outside_the_cache_are_unknown():
    ev = pl.DataFrame(
        {
            "date": [date(2026, 11, 10), date(2026, 12, 9)],
            "kind": ["cpi", "fomc"],
            "event": ["CPI", "FOMC"],
        }
    )
    f = context_features(
        sessions(date(2026, 11, 2), date(2026, 11, 11), date(2027, 3, 1)), EMPTY_VOL, ev
    )
    assert f["ev_any"].to_list() == [None, 0.0, None]
