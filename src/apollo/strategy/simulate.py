"""Walk candidate trades through real bars under the account's rules (spec 5.6-5.7).

Fills are at the entry bar's open. A bar that touches both the stop and the target counts as a
stop. Every position is flat at the close of the last bar that opens before `flat_at` ET. Costs
are commission plus slippage per contract per side, taken off the gross P&L.
"""

from datetime import date, datetime
from math import floor
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

from apollo.config import Symbol
from apollo.data.yahoo import bar_close
from apollo.strategy.candidates import SCHEMA
from apollo.strategy.config import TradeConfig, Variant

NY = ZoneInfo("America/New_York")
TRADE_SCHEMA = {
    **SCHEMA,
    "exit_ts": pl.Datetime("us", "UTC"),
    "exit": pl.Float64,
    "contracts": pl.Int64,
    "exit_reason": pl.Utf8,
    "gross_$": pl.Float64,
    "costs_$": pl.Float64,
    "net_$": pl.Float64,
    "r": pl.Float64,
}


def _commission(sym: Symbol, cfg: TradeConfig) -> float:
    if sym.kind == "stock":
        return 0.0
    return cfg.commission["micro" if sym.code.startswith("M") else "emini"]


def _interval(bars: pl.DataFrame) -> str:
    step = (bars["ts"][1] - bars["ts"][0]).total_seconds() / 60 if bars.height > 1 else 60
    return {5: "5m", 15: "15m", 60: "1h"}.get(int(step), "1h")


def simulate(
    cands: pl.DataFrame, bars: pl.DataFrame, sym: Symbol, cfg: TradeConfig, variant: Variant
) -> tuple[pl.DataFrame, dict]:
    b = bars.sort("ts").with_columns(close_ts=bar_close(_interval(bars)))  # type: ignore[arg-type]
    ts, close_ts = b["ts"].to_list(), b["close_ts"].to_list()
    stamps = np.array([t.timestamp() for t in ts])
    hi, lo, cl = b["high"].to_list(), b["low"].to_list(), b["close"].to_list()
    pv, tick = sym.point_value, sym.tick_size
    per_side = _commission(sym, cfg) + cfg.slip_ticks * tick * pv
    acct = cfg.account

    equity = peak = 0.0
    threshold = min(peak - acct.drawdown, acct.lock)
    breached_at: datetime | None = None
    busy_until: datetime | None = None
    per_session: dict[date, list[float]] = {}
    curve: dict[date, float] = {}
    out = []

    for c in cands.filter(pl.col("skip").is_null()).sort("entry_ts").iter_rows(named=True):
        row = dict.fromkeys(TRADE_SCHEMA) | c
        session = c["session"]
        done = per_session.setdefault(session, [])
        if breached_at is not None:
            out.append(row | {"skip": "account_breached"})
            continue
        if busy_until is not None and c["entry_ts"] < busy_until:
            out.append(row | {"skip": "in_position"})
            continue
        if len(done) >= cfg.max_trades:
            out.append(row | {"skip": "max_trades"})
            continue
        if variant.risk_rules and sum(done) <= -cfg.daily_cap_r:
            out.append(row | {"skip": "daily_cap"})
            continue

        cushion = equity - threshold
        pct = cfg.risk_pct
        if variant.risk_rules and cushion < acct.drawdown / 2:
            pct = cfg.step_down_pct
        risk_usd = pct * acct.size * (0.5 if c["half_size"] else 1.0)
        per_contract = c["planned_stop_pts"] * pv
        contracts = floor(risk_usd / per_contract) if per_contract > 0 else 0
        if contracts == 0:
            out.append(row | {"skip": "size_zero"})
            continue
        planned_loss = contracts * per_contract
        if variant.risk_rules and planned_loss > cfg.cushion_frac * cushion:
            out.append(row | {"skip": "cushion"})
            continue

        sign = 1.0 if c["direction"] == "bull" else -1.0
        entry, stop, target = c["entry"], c["stop"], c["target"]
        reached_1r = False
        k = int(np.searchsorted(stamps, c["entry_ts"].timestamp()))
        exit_px = exit_t = reason = None
        for i in range(k, len(ts)):
            local = ts[i].astimezone(NY)
            if local.date() != session or local.time() >= cfg.flat_at:
                exit_px, exit_t, reason = cl[i - 1], close_ts[i - 1], "flat"
                break
            if reached_1r and variant.breakeven:
                stop = entry if sign * (entry - stop) > 0 else stop
            worst, best = (lo[i], hi[i]) if sign > 0 else (hi[i], lo[i])
            if sign * (worst - stop) <= 0:
                exit_px, exit_t = stop, close_ts[i]
                reason = "breakeven" if stop == entry else "stop"
                break
            if sign * (best - target) >= 0:
                exit_px, exit_t, reason = target, close_ts[i], "target"
                break
            if sign * (best - entry) >= c["planned_stop_pts"]:
                reached_1r = True  # takes effect from the next bar
        if exit_px is None:  # data ended while in the trade
            exit_px, exit_t, reason = cl[-1], close_ts[-1], "flat"

        gross = sign * (exit_px - entry) * pv * contracts
        costs = 2 * contracts * per_side
        net = gross - costs
        r = net / planned_loss
        row |= {
            "exit_ts": exit_t,
            "exit": exit_px,
            "contracts": contracts,
            "exit_reason": reason,
            "gross_$": gross,
            "costs_$": costs,
            "net_$": net,
            "r": r,
        }
        out.append(row)
        done.append(r)
        busy_until = exit_t
        equity += net
        peak = max(peak, equity)
        threshold = min(peak - acct.drawdown, acct.lock)
        curve[session] = equity
        if equity <= threshold:
            breached_at = exit_t

    trades = pl.DataFrame(out, schema=TRADE_SCHEMA) if out else pl.DataFrame(schema=TRADE_SCHEMA)
    state = {
        "equity_curve": curve,
        "equity": equity,
        "peak": peak,
        "threshold": threshold,
        "breached_at": breached_at,
    }
    return trades, state
