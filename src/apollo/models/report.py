"""Score both models walk-forward, forecast the next session, and keep the ledger.

Run: python -m apollo.models.report --symbol MNQ [--root data_store] [--features both]
     [--ablation] [--write-ledger] [--score-ledger]

Every run is appended to runs/log.csv, so the number of attempts behind any result is public.
"""

import argparse
import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

from apollo.config import load_symbols
from apollo.data.store import read_bars
from apollo.models.context import CONTEXT_FEATURES, context_features
from apollo.models.health import FEATURES, health_features
from apollo.models.ledger import score_ledger, write_forecast
from apollo.models.range import _median_model, conformal_upper, coverage, range_forecasts
from apollo.models.regime import fit_regime, regime_baselines, regime_metrics
from apollo.models.returns import clean_returns
from apollo.models.runlog import append_run
from apollo.models.sessions import LABELS, build_sessions
from apollo.models.walkforward import walk_forward

NY = ZoneInfo("America/New_York")
FIRST, ALPHA, CALIB = 250, 0.05, 120
FeatureSet = Literal["health", "context", "both"]
FEATURE_SETS: dict[str, tuple[str, ...]] = {
    "health": FEATURES,
    "context": CONTEXT_FEATURES,
    "both": (*FEATURES, *CONTEXT_FEATURES),
}
RUN_LOG = Path("runs") / "log.csv"


def _config_hash(columns: tuple[str, ...]) -> str:
    spec = f"{columns}|{FIRST}|{ALPHA}|{CALIB}|logit:imputer+scaler+lr1000|gbm:d3,lr0.05,i200"
    return hashlib.sha256(spec.encode()).hexdigest()[:12]


def _context(root: Path) -> tuple[pl.DataFrame, pl.DataFrame]:
    """The cached OpenBB context, or empty frames when it hasn't been collected yet."""
    vol_p, ev_p = root / "context" / "vol.parquet", root / "context" / "events.parquet"
    vol = (
        pl.read_parquet(vol_p)
        if vol_p.exists()
        else pl.DataFrame(
            schema={"date": pl.Date, "vix": pl.Float64, "vix3m": pl.Float64, "vxn": pl.Float64}
        )
    )
    ev = (
        pl.read_parquet(ev_p)
        if ev_p.exists()
        else pl.DataFrame(schema={"date": pl.Date, "kind": pl.Utf8, "event": pl.Utf8})
    )
    return vol, ev


def _next_session(now: datetime) -> date:
    """The next session still to be forecast: today before 09:00 ET, else the next weekday."""
    local = now.astimezone(NY)
    d = local.date() if local.time() < time(9) else local.date() + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def build_report(
    root: Path, code: str, now: datetime | None = None, feature_set: FeatureSet = "both"
) -> dict:
    now = now or datetime.now(UTC)
    columns = FEATURE_SETS[feature_set]
    sym = load_symbols()[code]
    h1, d1 = read_bars(root, code, "1h"), read_bars(root, code, "1d")
    vol, events = _context(root)
    sessions = build_sessions(h1, sym)
    df = sessions.join(health_features(sessions, h1, d1, sym), on="date").join(
        context_features(sessions, vol, events), on="date"
    )
    jump_days = set(
        clean_returns(h1, sym)
        .filter("roll_jump")["ts"]
        .dt.convert_time_zone("America/New_York")
        .dt.date()
    )

    short = pl.col("label").is_null()
    warmup = pl.col("rms").is_null()
    rolled = pl.col("date").is_in(list(jump_days))
    dropped = {
        "short_session": df.filter(short).height,
        "warmup": df.filter(~short & warmup).height,
        "roll_jump": df.filter(~short & ~warmup & rolled).height,
    }
    use = df.filter(~short & ~warmup & ~rolled)
    if use.height < FIRST + 31:
        raise ValueError(f"{code}: {use.height} usable sessions, need more than {FIRST + 30}")

    # The same sessions for every feature set, so the ablation compares like with like.
    X = use.select(columns).to_numpy().astype(float)
    y = np.array(use["label"].to_list(), dtype=object)
    dates = use["date"].to_list()
    probs = {k: walk_forward(X, y, dates, *fit_regime(k), first=FIRST) for k in ("logit", "gbm")}
    probs |= regime_baselines(list(y), dates, FIRST)
    test = list(y[FIRST:])
    regime = {k: regime_metrics(p[FIRST:], test) for k, p in probs.items()}
    chosen = min(("logit", "gbm"), key=lambda k: regime[k]["log_loss"])

    # Regime probabilities only exist out-of-sample; earlier rows get an even 25% each.
    prior = np.nan_to_num(probs[chosen], nan=1 / len(LABELS))
    Xr = np.hstack([X, prior])
    up, down = use["up_exc"].to_numpy(), use["down_exc"].to_numpy()
    rf = range_forecasts(Xr, up, down, dates, ALPHA, CALIB, first=FIRST)
    scored = pl.concat([use, rf], how="horizontal")

    rows = []
    for i, r in enumerate(scored.iter_rows(named=True)):
        if i < FIRST:
            continue
        hit = None
        if r["up_bound"] is not None:
            hit = r["high"] <= r["open"] + r["up_bound"] and r["low"] >= r["open"] - r["down_bound"]
        rows.append(
            {
                "date": r["date"].isoformat(),
                "label": r["label"],
                "proba": dict(zip(LABELS, map(float, probs[chosen][i]), strict=True)),
                "up_bound": r["up_bound"],
                "down_bound": r["down_bound"],
                "hit_both": hit,
            }
        )

    # The next session: final models fitted on every usable session.
    nxt = _next_session(now)
    at = datetime.combine(nxt, time(8), tzinfo=NY).astimezone(UTC)  # the 08:00 ET cutoff
    ahead = pl.concat(
        [
            sessions.select("date", "forecast_at", "label", "close"),
            pl.DataFrame(
                {"date": [nxt], "forecast_at": [at], "label": [None], "close": [None]},
                schema=sessions.select("date", "forecast_at", "label", "close").schema,
            ),
        ]
    )
    ahead_f = health_features(ahead, h1, d1, sym).join(
        context_features(ahead, vol, events), on="date"
    )
    x_next = ahead_f.tail(1).select(columns).to_numpy().astype(float)
    fit, predict = fit_regime(chosen)  # type: ignore[arg-type]
    p_next = predict(fit(X, y), x_next)[0]
    xr_next = np.hstack([x_next, p_next[None, :]])
    latest = {
        "date": nxt.isoformat(),
        "model": chosen,
        "proba": dict(zip(LABELS, map(float, p_next), strict=True)),
    }
    for side, target in (("up", up), ("down", down)):
        pred_oos = scored[f"{side}_pred"].to_numpy()
        done = ~np.isnan(pred_oos.astype(float))
        resid = (target - pred_oos)[done][-CALIB:].astype(float)
        latest[f"{side}_bound"] = float(
            _median_model(Xr, target).predict(xr_next)[0] + conformal_upper(resid, ALPHA)
        )

    tail = scored.slice(FIRST)
    rng = coverage(tail)
    by_event = {
        key: coverage(tail.filter(pl.col("ev_any") == flag))
        for key, flag in (("0", 0.0), ("1", 1.0))
    }
    rng["by_event"] = {key: c["both"] for key, c in by_event.items()}
    rng["width_by_event"] = {key: c["mean_width"] for key, c in by_event.items()}

    return {
        "code": code,
        "generated": now.astimezone(UTC).isoformat(timespec="seconds"),
        "feature_set": feature_set,
        "config_hash": _config_hash(columns),
        "sessions_total": df.height,
        "sessions_used": use.height,
        "dropped": dropped,
        "regime": regime,
        "chosen": chosen,
        "range": rng,
        "sessions": rows,
        "latest": latest,
        "_sessions_frame": sessions,
    }


