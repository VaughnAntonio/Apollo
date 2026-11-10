"""Backtest the Fractal Model strategy, variant by variant, with the last months held out.

Run: python -m apollo.strategy.backtest --symbol MNQ --layer D-1H --variants all [--tearsheet]
     python -m apollo.strategy.backtest ... --final     (one-time test on the held-out months)

Development runs never see the holdout. A --final run tests only the holdout and writes
runs/holdout.lock; a later --final with a different config is refused. Every variant run is
appended to runs/backtests.csv.
"""

import argparse
import hashlib
import json
import subprocess
from dataclasses import replace
from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

from apollo.config import CONFIG_DIR, load_symbols
from apollo.data.store import read_bars
from apollo.fractal.model import PAIRINGS, run_model
from apollo.models.runlog import append_run
from apollo.strategy.candidates import build_candidates
from apollo.strategy.config import TradeConfig, load_trade_config
from apollo.strategy.metrics import (
    benchmark_curves,
    benchmarks,
    equity_stats,
    expectancy_ci,
    monthly_table,
    prop_monte_carlo,
)
from apollo.strategy.simulate import simulate

NY = ZoneInfo("America/New_York")
Layer = Literal["D-1H", "1H-5m"]
LOAD: Any = object()  # "load it from the data store", so tests can pass frames in instead
RUNS = Path("runs")
BACKTEST_COLUMNS = (
    "attempt",
    "run_at",
    "git_commit",
    "code",
    "layer",
    "variant",
    "final",
    "config_hash",
    "n_trades",
    "expectancy_r",
    "ci_low",
    "ci_high",
    "win_rate",
    "max_dd_r",
    "p_pass_1pct",
)


def holdout_start(sessions: list[date], months: int) -> date:
    """The first session on or after the date `months` calendar months before the last one."""
    last = sessions[-1]
    y, m = divmod(last.year * 12 + last.month - 1 - months, 12)
    boundary = date(y, m + 1, min(last.day, 28))
    return next(d for d in sessions if d >= boundary)


def config_hash(layer: str, variant: str) -> str:
    text = "".join((CONFIG_DIR / f).read_text() for f in ("strategy.toml", "accounts.toml"))
    return hashlib.sha256(f"{text}|{layer}|{variant}".encode()).hexdigest()[:12]


@lru_cache(maxsize=8)
def _forecasts(root: str, code: str, select_before: date) -> pl.DataFrame:
    from apollo.models.report import forecast_frame  # slow: fits the models once per process

    return forecast_frame(Path(root), code, select_before=select_before)


def _when(c: dict) -> date:
    t = c["session"] or (c["signal_ts"] or c["setup_ts"]).astimezone(NY).date()
    return t if isinstance(t, date) else t.date()


