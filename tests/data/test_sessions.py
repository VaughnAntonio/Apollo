from datetime import datetime

import polars as pl

from apollo.data.sessions import add_session_columns


def _one(ts_utc: datetime) -> pl.DataFrame:
    df = pl.DataFrame({"ts": [ts_utc]}).with_columns(pl.col("ts").dt.replace_time_zone("UTC"))
    return add_session_columns(df)


def test_evening_belongs_to_next_globex_day():
    r = _one(datetime(2026, 11, 4, 23, 30))  # 18:30 ET (EST), Wednesday
    assert str(r["globex_date"][0]) == "2026-11-05" and r["is_rth"][0] is False
    assert r["ny_date"][0] is None


def test_rth_bounds_edt_and_est():
    r = _one(datetime(2026, 10, 30, 13, 30))  # 09:30 EDT
    assert r["is_rth"][0] is True and str(r["ny_date"][0]) == "2026-10-30"
    assert _one(datetime(2026, 11, 2, 14, 29))["is_rth"][0] is False  # 09:29 EST
    assert _one(datetime(2026, 11, 2, 21, 0))["is_rth"][0] is False  # 16:00 EST


def test_dst_change_day():
    r = _one(datetime(2026, 11, 1, 23, 0))  # Sunday 18:00 EST, first bar after fall-back
    assert str(r["globex_date"][0]) == "2026-11-02"


def test_weekend_is_not_rth():
    assert _one(datetime(2026, 11, 7, 15, 0))["is_rth"][0] is False  # Saturday 10:00 EST
