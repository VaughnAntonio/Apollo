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


def test_attempt_survives_blank_lines_and_missing_newline(tmp_path):
    p = tmp_path / "log.csv"
    append_run(p, ROW)
    p.write_text(p.read_text() + "\n\n")  # stray blank lines
    assert append_run(p, ROW) == 2
    p.write_text(p.read_text().rstrip("\n"))  # an editor dropped the final newline
    assert append_run(p, ROW) == 3
    assert pl.read_csv(p)["attempt"].to_list() == [1, 2, 3]


def test_empty_file_starts_at_one(tmp_path):
    p = tmp_path / "log.csv"
    p.write_text("")
    assert append_run(p, ROW) == 1 and pl.read_csv(p)["attempt"].to_list() == [1]


REAL = Path("data_store/context/vol.parquet").exists() and Path("data_store/bars/MNQ/1h").exists()


@pytest.mark.skipif(not REAL, reason="no local data")
def test_health_set_reproduces_plan_3_and_both_reports_events():
    from apollo.models.report import build_report

    health = build_report(Path("data_store"), "MNQ", feature_set="health")
    assert health["regime"]["logit"]["n"] == 237  # 239 before the 2026-11-10 sync lost 2 sessions
    assert round(health["regime"]["logit"]["log_loss"], 3) == 1.338
    both = build_report(Path("data_store"), "MNQ", feature_set="both")
    assert set(both["range"]["by_event"]) == {"0", "1"} and both["feature_set"] == "both"
