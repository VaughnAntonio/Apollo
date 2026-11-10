"""Today's top-down checklist and signal (spec 5.6): daily bias, 4H, 1H, 15m, 5m trigger.

Every row comes from setups the Fractal Model pipeline already detected; nothing new is
inferred here. A trade signal ("trigger") needs every row to pass. Research only.
"""

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from math import floor
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import polars as pl

from apollo.config import load_symbols
from apollo.data.store import read_bars
from apollo.fractal.model import run_model
from apollo.strategy.candidates import build_candidates
from apollo.strategy.config import load_trade_config

NY = ZoneInfo("America/New_York")
FRESH = timedelta(minutes=10)  # a 5m fill this recent still counts as "now"


@dataclass
class CheckRow:
    step: str
    status: str  # pass | wait | fail | no_data
    detail: str


def _globex_day(t: datetime) -> date:
    local = t.astimezone(NY)
    return (local + timedelta(hours=6)).date()


def _prev_weekday(d: date) -> date:
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _closed_by(df: pl.DataFrame, col: str, now: datetime) -> pl.DataFrame:
    return df.filter(pl.col(col).is_not_null() & (pl.col(col) <= now))


def current_signal(
    root: Path | None, code: str, now: datetime, *, frames: dict | None = None
) -> dict[str, Any]:
    now = now.astimezone(UTC)  # the data is in UTC
    sym = load_symbols()[code]
    cfg = load_trade_config()
    base = {
        "symbol": code,
        "account": cfg.account.name,
        "variant": cfg.live_variant,
        "as_of": now,
        "research_only": True,
        "direction": None,
        "entry": None,
        "stop": None,
        "target": None,
        "contracts": None,
        "risk_of_limit": None,
        "checklist": [],
    }
    if not sym.model_enabled:
        return base | {"status": "no_model"}
    if frames is None:
        assert root is not None
        from apollo.models.report import forecast_frame  # slow; the API caches the result

        frames = {p: run_model(root, code, p) for p in ("D-1H", "4H-15m", "1H-5m")}
        frames["bars_5m"] = read_bars(root, code, "5m")
        frames["forecasts"] = forecast_frame(root, code)
    variant = cfg.variants[cfg.live_variant]
    today = now.astimezone(NY).date()
    rows: list[CheckRow] = []

    # Daily bias: C2 is the last completed daily bar, or C3 has closed through it.
    daily = _closed_by(frames["D-1H"], "c2_close", now)
    recent = _prev_weekday(today)
    bias = None
    for s in daily.sort("c2_close", descending=True).iter_rows(named=True):
        closed_day = s["c2_close"].astimezone(NY).date()
        if closed_day >= recent or (s["c3_closed"] and closed_day >= _prev_weekday(recent)):
            bias = s
        break
    if bias is None:
        rows.append(CheckRow("daily_bias", "fail", "No daily C2 setup from the last session"))
        rows += [
            CheckRow(st, "wait", "Needs a daily bias") for st in ("4h", "1h", "15m", "5m_trigger")
        ]
        return base | {"status": "flat", "checklist": [asdict(r) for r in rows]}
    direction = bias["direction"]
    rows.append(
        CheckRow(
            "daily_bias",
            "pass",
            f"{direction} C2 closed {bias['c2_close'].astimezone(NY):%a %H:%M} ET",
        )
    )

    same = pl.col("direction") == direction
    four = frames["4H-15m"].filter(same)
    four_today = [
        s
        for s in _closed_by(four, "c2_close", now).iter_rows(named=True)
        if _globex_day(s["c2_ts"]) == today
    ]
    rows.append(
        CheckRow(
            "4h",
            "pass" if four_today else "wait",
            f"4H C2 closed {four_today[-1]['c2_close'].astimezone(NY):%H:%M} ET"
            if four_today
            else "No 4H C2 in the bias direction yet",
        )
    )

    confirmed = bias["after_c2_cisd_confirmed_at"]
    live = bias["window_end"] is None or now < bias["window_end"]
    one_ok = confirmed is not None and confirmed <= now and live
    rows.append(
        CheckRow(
            "1h",
            "pass" if one_ok else "wait",
            f"1H CISD at {bias['after_c2_cisd_level']:,.2f}"
            if one_ok
            else "Waiting for the 1H CISD",
        )
    )

    fifteen = [
        s
        for s in four_today
        if s["after_c2_cisd_confirmed_at"] is not None and s["after_c2_cisd_confirmed_at"] <= now
    ]
    rows.append(
        CheckRow(
            "15m",
            "pass" if fifteen else "wait",
            "15m CISD confirmed" if fifteen else "Waiting for the 15m CISD",
        )
    )

    five = frames["1H-5m"].filter(same & pl.col("after_c2_cisd_ts").is_not_null())
    cands = build_candidates(
        five, frames["bars_5m"], frames["forecasts"], sym, cfg, variant, "1H-5m"
    )
    fresh = cands.filter(
        pl.col("skip").is_null()
        & (pl.col("session") == today)
        & (pl.col("entry_ts") >= now - FRESH)
        & (pl.col("entry_ts") <= now + timedelta(minutes=5))
    )
    trigger = fresh.sort("entry_ts").tail(1).row(0, named=True) if fresh.height else None
    rows.append(
        CheckRow(
            "5m_trigger",
            "pass" if trigger else "wait",
            f"5m CISD, fill {trigger['entry_ts'].astimezone(NY):%H:%M} ET"
            if trigger
            else "No 5m trigger in the 09:30-12:00 window",
        )
    )

    out = base | {"direction": direction, "checklist": [asdict(r) for r in rows]}
    if trigger is None or any(r.status != "pass" for r in rows):
        return out | {"status": "waiting"}
    per_contract = trigger["planned_stop_pts"] * sym.point_value
    contracts = floor(cfg.risk_pct * cfg.account.size / per_contract) if per_contract > 0 else 0
    return out | {
        "status": "trigger" if contracts > 0 else "waiting",
        "entry": trigger["entry"],
        "stop": trigger["stop"],
        "target": trigger["target"],
        "contracts": contracts,
        "risk_of_limit": contracts * per_contract / cfg.account.drawdown,
    }
