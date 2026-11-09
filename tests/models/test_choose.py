from datetime import date, timedelta

import numpy as np

from apollo.models.report import choose_model
from apollo.models.sessions import LABELS


def test_model_chosen_only_on_sessions_before_the_boundary():
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(20)]
    y = np.array(["chop"] * 20, dtype=object)
    good, bad = np.eye(4)[[LABELS.index("chop")]], np.full((1, 4), 0.25)
    # logit is right before the boundary (day 10) and wrong after; gbm the other way round
    logit = np.vstack([good] * 10 + [np.eye(4)[[0]]] * 10)
    gbm = np.vstack([bad] * 10 + [good] * 10)
    probs = {"logit": logit, "gbm": gbm}
    assert choose_model(probs, y, dates, first=0, before=dates[10]) == "logit"
    assert choose_model(probs, y, dates, first=0, before=None) == "gbm"
