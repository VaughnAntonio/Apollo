"""Public run log (spec 5.13): one row per model run, so the number of attempts is visible."""

import csv
import io
import subprocess
from datetime import UTC, datetime
from pathlib import Path

COLUMNS = (
    "attempt",
    "run_at",
    "git_commit",
    "code",
    "feature_set",
    "config_hash",
    "n_scored",
    "logit_acc",
    "logit_ll",
    "gbm_ll",
    "freq_ll",
    "range_both",
    "range_width",
)


def _commit() -> str:
    """The checked-out commit, marked "-dirty" when the code that ran has uncommitted changes."""
    try:
        cmd = ["git", "describe", "--always", "--dirty"]
        return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _last_attempt(path: Path) -> int:
    if not path.exists():
        return 0
    rows = [r for r in csv.DictReader(path.open()) if (r.get("attempt") or "").strip()]
    return max((int(r["attempt"]) for r in rows), default=0)


def append_run(path: Path, row: dict, columns: tuple[str, ...] = COLUMNS) -> int:
    """Append one run and return its attempt number. Every logged run counts, repeats included."""
    path.parent.mkdir(parents=True, exist_ok=True)
    attempt = _last_attempt(path) + 1
    full = {
        **row,
        "attempt": attempt,
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_commit": _commit(),
    }
    text = path.read_text() if path.exists() else ""
    if not text.strip():
        text = ",".join(columns) + "\n"
    text = text.rstrip("\n") + "\n"  # drop stray blank lines; make sure the last row ends cleanly
    out = io.StringIO()
    csv.DictWriter(out, fieldnames=columns, extrasaction="ignore").writerow(full)
    path.write_text(text + out.getvalue())
    return attempt
