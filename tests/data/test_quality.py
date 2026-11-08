import json
from datetime import datetime
from zoneinfo import ZoneInfo

import polars as pl

from apollo.data.quality import check_quality


def test_weekend_and_daily_break_not_gaps(bars):
    fri = bars("2026-11-06 15:00", 2, "1h")  # Friday 15:00, 16:00 ET
    sun = bars("2026-11-08 18:00", 2, "1h")  # Sunday 18:00, 19:00 ET
    brk = bars("2026-11-03 15:00", 2, "1h").vstack(bars("2026-11-03 18:00", 1, "1h"))
    assert check_quality(fri.vstack(sun), "1h").gaps == []
    assert check_quality(brk, "1h").gaps == []


def test_real_hole_reported(bars):
    df = bars("2026-11-03 09:30", 3, "5m").vstack(bars("2026-11-03 10:30", 3, "5m"))
    assert len(check_quality(df, "5m").gaps) == 1


def test_stock_overnight_not_gap(bars):
    df = bars("2026-11-03 15:55", 1, "5m", symbol="NVDA").vstack(
        bars("2026-11-04 09:30", 1, "5m", symbol="NVDA")
    )
    assert check_quality(df, "5m", kind="stock").gaps == []


def test_bad_tick(bars):
    df = bars("2026-11-03 09:30", 40, "5m")
    spike = pl.when(pl.int_range(pl.len()) == 30).then(pl.col("close") * 1.5)
    df = df.with_columns(spike.otherwise(pl.col("close")).alias("close"))
    assert check_quality(df, "5m").bad_ticks[0] == df["ts"][30].isoformat()


def test_sparse_day_is_bad_and_report_serialises(bars):
    r = check_quality(bars("2026-11-03 09:30", 3, "5m"), "5m")
    assert r.bad_days == ["2026-11-03"] and r.rows == 3 and r.duplicates == 0
    assert json.loads(r.to_json())["bad_days"] == ["2026-11-03"]


def test_single_missing_bar_reported(bars):
    df = bars("2026-11-03 10:00", 1, "1m").vstack(bars("2026-11-03 10:02", 1, "1m"))
    assert len(check_quality(df, "1m").gaps) == 1


def test_reopen_jump_not_bad_tick(bars):
    fri = bars("2026-11-06 14:00", 20, "5m")  # ends 15:35 ET
    sun = bars("2026-11-08 18:00", 3, "5m").with_columns(
        pl.col("open", "high", "low", "close") + 300
    )
    assert check_quality(fri.vstack(sun), "5m").bad_ticks == []


def test_unfinished_day_not_bad(bars):
    # The collector can run while the Globex day is still trading; it is not "sparse" yet.
    now = datetime(2026, 11, 3, 16, 0, tzinfo=ZoneInfo("America/New_York"))
    assert check_quality(bars("2026-11-03 09:30", 3, "5m"), "5m", now=now).bad_days == []
