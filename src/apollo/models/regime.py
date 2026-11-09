"""Regime detector (spec 5.4): which kind of session comes next, as four probabilities."""

from collections import Counter
from datetime import date
from typing import Literal

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from apollo.models.sessions import LABELS
from apollo.models.walkforward import refit_points


def fit_regime(kind: Literal["logit", "gbm"]):
    """(fit, predict) for walk_forward. predict returns probabilities in LABELS order."""

    def fit(X: np.ndarray, y: np.ndarray):
        if kind == "logit":
            model = make_pipeline(
                SimpleImputer(strategy="median"),
                StandardScaler(),
                LogisticRegression(max_iter=1000),
            )
        else:
            model = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200)
        return model.fit(X, y)

    def predict(model, X: np.ndarray) -> np.ndarray:
        raw = model.predict_proba(X)
        out = np.zeros((len(X), len(LABELS)))
        for j, cls in enumerate(model.classes_):  # a class missing from training stays at 0
            out[:, LABELS.index(cls)] = raw[:, j]
        return out

    return fit, predict


def _one_hot(label: str | None) -> np.ndarray:
    if label is None:
        return np.full(len(LABELS), 1 / len(LABELS))
    return np.eye(len(LABELS))[LABELS.index(label)]


def regime_baselines(
    labels: list[str], dates: list[date], first: int = 250
) -> dict[str, np.ndarray]:
    """Two baselines: the most common label seen at each refit, and yesterday's label."""
    n = len(labels)
    majority = np.full((n, len(LABELS)), np.nan)
    pts = refit_points(dates, first)
    for k, start in enumerate(pts):
        end = pts[k + 1] if k + 1 < len(pts) else n
        majority[start:end] = _one_hot(Counter(labels[:start]).most_common(1)[0][0])
    yesterday = np.full((n, len(LABELS)), np.nan)
    for i in range(max(first, 1), n):
        yesterday[i] = _one_hot(labels[i - 1])
    return {"majority": majority, "yesterday": yesterday}


def regime_metrics(proba: np.ndarray, labels: list[str]) -> dict:
    """Accuracy, log-loss (probabilities clipped to 1e-6) and a 4x4 confusion matrix."""
    truth = np.array([LABELS.index(lab) for lab in labels])
    pred = proba.argmax(axis=1)
    p_true = np.clip(proba[np.arange(len(truth)), truth], 1e-6, 1.0)
    confusion = np.zeros((len(LABELS), len(LABELS)), dtype=int)
    np.add.at(confusion, (truth, pred), 1)
    return {
        "n": len(truth),
        "accuracy": float(np.mean(pred == truth)),
        "log_loss": float(-np.mean(np.log(p_true))),
        "confusion": confusion.tolist(),
    }
