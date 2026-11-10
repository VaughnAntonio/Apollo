"""Journal statistics (spec 5.8) and the export the journal-review skill reads (spec 5.15).

The key split is signal / manual / skipped: did following Apollo's signals beat Vaughn's own
calls, and how often were signals left untaken? Only closed trades (with an R) count.

Run: python -m apollo.journal.stats --db data_store/journal.duckdb --out docs/reviews/journal-export.csv

DuckDB lets one process write the file at a time. The API opens it only for each request, so
the export works while the API runs, but it can fail if a request is in flight; run it again.
"""

import argparse
import csv
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from apollo.journal.store import JournalStore

NY = ZoneInfo("America/New_York")
DAILY_CAP_R, DAILY_MAX_TRADES = -2.0, 2  # the journal review's suggested rule


def _day(e: dict[str, Any]) -> date:
    return e["opened_at"].astimezone(NY).date()


def _summary(rs: list[float]) -> dict[str, Any]:
    if not rs:
        return {"n": 0, "win_rate": None, "mean_r": None, "sum_r": 0.0}
    return {
        "n": len(rs),
        "win_rate": sum(r > 0 for r in rs) / len(rs),
        "mean_r": round(sum(rs) / len(rs), 6),
        "sum_r": round(sum(rs), 6),
    }


def _group(entries: list[dict[str, Any]], key) -> dict[str, Any]:
    groups: dict[str, list[float]] = defaultdict(list)
    for e in entries:
        for k in key(e):
            groups[k].append(e["r"])
    return {k: _summary(v) for k, v in sorted(groups.items())}


def journal_stats(entries: list[dict[str, Any]], signal_days: list[date]) -> dict[str, Any]:
    closed = [e for e in entries if e.get("r") is not None]
    taken = {_day(e) for e in entries if e["source"] == "signal"}
    days = calendar(closed)
    breaks = []
    for d in days:
        reasons = []
        if d["n"] > DAILY_MAX_TRADES:
            reasons.append(f"more than {DAILY_MAX_TRADES} trades")
        if d["r"] < DAILY_CAP_R:
            reasons.append(f"below {DAILY_CAP_R:g}R")
        if reasons:
            breaks.append({"date": d["date"], "n": d["n"], "r": d["r"], "reasons": reasons})
    return {
        "by_source": _group(closed, lambda e: [e["source"]]),
        "skipped": sorted(d for d in signal_days if d not in taken),
        "by_tag": _group(closed, lambda e: e.get("tags") or ["(none)"]),
        "by_grade": _group(closed, lambda e: [e.get("grade") or "(ungraded)"]),
        "by_stage": _group(closed, lambda e: [e.get("stage") or "(none)"]),
        "worst_days": sorted(days, key=lambda d: d["r"])[:3],
        "daily_cap_breaks": breaks,
    }


def calendar(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Closed trades per day: count, total R and total P&L."""
    days: dict[date, dict[str, Any]] = {}
    for e in entries:
        if e.get("r") is None:
            continue
        d = days.setdefault(_day(e), {"date": _day(e), "n": 0, "r": 0.0, "pnl_$": 0.0})
        d["n"] += 1
        d["r"] = round(d["r"] + e["r"], 6)
        d["pnl_$"] = round(d["pnl_$"] + (e.get("pnl_$") or 0.0), 6)
    return [days[k] for k in sorted(days)]


EXPORT_COLUMNS: tuple[str, ...] = (
    "id",
    "date",
    "symbol",
    "side",
    "stage",
    "account",
    "strategy",
    "grade",
    "tags",
    "source",
    "entry",
    "stop",
    "initial_stop",
    "target",
    "exit",
    "size",
    "fees",
    "r",
    "pnl_$",
    "scaled",
    "exit_reason",
)


def export_for_review(store: JournalStore, path: Path) -> Path:
    """One row per trade, oldest first, for the journal-review skill."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for e in reversed(store.list()):
            w.writerow(e | {"date": _day(e).isoformat(), "tags": ";".join(e.get("tags") or [])})
    return path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--db", default="data_store/journal.duckdb", type=Path)
    p.add_argument("--out", default="docs/reviews/journal-export.csv", type=Path)
    a = p.parse_args(argv)
    print(export_for_review(JournalStore(a.db), a.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
