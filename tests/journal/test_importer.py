from pathlib import Path

from apollo.journal.importer import import_case_study
from apollo.journal.store import JournalStore

FIXTURE = Path(__file__).parents[1] / "fixtures" / "case_study"


def test_import_counts_and_r(tmp_path):
    s = JournalStore(tmp_path / "j.duckdb")
    assert import_case_study(s, FIXTURE) == 51
    rows = s.list(source="imported")
    first = next(
        e for e in rows if e["import_key"] == "case-study:1"
    )  # 2025-07-10, Backtest, trade 1
    assert first["r"] == -1.0 and first["scaled"] is True and first["stage"] == "backtest"
    assert first["strategy"] == "Forever Model" and first["side"] is None


def test_grade_family_and_import_twice(tmp_path):
    s = JournalStore(tmp_path / "j.duckdb")
    import_case_study(s, FIXTURE)
    assert {e["grade"] for e in s.list(source="imported")} <= {None, "A", "B", "C", "E"}
    assert import_case_study(s, FIXTURE) == 0 and len(s.list()) == 51
