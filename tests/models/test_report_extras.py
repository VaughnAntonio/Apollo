import json
from datetime import date

import numpy as np
from sklearn.linear_model import LogisticRegression

from apollo.models import report
from apollo.models.report import feature_importance, forecast_cached, ledger_summary

FAKE_REPORT = {
    "latest": {"date": "2026-11-11", "proba": {"chop": 0.3}},
    "range": {"both": 0.9},
    "chosen": "logit",
    "sessions": [],
    "importance": [{"feature": "rms", "drop": 0.01}],
}


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def test_forecast_cached_refits_once_per_ny_day(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        report, "build_report", lambda root, code: calls.append(code) or FAKE_REPORT
    )
    a = forecast_cached(tmp_path, "MNQ", date(2026, 11, 10), cache_dir=tmp_path)
    b = forecast_cached(tmp_path, "MNQ", date(2026, 11, 10), cache_dir=tmp_path)
    c = forecast_cached(tmp_path, "MNQ", date(2026, 11, 11), cache_dir=tmp_path)
    assert calls == ["MNQ", "MNQ"] and a == b and c["date"] == "2026-11-11"
    assert set(a) >= {"latest", "model_check", "importance", "ledger"}
    assert json.loads((tmp_path / "forecast_MNQ.json").read_text())["date"] == "2026-11-11"


def test_feature_importance_finds_the_signal_feature():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(300, 3))
    y = ["trend_up" if v > 0 else "chop" for v in X[:, 1]]
    model = LogisticRegression().fit(X, y)
    imp = feature_importance(model, X, y, ["noise_a", "signal", "noise_b"])
    assert imp[0]["feature"] == "signal" and imp[0]["drop"] > imp[1]["drop"]
    assert len(imp) == 3


def test_ledger_summary(tmp_path):
    write_json(
        tmp_path / "ledger/MNQ/2026-11-10.json",
        {"date": "2026-11-10", "hit_both": True, "scored_at": "x"},
    )
    write_json(tmp_path / "ledger/MNQ/2026-11-11.json", {"date": "2026-11-11"})
    assert ledger_summary(tmp_path, "MNQ") == {
        "since": "2026-11-10",
        "n": 2,
        "scored": 1,
        "hit_both": 1.0,
    }
    assert ledger_summary(tmp_path, "MES") == {"since": None, "n": 0, "scored": 0, "hit_both": None}


def test_feature_importance_survives_a_tail_missing_a_regime():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(200, 2))
    y = np.where(X[:, 0] > 0.5, "trend_up", np.where(X[:, 0] < -0.5, "chop", "normal"))
    model = LogisticRegression().fit(X, y)
    tail = X[:, 0] > -0.5  # no chop in the scored rows
    imp = feature_importance(model, X[tail], list(y[tail]), ["a", "b"])
    assert imp[0]["feature"] == "a"
