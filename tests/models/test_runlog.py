from pathlib import Path

import polars as pl
import pytest

from apollo.models.runlog import append_run

ROW = {
    "code": "MNQ",
    "feature_set": "both",
    "config_hash": "abc123",
    "n_scored": 239,
    "logit_acc": 0.35,
    "logit_ll": 1.34,
    "gbm_ll": 1.6,
    "freq_ll": 1.3,
    "range_both": 0.89,
    "range_width": 1100.0,
}


def test_attempts_count_every_run(tmp_path):
    p = tmp_path / "runs" / "log.csv"
    assert append_run(p, ROW) == 1 and append_run(p, ROW) == 2
    log = pl.read_csv(p)
    assert log["attempt"].to_list() == [1, 2] and {"run_at", "git_commit"} <= set(log.columns)


REAL = Path("data_store/context/vol.parquet").exists() and Path("data_store/bars/MNQ/1h").exists()


@pytest.mark.skipif(not REAL, reason="no local data")
def test_health_set_reproduces_plan_3_and_both_reports_events():
    from apollo.models.report import build_report

    health = build_report(Path("data_store"), "MNQ", feature_set="health")
    assert health["regime"]["logit"]["n"] == 239
    assert round(health["regime"]["logit"]["log_loss"], 3) == 1.344
    both = build_report(Path("data_store"), "MNQ", feature_set="both")
    assert set(both["range"]["by_event"]) == {"0", "1"} and both["feature_set"] == "both"
