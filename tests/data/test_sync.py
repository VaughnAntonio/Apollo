import subprocess
from pathlib import Path

import pytest

from apollo.data.sync import sync_data


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def make_repo_with_data_branch(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "README").write_text("main")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "main")
    _git(repo, "checkout", "-q", "--orphan", "data")
    _git(repo, "rm", "-rfq", ".")
    for rel in (
        "bars/MES/1h/2026-11.parquet",
        "ledger/MNQ/2026-11-10.json",
        "quality/x.json",
        "notes.txt",
    ):
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(rel)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "data")
    _git(repo, "checkout", "-q", "main")
    root = tmp_path / "root"
    root.mkdir()
    (root / "journal.duckdb").write_text("PRIVATE")
    return repo, root


def test_sync_copies_branch_files_and_keeps_the_journal(tmp_path):
    repo, root = make_repo_with_data_branch(tmp_path)
    counts = sync_data(root, ref="data", repo=repo)
    assert (root / "bars/MES/1h/2026-11.parquet").exists()
    assert (root / "ledger/MNQ/2026-11-10.json").exists()
    assert not (root / "notes.txt").exists()
    assert counts == {"bars": 1, "ledger": 1, "quality": 1}
    assert (root / "journal.duckdb").read_text() == "PRIVATE"  # never touched


def test_sync_refuses_a_missing_ref(tmp_path):
    repo, root = make_repo_with_data_branch(tmp_path)
    with pytest.raises(ValueError, match="no such ref"):
        sync_data(root, ref="nope", repo=repo)


def test_sync_merges_bar_files_so_local_bars_survive(tmp_path, bars):
    from apollo.data.store import append_bars, read_bars

    repo = tmp_path / "repo"
    branch_bars = bars("2026-11-03 10:00", 3, "1h")
    append_bars(repo, branch_bars, "1h")
    _git(repo, "init", "-q", "-b", "data")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "data")
    root = tmp_path / "root"
    append_bars(
        root, bars("2026-11-03 08:00", 3, "1h"), "1h"
    )  # 08:00-10:00, older than the branch's
    sync_data(root, ref="data", repo=repo)
    got = read_bars(root, "MNQ", "1h")
    assert (
        got.height == 5
    )  # 08:00 and 09:00 kept, 10:00 taken from the branch, 11:00 and 12:00 added
