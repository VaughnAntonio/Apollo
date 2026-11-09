"""Public run log (spec 5.13): one row per model run, so the number of attempts is visible."""

import csv
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
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def append_run(path: Path, row: dict) -> int:
    """Append one run and return its attempt number. Every run counts, repeats included."""
    path.parent.mkdir(parents=True, exist_ok=True)
    attempt = sum(1 for _ in path.open()) if path.exists() else 1  # header line + rows so far
    full = {
        **row,
        "attempt": attempt,
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_commit": _commit(),
    }
    new = not path.exists()
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(full)
    return attempt
