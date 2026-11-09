"""Results you can weigh: expectancy with a bootstrap range, drawdown, benchmarks over the same
window, and a Monte Carlo of passing or breaching a prop-firm account (spec 5.7, 5.13)."""

from datetime import date, timedelta

import numpy as np
import polars as pl

from apollo.config import Symbol
from apollo.strategy.config import Account


def expectancy_ci(r: np.ndarray, n_boot: int = 10_000, seed: int = 7) -> dict:
    """Mean R per trade with a 95% bootstrap percentile range."""
    r = np.asarray(r, dtype=float)
    if r.size == 0:
        return {
            "n": 0,
            "mean": float("nan"),
            "low": float("nan"),
            "high": float("nan"),
            "win_rate": float("nan"),
        }
    means = np.random.default_rng(seed).choice(r, (n_boot, r.size)).mean(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return {
        "n": int(r.size),
        "mean": float(r.mean()),
        "low": float(low),
        "high": float(high),
        "win_rate": float((r > 0).mean()),
    }


def equity_stats(trades: pl.DataFrame) -> dict:
    t = trades.filter(pl.col("skip").is_null() & pl.col("net_$").is_not_null()).sort("session")
    if t.is_empty():
        return {
            "net_$": 0.0,
            "max_dd_$": 0.0,
            "max_dd_r": 0.0,
            "profit_factor": float("nan"),
            "trades_per_month": 0.0,
        }

    def max_dd(x: np.ndarray) -> float:
        curve = np.concatenate([[0.0], np.cumsum(x)])
        return float((curve - np.maximum.accumulate(curve)).min())

    net = t["net_$"].to_numpy()
    wins, losses = net[net > 0].sum(), -net[net < 0].sum()
    days = t["session"].to_list()
    months = max(1.0, (days[-1] - days[0]).days / 30.44)
    return {
        "net_$": float(net.sum()),
        "max_dd_$": max_dd(net),
        "max_dd_r": max_dd(t["r"].to_numpy()),
        "profit_factor": float(wins / losses) if losses else float("inf"),
        "trades_per_month": float(len(net) / months),
    }


def benchmarks(d1: pl.DataFrame, start: date, end: date, sym: Symbol) -> dict:
    """Buy & hold and the case study's MA 20/50 rule, 1 contract, over [start, end]."""
    shift = timedelta(hours=6) if sym.kind == "future" else timedelta(0)
    d = d1.sort("ts").with_columns(
        day=(pl.col("ts").dt.convert_time_zone("America/New_York") + shift).dt.date(),
        pts=pl.col("close") - pl.col("close").shift(1),
        # long today only if the 20-day average was above the 50-day at yesterday's close
        long=(pl.col("close").rolling_mean(20) > pl.col("close").rolling_mean(50)).shift(1),
    )
    w = d.filter(pl.col("day").is_between(start, end)).drop_nulls("pts")
    pv = sym.point_value
    return {
        "buy_hold_$": float(w["pts"].to_numpy().sum()) * pv,
        "ma_20_50_$": float(w.filter(pl.col("long").fill_null(False))["pts"].to_numpy().sum()) * pv,
    }


def prop_monte_carlo(
    r: np.ndarray,
    account: Account,
    risk_pct: float,
    n_paths: int = 10_000,
    max_trades: int = 200,
    seed: int = 7,
) -> dict:
    """Resample the trade R-multiples into many trade sequences and run each through the account.

    The trailing threshold is min(peak - drawdown, lock) above the start, as on APEX and TOPSTEP.
    A path passes when it reaches the profit target before touching the threshold.
    """
    r = np.asarray(r, dtype=float)
    if r.size == 0:
        return {
            "p_pass": float("nan"),
            "p_breach": float("nan"),
            "median_trades_to_pass": float("nan"),
        }
    rng = np.random.default_rng(seed)
    pnl = rng.choice(r, (n_paths, max_trades)) * risk_pct * account.size
    equity = np.cumsum(pnl, axis=1)
    peak = np.maximum(np.maximum.accumulate(equity, axis=1), 0.0)
    threshold = np.minimum(peak - account.drawdown, account.lock)
    never = max_trades + 1

    def first(mask: np.ndarray) -> np.ndarray:
        return np.where(mask.any(axis=1), mask.argmax(axis=1), never)

    breach, passed = first(equity <= threshold), first(equity >= account.profit_target)
    ok = passed < breach
    return {
        "p_pass": float(ok.mean()),
        "p_breach": float((breach < never).mean()),
        "median_trades_to_pass": float(np.median(passed[ok] + 1)) if ok.any() else float("nan"),
    }
