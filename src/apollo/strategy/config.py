"""Trading, cost, account and risk settings from config/strategy.toml and config/accounts.toml."""

import tomllib
from dataclasses import dataclass
from datetime import time
from pathlib import Path

from apollo.config import CONFIG_DIR


@dataclass(frozen=True)
class Account:
    name: str
    size: float
    drawdown: float
    lock: float
    profit_target: float


@dataclass(frozen=True)
class Variant:
    regime: bool
    range: bool
    risk_rules: bool
    breakeven: bool
    fomc_cutoff: bool
    event_half: bool


@dataclass(frozen=True)
class TradeConfig:
    account: Account
    risk_pct: float
    min_rr: float
    max_trades: int
    stop_ticks_beyond: int
    flat_at: time
    range_room: float
    windows: dict[str, tuple[time, time]]
    commission: dict[str, float]
    slip_ticks: int
    daily_cap_r: float
    cushion_frac: float
    step_down_pct: float
    min_stop_ticks: int
    max_stop_zone_frac: float
    holdout_months: int
    variants: dict[str, Variant]


def _t(s: str) -> time:
    return time.fromisoformat(s)


def load_accounts(path: Path = CONFIG_DIR / "accounts.toml") -> dict[str, Account]:
    return {a["name"]: Account(**a) for a in tomllib.loads(path.read_text())["account"]}


def load_trade_config(path: Path = CONFIG_DIR / "strategy.toml") -> TradeConfig:
    raw = tomllib.loads(path.read_text())
    tr, costs, risk = raw["trade"], raw["costs"], raw["risk"]
    return TradeConfig(
        account=load_accounts()[tr["account"]],
        risk_pct=tr["risk_pct"],
        min_rr=tr["min_rr"],
        max_trades=tr["max_trades"],
        stop_ticks_beyond=tr["stop_ticks_beyond"],
        flat_at=_t(tr["flat_at"]),
        range_room=tr["range_room"],
        windows={k: (_t(a), _t(b)) for k, (a, b) in tr["windows"].items()},
        commission=dict(costs["commission"]),
        slip_ticks=costs["slip_ticks"],
        daily_cap_r=risk["daily_cap_r"],
        cushion_frac=risk["cushion_frac"],
        step_down_pct=risk["step_down_pct"],
        min_stop_ticks=risk["min_stop_ticks"],
        max_stop_zone_frac=risk["max_stop_zone_frac"],
        holdout_months=raw["backtest"]["holdout_months"],
        variants={k: Variant(*v) for k, v in raw["variants"].items()},
    )
