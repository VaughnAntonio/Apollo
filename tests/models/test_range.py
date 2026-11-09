import numpy as np
import polars as pl
import pytest

from apollo.models.range import conformal_upper, coverage, range_forecasts
from tests.models.conftest import DATES_300, DATES_1000


def _iid(n, seed):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 2))
    scale = 1 + np.abs(X[:, 0])
    return X, rng.exponential(scale), rng.exponential(scale)


def _with_actuals(f: pl.DataFrame, up, down) -> pl.DataFrame:
    return f.with_columns(open=pl.lit(0.0), high=pl.Series(up), low=pl.Series(-down))


def test_conformal_rank():
    assert conformal_upper(np.arange(1, 20, dtype=float), 0.05) == 19.0  # ceil(20 * 0.95) = 19
    assert conformal_upper(np.arange(1, 10, dtype=float), 0.05) == np.inf  # rank 10 > 9 residuals


def test_matches_mapie_split_conformal():
    from mapie.regression import SplitConformalRegressor
    from sklearn.linear_model import LinearRegression

    rng = np.random.default_rng(1)
    X = rng.normal(size=(400, 1))
    y = 2 * X[:, 0] + rng.normal(size=400)
    model = LinearRegression().fit(X[:200], y[:200])
    m = SplitConformalRegressor(model, confidence_level=0.9, prefit=True)
    m.conformalize(X[200:], y[200:])
    _, iv = m.predict_interval(X[:1])
    ours = conformal_upper(np.abs(y[200:] - model.predict(X[200:])), 0.10)
    assert iv[0, 1, 0] - model.predict(X[:1])[0] == pytest.approx(ours)


def test_coverage_near_nominal_on_iid_data():
    X, up, down = _iid(1000, 5)
    cov = coverage(_with_actuals(range_forecasts(X, up, down, DATES_1000), up, down))
    assert 0.86 <= cov["both"] <= 0.94 and cov["n"] == 1000 - 250 - 30


def test_no_bound_before_min_calib():
    X, up, down = _iid(300, 6)
    f = range_forecasts(X, up, down, DATES_300)
    assert f["up_bound"].is_not_null().arg_max() == 250 + 30
    assert f["up_pred"][249] is None and f["up_pred"][250] is not None


def test_coverage_by_regime():
    f = pl.DataFrame(
        {
            "open": [0.0] * 4,
            "high": [1.0, 3.0, 1.0, 1.0],
            "low": [-1.0, -1.0, -1.0, -3.0],
            "up_bound": [2.0] * 4,
            "down_bound": [2.0] * 4,
            "label": ["chop", "chop", "normal", "normal"],
        }
    )
    cov = coverage(f)
    assert cov["both"] == 0.5 and cov["by_regime"] == {"chop": 0.5, "normal": 0.5}
    assert cov["mean_width"] == 4.0
