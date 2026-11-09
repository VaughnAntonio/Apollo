from datetime import date, timedelta

import numpy as np

from apollo.models.walkforward import refit_points, walk_forward
from tests.models.conftest import DATES_300


def test_refit_points_monthly():
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(400)]
    pts = refit_points(dates, first=250)
    assert pts[0] == 250 and all(dates[p].day == 1 for p in pts[1:]) and len(pts) == 6


def test_walk_forward_never_trains_on_future():
    seen = []

    def fit(X, y):
        seen.append(len(X))
        return len(X)

    out = walk_forward(
        np.zeros((300, 1)), np.zeros(300), DATES_300, fit, lambda m, X: np.full(len(X), m)
    )
    assert seen[0] == 250 and seen == sorted(seen)
    assert np.isnan(out[:250]).all() and (out[250:] <= np.arange(250, 300)).all()
