import numpy as np
import pytest

from apollo.models.regime import fit_regime, regime_baselines, regime_metrics
from apollo.models.sessions import LABELS
from apollo.models.walkforward import walk_forward
from tests.models.conftest import DATES_300


def test_unseen_class_gets_zero_and_finite_loss():
    X = np.random.default_rng(0).normal(size=(300, 3))
    y = np.array(["chop", "normal"] * 150)
    fit, predict = fit_regime("logit")
    p = walk_forward(X, y, DATES_300, fit, predict)[250:]
    assert p.shape == (50, 4) and (p[:, LABELS.index("trend_down")] == 0).all()
    assert np.isfinite(regime_metrics(p, list(y[250:]))["log_loss"])


@pytest.mark.parametrize("kind", ["logit", "gbm"])
def test_learns_separable_signal_with_missing_values(kind):
    X = np.random.default_rng(3).normal(size=(300, 2))
    y = np.where(X[:, 0] > 0.5, "trend_up", np.where(X[:, 0] < -0.5, "chop", "normal"))
    X[::17, 1] = np.nan  # warm-up gaps must not break either model
    fit, predict = fit_regime(kind)
    p = walk_forward(X, y, DATES_300, fit, predict)[250:]
    assert regime_metrics(p, list(y[250:]))["accuracy"] > 0.9


def test_baselines():
    y = ["chop"] * 200 + ["normal"] * 100
    b = regime_baselines(y, DATES_300)
    assert b["majority"][250, LABELS.index("chop")] == 1.0
    assert b["yesterday"][260, LABELS.index("normal")] == 1.0


def test_metrics_confusion():
    p = np.eye(4)[[0, 1, 2, 2]]
    m = regime_metrics(p, ["trend_up", "trend_down", "chop", "normal"])
    assert m["accuracy"] == 0.75 and m["n"] == 4 and m["confusion"][3][2] == 1
