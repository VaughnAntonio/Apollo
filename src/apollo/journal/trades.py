"""Take trade, close and auto-close (spec 5.8).

Take trade freezes what the model said at that moment into the entry's snapshot. Auto-close uses
the backtest's own bar rules, then waits for Vaughn to confirm the fill.
"""

from datetime import UTC, datetime
from typing import Any

import numpy as np
import polars as pl

from apollo.config import load_symbols
from apollo.data.yahoo import bar_close
from apollo.journal.store import SIDES, JournalStore
from apollo.strategy.config import load_trade_config
from apollo.strategy.walk import NY, walk_trade

AUTO_REASONS = {
    "stop": "stop_auto",
    "target": "target_auto",
    "flat": "flat_auto",
    "breakeven": "stop_auto",
}


def build_snapshot(signal: dict[str, Any], forecast: dict[str, Any] | None) -> dict[str, Any]:
    keep = (
        "status",
        "direction",
        "entry",
        "stop",
        "target",
        "contracts",
        "risk_of_limit",
        "variant",
    )
    return {
        "snapshot_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "signal": {k: signal.get(k) for k in keep},
        "checklist": signal.get("checklist", []),
        "forecast": forecast,
    }


def take_trade(
    store: JournalStore,
    signal: dict[str, Any],
    forecast: dict[str, Any] | None,
    fill: float | None = None,
    size: int | None = None,
) -> int:
    """Journal the current signal as a trade (source "signal")."""
    if signal.get("status") != "trigger":
        raise ValueError("there is no trade signal right now")
    contracts = size if size is not None else signal["contracts"]
    cfg, sym = load_trade_config(), load_symbols()[signal["symbol"]]
    commission = (
        0.0
        if sym.kind == "stock"
        else cfg.commission["micro" if sym.code.startswith("M") else "emini"]
    )
    return store.add(
        {
            "opened_at": signal["as_of"],
            "symbol": signal["symbol"],
            "side": "long" if signal["direction"] == "bull" else "short",
            "entry": fill if fill is not None else signal["entry"],
            "stop": signal["stop"],
            "target": signal["target"],
            "size": contracts,
            "fees": 2 * contracts * commission,  # commission both ways; slippage is in the fill
            "account": signal.get("account"),
            "stage": signal.get("stage", "live"),
            "strategy": "Fractal Model (Apollo signal)",
            "source": "signal",
            "model_snapshot": build_snapshot(signal, forecast),
        }
    )


def close_trade(
    store: JournalStore, id: int, exit: float, at: datetime, reason: str
) -> dict[str, Any]:
    return store.update(
        id, {"exit": exit, "closed_at": at, "exit_reason": reason, "needs_confirm": False}
    )


def auto_close(
    store: JournalStore, bars_by_symbol: dict[str, pl.DataFrame], now: datetime
) -> list[int]:
    """Close open trades whose stop, target or 16:00 ET flat time has passed in the bars."""
    flat_at = load_trade_config().flat_at
    closed = []
    for e in store.list():
        bars = bars_by_symbol.get(e["symbol"])
        if e["exit"] is not None or e["source"] == "imported" or bars is None or bars.is_empty():
            continue
        b = bars.sort("ts").filter(pl.col("ts") <= now)
        step = int(np.diff(b["ts"].dt.epoch("s").to_numpy()).min()) // 60 if b.height > 1 else 60
        b = b.with_columns(close_ts=bar_close({5: "5m", 15: "15m"}.get(step, "1h")))  # type: ignore[arg-type]
        b = b.filter(pl.col("close_ts") <= now)  # only bars that have finished
        stamps = np.array([t.timestamp() for t in b["ts"]])
        opened = e["opened_at"]
        k = max(int(np.searchsorted(stamps, opened.timestamp(), side="right")) - 1, 0)
        risk_pts = abs(e["entry"] - e["initial_stop"])
        px, at, reason = walk_trade(
            b["ts"].to_list(),
            b["close_ts"].to_list(),
            b["high"].to_list(),
            b["low"].to_list(),
            b["close"].to_list(),
            k,
            opened.astimezone(NY).date(),
            e["entry"],
            e["stop"],
            e["target"],
            SIDES[e["side"]],
            risk_pts,
            flat_at,
        )
        if px is None or reason == "open":
            continue
        store.update(
            e["id"],
            {
                "exit": px,
                "closed_at": at,
                "exit_reason": AUTO_REASONS[reason],
                "needs_confirm": True,
            },
        )
        closed.append(e["id"])
    return closed
