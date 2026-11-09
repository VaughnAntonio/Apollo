import csv
from datetime import date, datetime
from zoneinfo import ZoneInfo

from apollo.journal.stats import calendar, export_for_review, journal_stats
from apollo.journal.store import JournalStore

NY = ZoneInfo("America/New_York")


def e(day, hour, r, source="manual", tags=(), grade=None, pnl=None):
    return {
        "opened_at": datetime(2026, 11, day, hour, tzinfo=NY),
        "r": r,
        "pnl_$": pnl if pnl is not None else (None if r is None else r * 100),
        "source": source,
        "tags": list(tags),
        "grade": grade,
        "stage": "eval",
    }


ENTRIES = [
    e(2, 10, 1.5, "signal"),
    e(2, 11, -1.0, "signal"),
    e(3, 10, -1.0, "manual", tags=["Gamba"]),
    e(3, 11, -1.0, "manual", tags=["Gamba"]),
    e(3, 12, -0.5, "manual", tags=["Gamba"]),  # 3 trades and -2.5R on Nov 3
    e(4, 10, None, "signal"),  # still open: not counted
]


def test_by_source_and_skipped():
    s = journal_stats(ENTRIES, signal_days=[date(2026, 11, 2), date(2026, 11, 5)])
    assert s["by_source"]["signal"] == {"n": 2, "win_rate": 0.5, "mean_r": 0.25, "sum_r": 0.5}
    assert s["by_source"]["manual"]["n"] == 3 and s["skipped"] == [date(2026, 11, 5)]
    assert s["by_tag"]["Gamba"]["sum_r"] == -2.5


def test_daily_cap_breaks():
    breaks = journal_stats(ENTRIES, signal_days=[])["daily_cap_breaks"]
    assert breaks == [
        {
            "date": date(2026, 11, 3),
            "n": 3,
            "r": -2.5,
            "reasons": ["more than 2 trades", "below -2R"],
        }
    ]


def test_calendar_sums():
    cal = calendar(ENTRIES)
    assert cal == [
        {"date": date(2026, 11, 2), "n": 2, "r": 0.5, "pnl_$": 50.0},
        {"date": date(2026, 11, 3), "n": 3, "r": -2.5, "pnl_$": -250.0},
    ]


def test_export_columns(tmp_path):
    s = JournalStore(tmp_path / "j.duckdb")
    s.add(
        {
            "opened_at": datetime(2026, 11, 3, 10, tzinfo=NY),
            "symbol": "MNQ",
            "side": "long",
            "entry": 102.0,
            "stop": 99.75,
            "target": 110.0,
            "size": 1,
            "source": "manual",
            "tags": ["A", "B"],
        }
    )
    out = export_for_review(s, tmp_path / "export.csv")
    row = next(csv.DictReader(out.open()))
    assert row["date"] == "2026-11-03" and row["tags"] == "A;B" and row["source"] == "manual"
    assert {"r", "pnl_$", "initial_stop", "stage", "grade", "scaled"} <= set(row)