def _log_row(report: dict) -> dict:
    g, r = report["regime"], report["range"]
    return {
        "code": report["code"],
        "feature_set": report["feature_set"],
        "config_hash": report["config_hash"],
        "n_scored": g["logit"]["n"],
        "logit_acc": round(g["logit"]["accuracy"], 4),
        "logit_ll": round(g["logit"]["log_loss"], 4),
        "gbm_ll": round(g["gbm"]["log_loss"], 4),
        "freq_ll": round(g["frequency"]["log_loss"], 4),
        "range_both": round(r["both"], 4),
        "range_width": round(r["mean_width"], 1),
    }


def _print(report: dict, attempt: int) -> None:
    r = report["range"]
    print(
        f"{report['code']} [{report['feature_set']}] attempt {attempt}: {report['sessions_used']} sessions used, "
        f"dropped {report['dropped']}"
    )
    print(f"  {'model':<10}{'accuracy':>10}{'log-loss':>10}{'n':>6}")
    for k, m in report["regime"].items():
        print(f"  {k:<10}{m['accuracy']:>10.3f}{m['log_loss']:>10.3f}{m['n']:>6}")
    print(
        f"  range: both-sides hit {r['both']:.3f} (up {r['up']:.3f}, down {r['down']:.3f}), "
        f"mean width {r['mean_width']:.1f} pts, n {r['n']}"
    )
    print(
        f"  event days: hit {r['by_event'].get('1', float('nan')):.3f}, width {r['width_by_event'].get('1', float('nan')):.1f}"
        f" | other days: hit {r['by_event'].get('0', float('nan')):.3f}, width {r['width_by_event'].get('0', float('nan')):.1f}"
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default="data_store", type=Path)
    p.add_argument("--symbol", default="MNQ")
    p.add_argument("--features", default="both", choices=list(FEATURE_SETS))
    p.add_argument("--ablation", action="store_true", help="run health, context and both")
    p.add_argument("--write-ledger", action="store_true")
    p.add_argument("--score-ledger", action="store_true")
    a = p.parse_args(argv)

    now = datetime.now(UTC)
    sets = list(FEATURE_SETS) if a.ablation else [a.features]
    reports = {}
    for fs in sets:
        try:
            report = build_report(a.root, a.symbol, now, fs)  # type: ignore[arg-type]
        except ValueError as e:  # not enough data for this symbol yet
            print(f"skipped: {e}")
            return 1
        attempt = append_run(RUN_LOG, _log_row(report))
        _print(report, attempt)
        reports[fs] = report

    report = reports[sets[-1]]
    sessions = report.pop("_sessions_frame")
    if a.write_ledger:
        write_forecast(a.root, a.symbol, report["latest"], now)
    if a.score_ledger:
        report["ledger"] = score_ledger(a.root, a.symbol, sessions)
        print(f"ledger: {report['ledger']}")
    out = Path("reports") / f"models_{a.symbol}.json"
    out.parent.mkdir(exist_ok=True)
    for r in reports.values():
        r.pop("_sessions_frame", None)
    out.write_text(json.dumps(reports if a.ablation else report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
