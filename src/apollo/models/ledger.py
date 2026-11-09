"""Forecast ledger (spec 5.13): each forecast is written before its session and scored after.

The nightly Action commits these files, so git timestamps show no forecast was written late.
"""

import json
from datetime import UTC, date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl

NY = ZoneInfo("America/New_York")


def _path(root: Path, code: str, day: str) -> Path:
    return root / "ledger" / code / f"{day}.json"


def write_forecast(root: Path, code: str, forecast: dict, now: datetime) -> Path | None:
    """Write the forecast for forecast["date"], unless that session has already started."""
    day = forecast["date"]
    if now >= datetime.combine(date.fromisoformat(day), time(9), tzinfo=NY):
        return None
    path = _path(root, code, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {**forecast, "written_at": now.astimezone(UTC).isoformat(timespec="seconds")}
    path.write_text(json.dumps(entry, indent=2, sort_keys=True))
    return path


def score_ledger(root: Path, code: str, sessions: pl.DataFrame) -> dict:
    """Score every finished, unscored forecast; return totals over all scored forecasts."""
    done = {
        r["date"].isoformat(): r for r in sessions.filter(pl.col("bars") >= 7).iter_rows(named=True)
    }
    n = hits = 0
    for path in sorted((root / "ledger" / code).glob("*.json")):
        entry = json.loads(path.read_text())
        s = done.get(entry["date"])
        if "scored_at" not in entry and s is not None:
            entry["hit_both"] = bool(
                s["high"] <= s["open"] + entry["up_bound"]
                and s["low"] >= s["open"] - entry["down_bound"]
            )
            entry["actual_label"] = s["label"]
            entry["scored_at"] = datetime.now(UTC).isoformat(timespec="seconds")
            path.write_text(json.dumps(entry, indent=2, sort_keys=True))
        if "scored_at" in entry:
            n += 1
            hits += entry["hit_both"]
    return {"n": n, "hit_both": hits}
