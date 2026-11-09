"""Expanding-window walk-forward: refit on the first session of each month, predict the rest.

Every prediction for row i comes from a model trained only on rows before the latest refit at
or before i, so all reported scores are out-of-sample.
"""

from collections.abc import Callable
from datetime import date
from typing import Any

import numpy as np


def refit_points(dates: list[date], first: int = 250) -> list[int]:
    """Row `first`, then the first row of every later calendar month."""
    pts = [first] if first < len(dates) else []
    for i in range(first + 1, len(dates)):
        if (dates[i].year, dates[i].month) != (dates[i - 1].year, dates[i - 1].month):
            pts.append(i)
    return pts


def walk_forward(
    X: np.ndarray,
    y: np.ndarray,
    dates: list[date],
    fit: Callable[[np.ndarray, np.ndarray], Any],
    predict: Callable[[Any, np.ndarray], np.ndarray],
    first: int = 250,
) -> np.ndarray:
    """Out-of-sample predictions; rows before `first` are NaN."""
    pts = refit_points(dates, first)
    chunks = []
    for k, start in enumerate(pts):
        end = pts[k + 1] if k + 1 < len(pts) else len(X)
        model = fit(X[:start], y[:start])
        chunks.append(np.asarray(predict(model, X[start:end]), dtype=float))
    if not chunks:
        return np.full(len(X), np.nan)
    pred = np.concatenate(chunks)
    head = np.full((first, *pred.shape[1:]), np.nan)
    return np.concatenate([head, pred])
