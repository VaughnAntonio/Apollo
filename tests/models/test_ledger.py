import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from apollo.models.ledger import score_ledger, write_forecast

NY = ZoneInfo("America/New_York")
FORECAST_FOR_NOV_10 = {
    "date": "2026-11-10",
    "model": "logit",
    "proba": {"trend_up": 0.4, "trend_down": 0.1, "chop": 0.2, "normal": 0.3},
    "up_bound": 120.0,
    "down_bound": 110.0,
}


def test_no_forecast_after_session_start(tmp_path):
    late = datetime(2026, 11, 10, 9, 1, tzinfo=NY)
    assert write_forecast(tmp_path, "MNQ", FORECAST_FOR_NOV_10, late) is None
    assert not (tmp_path / "ledger").exists()


def test_rewrite_same_day_is_identical(tmp_path):
    early = datetime(2026, 11, 9, 18, 0, tzinfo=NY)
    a = write_forecast(tmp_path, "MNQ", FORECAST_FOR_NOV_10, early)
    assert a is not None and a == tmp_path / "ledger" / "MNQ" / "2026-11-10.json"
    first = a.read_text()
    write_forecast(tmp_path, "MNQ", FORECAST_FOR_NOV_10, early)
    assert a.read_text() == first


def test_score_marks_hits_once(tmp_path):
    early = datetime(2026, 11, 2, 18, 0, tzinfo=NY)
    for d in ("2026-11-03", "2026-11-04"):
        f = {**FORECAST_FOR_NOV_10, "date": d, "up_bound": 5.0, "down_bound": 5.0}
        write_forecast(tmp_path, "MNQ", f, early)
    sessions = pl.DataFrame(
        {
            "date": [date(2026, 11, 3), date(2026, 11, 4)],
            "open": [100.0, 100.0],
            "high": [104.0, 106.0],
            "low": [97.0, 99.0],
            "bars": [7, 7],
            "label": ["chop", "trend_up"],
        }
    )
    assert score_ledger(tmp_path, "MNQ", sessions) == {"n": 2, "hit_both": 1}
    entry = json.loads((tmp_path / "ledger/MNQ/2026-11-03.json").read_text())
    assert entry["hit_both"] is True and entry["actual_label"] == "chop"
    stamp = entry["scored_at"]
    score_ledger(tmp_path, "MNQ", sessions)  # already scored: left alone
    assert json.loads((tmp_path / "ledger/MNQ/2026-11-03.json").read_text())["scored_at"] == stamp


@pytest.mark.skipif(not Path("data_store/bars/MNQ/1h").exists(), reason="no local data")
def test_report_on_real_data_has_baselines():
    from apollo.models.report import build_report

    r = build_report(Path("data_store"), "MNQ")
    assert set(r["regime"]) == {"logit", "gbm", "majority", "yesterday", "frequency"}
    assert r["range"]["n"] > 100 and r["chosen"] in ("logit", "gbm")
    assert r["latest"]["date"] > r["sessions"][-1]["date"]
