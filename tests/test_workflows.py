"""Safety checks on the publish workflow. Plain text checks: PyYAML isn't a dependency."""

import re
from pathlib import Path

PUBLISH = Path(".github/workflows/publish.yml")


def steps(text: str) -> list[str]:
    """Each `- name:` / `- uses:` / `- run:` step of the build job, as its own block of text."""
    build = text.split("\n  deploy:")[0].split("\n  build:")[1]
    return re.split(r"\n      - ", build)[1:]


def test_publish_workflow_is_safe():
    text = PUBLISH.read_text()
    assert "permissions:\n  contents: read\n  pages: write\n  id-token: write\n" in text
    assert 'workflows: ["Collect bars"]' in text and "workflow_dispatch:" in text
    assert "group: pages" in text
    assert "journal.duckdb" not in text.replace("snap_journal.duckdb", "")  # never the private journal
    assert "--final" not in text  # the holdout stays locked
    blocks = steps(text)
    backtests = [b for b in blocks if "apollo.strategy.backtest" in b]
    assert backtests and all("continue-on-error: true" in b for b in backtests)
    snapshot = [b for b in blocks if "apollo.export.snapshot" in b]
    assert snapshot and not any("continue-on-error" in b for b in snapshot)
    assert "--journal snap_journal.duckdb" in snapshot[0]
    assert "VITE_MODE=static VITE_BASE=/Apollo/" in text
    assert "cp web/dist/index.html web/dist/404.html" in text
    assert "actions/upload-pages-artifact@v3" in text and "path: web/dist" in text
    deploy = text.split("\n  deploy:")[1]
    assert "needs: build" in deploy and "actions/deploy-pages@v4" in deploy
    assert "name: github-pages" in deploy


def test_ci_builds_the_static_site():
    ci = Path(".github/workflows/ci.yml").read_text()
    assert "VITE_MODE=static VITE_BASE=/Apollo/ npm --prefix web run build" in ci