def run_backtest(
    root: Path,
    code: str,
    layer: Layer,
    variant_name: str,
    cfg: TradeConfig,
    final: bool = False,
    *,
    setups: pl.DataFrame = LOAD,
    bars: pl.DataFrame = LOAD,
    forecasts: pl.DataFrame = LOAD,
    d1: pl.DataFrame | None = LOAD,
    sessions: list[date] = LOAD,
) -> dict:
    sym = load_symbols()[code]
    variant = cfg.variants[variant_name]
    if setups is LOAD:
        setups = run_model(root, code, layer)
    if bars is LOAD:
        bars = read_bars(root, code, PAIRINGS[layer][1])  # type: ignore[arg-type]
    if forecasts is LOAD:
        forecasts = _forecasts(str(root), code, cfg.holdout_from)
    if d1 is LOAD:
        d1 = read_bars(root, code, "1d")
    if sessions is LOAD:
        # One holdout date for every layer, taken from the hourly history (the longest intraday one).
        et = read_bars(root, code, "1h")["ts"].dt.convert_time_zone("America/New_York")
        sessions = sorted(
            {d for d, wd in zip(et.dt.date(), et.dt.weekday(), strict=True) if wd <= 5}
        )

    before_data = 0
    if "ltf_missing" in setups.columns:  # older than the lower-timeframe history: not a test case
        before_data = setups.filter(pl.col("ltf_missing")).height
        setups = setups.filter(~pl.col("ltf_missing"))
    boundary = cfg.holdout_from  # pinned: more data never moves it
    cands = build_candidates(setups, bars, forecasts, sym, cfg, variant, layer)
    keep = [(_when(c) >= boundary) == final for c in cands.iter_rows(named=True)]
    cands = cands.filter(pl.Series(keep, dtype=pl.Boolean))
    when = [_when(c) for c in cands.iter_rows(named=True)]
    # The strategy's record ignores the account: with no limit, a breach can't hide later trades.
    # The account run then answers the separate question of what the prop firm would have allowed.
    unlimited = replace(cfg, account=replace(cfg.account, drawdown=1e12, lock=1e12))
    trades, _ = simulate(cands, bars, sym, unlimited, variant)
    acct_trades, state = simulate(cands, bars, sym, cfg, variant)
    acct_done = acct_trades.filter(pl.col("skip").is_null())

    skips: dict[str, int] = {}
    for s in [*cands["skip"].drop_nulls().to_list(), *trades["skip"].drop_nulls().to_list()]:
        skips[s] = skips.get(s, 0) + 1
    done = trades.filter(pl.col("skip").is_null())
    skips["traded"] = done.height
    r = done["r"].to_numpy()
    period = {"start": min(when) if when else None, "end": max(when) if when else None}
    bench = benchmarks(d1, min(when), max(when), sym) if d1 is not None and when else {}
    daily = done.group_by("session").agg(pl.col("net_$").sum()).sort("session")
    closed = done.filter(pl.col("net_$").is_not_null()).sort("exit_ts")
    by_exit = (
        closed.group_by(day=pl.col("exit_ts").dt.convert_time_zone("America/New_York").dt.date())
        .agg(pl.col("net_$").sum())
        .sort("day")
    )
    curves = {
        "strategy": [
            {"date": d.isoformat(), "usd": float(v)}
            for d, v in zip(by_exit["day"], by_exit["net_$"].cum_sum(), strict=True)
        ],
        **(benchmark_curves(d1, min(when), max(when), sym) if d1 is not None and when else {}),
    }
    return {
        "code": code,
        "layer": layer,
        "variant": variant_name,
        "final": final,
        "config_hash": config_hash(layer, variant_name),
        "holdout_from": boundary,
        "period": period,
        "n_setups": cands.height,
        "setups_before_data": before_data,
        "skip_counts": skips,
        "expectancy": expectancy_ci(r),
        "equity": equity_stats(trades),
        "monte_carlo": {
            "1%": prop_monte_carlo(r, cfg.account, 0.01),
            "2%": prop_monte_carlo(r, cfg.account, 0.02),
        },
        "benchmarks": bench,
        "trades": [
            {
                "session": t["session"].isoformat(),
                "direction": t["direction"],
                "r": t["r"],
                "net_$": t["net_$"],
                "exit_reason": t["exit_reason"],
            }
            for t in done.sort("session").iter_rows(named=True)
        ],
        "curves": curves,
        "monthly": monthly_table(trades),
        "account": {
            "name": cfg.account.name,
            "trades": acct_done.height,
            "net_$": float(acct_done["net_$"].sum()) if acct_done.height else 0.0,
            "breached_at": state["breached_at"],
            "peak_$": state["peak"],
        },
        "_trades": trades,
        "_daily": daily,
    }


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=False
    ).stdout.strip()


def check_lock(
    path: Path, chash: str, variants: list[str], *, commit: str, dirty: bool, holdout_from: date
) -> str:
    """Allow --final only on committed code, with the code, config and holdout of the first one.

    Returns the lock hash, which every final run logs so its rows can be matched to the lock.
    """
    if dirty:
        raise SystemExit("Commit your changes first: a final test must name the exact code it ran.")
    spec = f"{chash}|{commit}|{holdout_from.isoformat()}|{','.join(sorted(variants))}"
    lock_hash = hashlib.sha256(spec.encode()).hexdigest()[:12]
    if path.exists():
        lock = json.loads(path.read_text())
        if lock["lock_hash"] != lock_hash:
            raise SystemExit(
                f"The holdout was already used on {lock['date']} (commit {lock['commit']}, "
                f"config {lock['config_hash']}). A second final test with different code or rules "
                "would no longer be out of sample."
            )
        return lock_hash
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "date": datetime.now(UTC).date().isoformat(),
        "commit": commit,
        "config_hash": chash,
        "holdout_from": holdout_from.isoformat(),
        "variants": sorted(variants),
        "lock_hash": lock_hash,
    }
    path.write_text(json.dumps(record, indent=2))
    return lock_hash


