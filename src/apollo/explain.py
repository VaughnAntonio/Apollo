"""Worked examples for the Guide page: one past MNQ day, step by step (spec 5.11).

The regime and range parts are the walk-forward forecasts for that day, with the model chosen on
earlier sessions only, so nothing after the 08:00 ET cutoff feeds them. The actual high, low and
regime are shown last, as what happened.
"""

import tomllib
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import polars as pl

from apollo.config import CONFIG_DIR, load_symbols
from apollo.data.serve import bars_json
from apollo.data.store import read_bars
from apollo.fractal.model import run_model
from apollo.models.health import FEATURES, health_features
from apollo.models.report import build_report
from apollo.strategy.candidates import build_candidates
from apollo.strategy.config import load_trade_config

NY = ZoneInfo("America/New_York")
_raw = tomllib.loads((CONFIG_DIR / "strategy.toml").read_text())["explain"]
EXAMPLE: dict[str, Any] = {"symbol": _raw["symbol"], "date": _raw["date"]}


def _sec(t: datetime | None) -> int | None:
    return None if t is None else int(t.timestamp())


def _fractal(root: Path, code: str, day: date) -> dict[str, Any]:
    sym, cfg = load_symbols()[code], load_trade_config()
    setups = run_model(root, code, "D-1H")
    d1, h1 = read_bars(root, code, "1d"), read_bars(root, code, "1h")
    cands = build_candidates(setups, h1, pl.DataFrame(), sym, cfg, cfg.variants["plain"], "D-1H")
    hit = cands.filter((pl.col("session") == day) & pl.col("skip").is_null())
    if hit.is_empty():
        raise ValueError(f"no plain D-1H trade on {day}")
    c = hit.row(0, named=True)
    s = setups.filter(pl.col("c2_ts") == c["setup_ts"]).row(0, named=True)
    end = datetime.combine(day + timedelta(days=1), time(0), tzinfo=NY).astimezone(UTC)
    htf = d1.filter((pl.col("ts") >= s["c1_ts"] - timedelta(days=12)) & (pl.col("ts") < end))
    ltf = h1.filter((pl.col("ts") >= s["c2_ts"]) & (pl.col("ts") < end))
    return {
        "htf": bars_json(htf),
        "ltf": bars_json(ltf),
        "setup": {
            "direction": s["direction"],
            "c1_ts": _sec(s["c1_ts"]),
            "c2_ts": _sec(s["c2_ts"]),
            "c2_close": _sec(s["c2_close"]),
            "c1_high": s["c1_high"],
            "c1_low": s["c1_low"],
            "poi_level": s["poi_level"],
            "poi_kind": s["poi_kind"],
            "cisd_ts": _sec(s["after_c2_cisd_ts"]),
            "cisd_level": s["after_c2_cisd_level"],
            "protected": s["after_c2_protected"],
            "entry_ts": _sec(c["entry_ts"]),
            "entry": c["entry"],
            "stop": c["stop"],
            "target": c["target"],
        },
    }


def explain_day(root: Path, code: str, day: date) -> dict[str, Any]:
    fractal = _fractal(root, code, day)
    sym = load_symbols()[code]
    report = build_report(root, code, select_before=day)  # the model is chosen on earlier days
    rows = [r for r in report["sessions"] if r["date"] <= day.isoformat()]
    if not rows or rows[-1]["date"] != day.isoformat():
        raise ValueError(f"{day} is not a scored session")
    row = rows[-1]
    sessions = report["_sessions_frame"]
    feats = health_features(
        sessions, read_bars(root, code, "1h"), read_bars(root, code, "1d"), sym
    ).filter(pl.col("date") == day)
    actual = sessions.filter(pl.col("date") == day).row(0, named=True)
    scored = [r for r in rows if r["hit_both"] is not None]
    return {
        "date": day.isoformat(),
        "symbol": code,
        "fractal": fractal,
        "regime": {
            "features": {f: feats[f][0] for f in FEATURES},
            "proba": row["proba"],
            "model": report["chosen"],
            "label": row["label"],
        },
        "range": {
            "open": row["open"],
            "up_bound": row["up_bound"],
            "down_bound": row["down_bound"],
            "high": actual["high"],
            "low": actual["low"],
            "hit_both": row["hit_both"],
            "coverage_60": [{"date": r["date"], "hit_both": r["hit_both"]} for r in scored[-60:]],
        },
    }
