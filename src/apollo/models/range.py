"""Range forecaster (spec 5.5): how far price may travel up and down from the session open.

Each side gets a one-sided split-conformal upper bound at 95%, recalibrated on the last 120
out-of-sample residuals, so the high and the low both stay inside the zone about 90% of the time.
"""

from datetime import date
from math import ceil

import numpy as np
import polars as pl
from sklearn.ensemble import HistGradientBoostingRegressor

from apollo.models.walkforward import walk_forward


def conformal_upper(residuals: np.ndarray, alpha: float) -> float:
    """The ceil((n+1)(1-alpha))-th smallest residual; infinite when there are too few."""
    n = len(residuals)
    rank = ceil((n + 1) * (1 - alpha))
    return float(np.sort(residuals)[rank - 1]) if rank <= n else float("inf")


def _median_model(X: np.ndarray, y: np.ndarray):
    model = HistGradientBoostingRegressor(loss="quantile", quantile=0.5, max_depth=3, max_iter=200)
    return model.fit(X, y)


def _bounds(
    y: np.ndarray, pred: np.ndarray, alpha: float, calib: int, min_calib: int
) -> np.ndarray:
    """pred + conformal quantile of the residuals from earlier sessions only."""
    out = np.full(len(y), np.nan)
    done = ~np.isnan(pred)
    for i in np.flatnonzero(done):
        past = np.flatnonzero(done[:i])[-calib:]
        if len(past) >= min_calib:
            out[i] = pred[i] + conformal_upper(y[past] - pred[past], alpha)
    return out


def range_forecasts(
    X: np.ndarray,
    up: np.ndarray,
    down: np.ndarray,
    dates: list[date],
    alpha: float = 0.05,
    calib: int = 120,
    min_calib: int = 30,
    first: int = 250,
) -> pl.DataFrame:
    """Median forecast and conformal upper bound for each side's excursion, walk-forward."""
    cols = {}
    for side, y in (("up", up), ("down", down)):
        pred = walk_forward(X, y, dates, _median_model, lambda m, Xs: m.predict(Xs), first)
        cols[f"{side}_pred"] = pred
        cols[f"{side}_bound"] = _bounds(y, pred, alpha, calib, min_calib)
    return pl.DataFrame(cols).fill_nan(None)


def _mean(s: pl.Series) -> float:
    v = s.cast(pl.Float64).mean()
    return float(v) if isinstance(v, int | float) else 0.0


def coverage(df: pl.DataFrame) -> dict:
    """How often the high and the low both stayed inside open - down_bound .. open + up_bound."""
    d = df.drop_nulls(["up_bound", "down_bound"])
    up_ok = d["high"] <= d["open"] + d["up_bound"]
    down_ok = d["low"] >= d["open"] - d["down_bound"]
    d = d.with_columns(both=up_ok & down_ok)
    out = {
        "n": d.height,
        "both": _mean(d["both"]),
        "up": _mean(up_ok),
        "down": _mean(down_ok),
        "mean_width": _mean(d["up_bound"] + d["down_bound"]),
    }
    if "label" in d.columns:
        by = d.drop_nulls("label").group_by("label").agg(pl.col("both").mean()).sort("label")
        out["by_regime"] = dict(by.iter_rows())
    return out
