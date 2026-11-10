import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from apollo.data.store import append_bars
from apollo.export import snapshot
from apollo.export.snapshot import PUBLIC_FIELDS, export_snapshot
from apollo.journal.importer import import_case_study
from apollo.journal.store import JournalStore

FIXTURES = Path(__file__).parents[1] / "fixtures"
NOW = datetime(2026, 11, 10, 23, tzinfo=UTC)
MANUAL = {
    "opened_at": datetime(2026, 11, 3, 15, tzinfo=UTC),
    "symbol": "MNQ",
    "side": "long",
    "entry": 102.0,
    "stop": 99.75,
    "target": 110.0,
    "size": 1,
}


@pytest.fixture
def store_with_bars(tmp_path, bars, monkeypatch):
    root = tmp_path / "data"
    for code in ("MNQ", "MES"):
        append_bars(root, bars("2026-11-03 09:00", 10, "5m", symbol=code), "5m")
        append_bars(root, bars("2026-11-03 09:00", 10, "1h", symbol=code), "1h")
    # the real models need years of bars; these tests are about what gets written
    monkeypatch.setattr(
        snapshot,
        "forecast_cached",
        lambda root, code, today, d: {"latest": {"date": "x", "p": float("nan")}},
    )
    monkeypatch.setattr(
        snapshot, "current_signal", lambda root, code, now: {"status": "no_setup", "as_of": now}
    )
    monkeypatch.setattr(snapshot, "explain_day", lambda root, code, day: {"date": "x"})
    return root


def run(root, tmp_path):
    return export_snapshot(
        root,
        tmp_path / "out",
        journal_path=tmp_path / "j.duckdb",
        reports_dir=tmp_path / "reports",
        now=NOW,
    )


def test_snapshot_never_exports_private_rows(tmp_path, store_with_bars):
    j = JournalStore(tmp_path / "j.duckdb")
    import_case_study(j, FIXTURES / "case_study")
    j.add(MANUAL | {"notes": "my private note", "source": "manual"})
    i = j.add(MANUAL | {"source": "signal", "model_snapshot": {"x": 1}})
    j.update(i, {"screenshot": "journal_media/1-abc.png"})
    run(store_with_bars, tmp_path)
    rows = json.loads((tmp_path / "out/journal.json").read_text())
    assert len(rows) == 51 and {r["source"] for r in rows} == {"imported"}
    assert all(set(r) <= set(PUBLIC_FIELDS) for r in rows)
    assert all(
        "notes" not in r and "screenshot" not in r and "model_snapshot" not in r for r in rows
    )
    blob = "".join(p.read_text() for p in (tmp_path / "out").rglob("*.json"))
    assert "my private note" not in blob and "journal_media" not in blob
    stats = json.loads((tmp_path / "out/journal_stats.json").read_text())
    assert stats["stats"]["skipped"] == [] and sum(d["n"] for d in stats["calendar"]) <= 51


def test_one_failing_symbol_is_listed_not_fatal(tmp_path, store_with_bars, monkeypatch):
    def fail_for_mes(root, code, today, d):
        if code == "MES":
            raise ValueError("MES: 10 usable sessions")
        return {"latest": {}}

    monkeypatch.setattr(snapshot, "forecast_cached", fail_for_mes)
    meta = run(store_with_bars, tmp_path)
    missing = [{k: m[k] for k in ("what", "symbol")} for m in meta["missing"]]
    assert {"what": "forecast", "symbol": "MES"} in missing
    assert (tmp_path / "out/forecast/MNQ.json").exists()
    assert not (tmp_path / "out/forecast/MES.json").exists()
    assert "MNQ" in meta["symbols_ok"] and meta["date"] == "2026-11-10"
    assert json.loads((tmp_path / "out/meta.json").read_text()) == meta


def test_bars_are_capped_and_json_is_strict(tmp_path, store_with_bars, bars):
    append_bars(store_with_bars, bars("2026-11-04 09:00", 400, "5m"), "5m")
    run(store_with_bars, tmp_path)
    got = json.loads((tmp_path / "out/bars/MNQ_5m.json").read_text())
    assert len(got) == 300 and set(got[0]) == {"time", "open", "high", "low", "close", "volume"}
    assert not (tmp_path / "out/bars/NVDA_5m.json").exists()  # no bars, no file
    for p in (tmp_path / "out").rglob("*.json"):  # browsers reject NaN
        json.loads(p.read_text(), parse_constant=lambda c, p=p: pytest.fail(f"{p.name} has {c}"))


def test_reports_are_copied_when_present(tmp_path, store_with_bars):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "backtest_MNQ_D-1H.json").write_text('[{"variant": "plain", "x": NaN}]')
    (reports / "backtest_MNQ_D-1H_final.json").write_text("[]")
    (reports / "models_MNQ.json").write_text('{"both": {"chosen": "logit"}}')
    run(store_with_bars, tmp_path)
    assert json.loads((tmp_path / "out/backtest/MNQ_D-1H.json").read_text()) == [
        {"variant": "plain", "x": None}
    ]
    assert json.loads((tmp_path / "out/models/MNQ.json").read_text())["ledger"]["n"] == 0
    assert not list((tmp_path / "out/backtest").glob("*final*"))


def test_the_worked_example_is_exported(tmp_path, store_with_bars, monkeypatch):
    monkeypatch.setattr(snapshot, "explain_day", lambda root, code, day: {"date": day.isoformat()})
    run(store_with_bars, tmp_path)
    assert json.loads((tmp_path / "out/explain/MNQ.json").read_text()) == {"date": "2026-04-22"}


def test_missing_reports_are_listed_for_model_symbols(tmp_path, store_with_bars):
    meta = run(store_with_bars, tmp_path)
    missing = {(m["what"], m["symbol"]) for m in meta["missing"]}
    assert ("models", "MNQ") in missing and ("backtest", "MNQ") in missing
    assert ("models", "NVDA") not in missing  # stocks have no model to report on


def test_a_failed_export_removes_the_file_from_an_earlier_run(
    tmp_path, store_with_bars, monkeypatch
):
    run(store_with_bars, tmp_path)
    assert (tmp_path / "out/signal/MNQ.json").exists()

    def fail(root, code, now):
        raise ValueError("no bars today")

    monkeypatch.setattr(snapshot, "current_signal", fail)
    run(store_with_bars, tmp_path)
    assert not (tmp_path / "out/signal/MNQ.json").exists()  # never yesterday's signal as today's