def log_backtest(path: Path, res: dict) -> int:
    e = res["expectancy"]
    row = {
        "code": res["code"],
        "layer": res["layer"],
        "variant": res["variant"],
        "final": res["final"],
        "config_hash": res["config_hash"],
        "n_trades": e["n"],
        "expectancy_r": round(e["mean"], 4),
        "ci_low": round(e["low"], 4),
        "ci_high": round(e["high"], 4),
        "win_rate": round(e["win_rate"], 4),
        "max_dd_r": round(res["equity"]["max_dd_r"], 3),
        "p_pass_1pct": round(res["monte_carlo"]["1%"]["p_pass"], 3),
    }
    return append_run(path, row, BACKTEST_COLUMNS)


def _tearsheet(res: dict, cfg: TradeConfig, out: Path) -> None:
    import pandas as pd
    import quantstats as qs

    daily = res["_daily"]
    if daily.is_empty():
        return
    returns = pd.Series(
        (daily["net_$"] / cfg.account.size).to_list(),
        index=pd.to_datetime(daily["session"].to_list()),
        name=res["variant"],
    )
    title = f"Apollo {res['code']} {res['layer']} {res['variant']}"
    qs.reports.html(returns, output=str(out), title=title)


def _fmt(x: float) -> str:
    return "  n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:+.2f}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--root", default="data_store", type=Path)
    p.add_argument("--symbol", default="MNQ")
    p.add_argument("--layer", default="D-1H", choices=list(PAIRINGS)[::2])  # D-1H and 1H-5m
    p.add_argument("--variants", default="all")
    p.add_argument("--final", action="store_true")
    p.add_argument("--tearsheet", action="store_true")
    a = p.parse_args(argv)

    cfg = load_trade_config()
    names = list(cfg.variants) if a.variants == "all" else a.variants.split(",")
    layer = cast(Layer, a.layer)
    lock_hash = None
    if a.final:
        dirty = bool(_git("status", "--porcelain", "--", "src", "config"))
        lock_hash = check_lock(
            RUNS / "holdout.lock",
            config_hash(layer, ",".join(names)),
            names,
            commit=_git("rev-parse", "HEAD"),
            dirty=dirty,
            holdout_from=cfg.holdout_from,
        )

    results = []
    print(
        f"{a.symbol} {layer} {'FINAL (holdout)' if a.final else 'development (holdout excluded)'}"
    )
    print(
        f"{'variant':<17}{'trades':>7}{'exp R':>8}{'95% range':>17}{'win':>6}{'maxDD R':>9}"
        f"{'pass 1%':>9}{'pass 2%':>9}  top skips"
    )
    for name in names:
        res = run_backtest(a.root, a.symbol, layer, name, cfg, a.final)
        if lock_hash:
            res["config_hash"] = lock_hash  # final rows point at the lock
        res["attempt"] = log_backtest(RUNS / "backtests.csv", res)
        e, mc = res["expectancy"], res["monte_carlo"]
        skips = sorted(
            ((v, k) for k, v in res["skip_counts"].items() if k != "traded"), reverse=True
        )[:3]
        print(
            f"{name:<17}{e['n']:>7}{_fmt(e['mean']):>8}   [{_fmt(e['low'])}, {_fmt(e['high'])}]"
            f"{e['win_rate'] if e['n'] else float('nan'):>6.0%}{res['equity']['max_dd_r']:>9.1f}"
            f"{mc['1%']['p_pass']:>9.0%}{mc['2%']['p_pass']:>9.0%}  "
            + ", ".join(f"{k} {v}" for v, k in skips)
        )
        if a.tearsheet:
            out = Path("reports") / f"tearsheet_{a.symbol}_{layer}_{name}.html"
            out.parent.mkdir(exist_ok=True)
            _tearsheet(res, cfg, out)
        results.append(res)

    first = results[0]
    print(
        f"period {first['period']['start']} to {first['period']['end']}, holdout from {first['holdout_from']}"
    )
    if first["benchmarks"]:
        b = first["benchmarks"]
        print(
            f"benchmarks, 1 contract: buy & hold ${b['buy_hold_$']:,.0f}, MA 20/50 ${b['ma_20_50_$']:,.0f}"
        )
    out = Path("reports") / f"backtest_{a.symbol}_{layer}{'_final' if a.final else ''}.json"
    out.parent.mkdir(exist_ok=True)
    clean = [{k: v for k, v in r.items() if not k.startswith("_")} for r in results]
    out.write_text(json.dumps(clean, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
