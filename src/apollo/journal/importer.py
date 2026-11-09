"""Import the case study's public journal (spec 5.8). Its dollars are scaled by one hidden factor,
so those rows are flagged `scaled` and keep the case study's own R and P&L. Prices, sizes and the
trade direction weren't published, so they stay empty ("Not recorded")."""

import csv
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from apollo.journal.store import GRADES, JournalStore

NY = ZoneInfo("America/New_York")


def import_case_study(store: JournalStore, csv_dir: Path) -> int:
    """Add every case-study trade once; returns how many were new."""
    added, seen = 0, store.import_keys()
    with (csv_dir / "trades_public.csv").open() as f:
        for row in csv.DictReader(f):
            key = f"case-study:{row['trade_id']}"  # date+account+trade_no repeats once (2025-10-20)
            if key in seen:  # already imported
                continue
            day = datetime.fromisoformat(row["date"]).date()
            grade = (row["setup_grade"] or "")[:1]
            store.add(
                {
                    # the time of day wasn't recorded; 09:30 ET marks the session only
                    "opened_at": datetime.combine(day, time(9, 30), tzinfo=NY),
                    "symbol": "MNQ",
                    "side": None,
                    "account": row["account_name"],
                    "stage": row["account_type"],
                    "strategy": row["strategy_main"] if row["strategy_main"] != "NA" else None,
                    "grade": grade if grade in GRADES else None,
                    "source": "imported",
                    "scaled": True,
                    "imported_r": float(row["r_multiple"]),
                    "imported_pnl": float(row["pnl_scaled"]),
                    "import_key": key,
                }
            )
            added += 1
    return added
