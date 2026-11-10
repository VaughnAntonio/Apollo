"""Write everything the public site reads as JSON files (spec 5.10).

Run: python -m apollo.export.snapshot --out web/public/snapshot
     [--root data_store] [--journal data_store/journal.duckdb] [--reports reports]

Only the case study's imported rows leave the journal, and only the fields in PUBLIC_FIELDS.
Notes, screenshots and model snapshots never do. A symbol that fails is listed in meta.json
and the rest still export.
"""

import argparse
import json
import math
from collections.abc import Callable
from datetime import UTC, date, datetime
from functools import partial
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from apollo.config import load_symbols
from apollo.data.serve import TIMEFRAMES, bars_json, read_tf
from apollo.explain import EXAMPLE, explain_day
from apollo.journal.stats import calendar, journal_stats
from apollo.journal.store import JournalStore
from apollo.live.signal import current_signal
from apollo.models.report import forecast_cached, ledger_summary

NY = ZoneInfo("America/New_York")
BARS_KEPT = {"1d": 750}  # every other timeframe keeps 300
LAYERS = ("D-1H", "1H-5m")
# An allow-list, so a column added to the journal later stays private until it's added here.
PUBLIC_FIELDS = (
    "id",
    "opened_at",
    "closed_at",
    "symbol",
    "side",
    "entry",
    "stop",
    "initial_stop",
    "target",
    "exit",
    "size",
    "fees",
    "account",
    "stage",
    "strategy",
    "grade",
    "tags",
    "source",
    "scaled",
    "imported_r",
    "imported_pnl",
    "exit_reason",
    "needs_confirm",
    "import_key",
    "risk_$",
    "pnl_$",
    "r",
    "win",
)


def _clean(x: Any) -> Any:
    """Strict JSON: NaN and infinity become null, dates become ISO strings."""
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, datetime | date):
        return x.isoformat()
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [_clean(v) for v in x]
    if hasattr(x, "item"):  # numpy scalars
        return _clean(x.item())
    return x


def _write(out: Path, rel: str, data: Any) -> None:
    path = out / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_clean(data), allow_nan=False, separators=(",", ":")))


def _read(path: Path) -> Any:
    return json.loads(path.read_text())  # Python's reader accepts the NaN the reports hold


def export_snapshot(
    root: Path, out: Path, *, journal_path: Path, reports_dir: Path, now: datetime
) -> dict:
    symbols = load_symbols()
    today = now.astimezone(NY).date()
    missing: list[dict] = []
    ok: list[str] = []

    def attempt(what: str, code: str, make: Callable[[], Any]) -> None:
        try:
            _write(out, f"{what}/{code}.json", make())
        except Exception as e:  # noqa: BLE001 - one symbol's failure must not stop the others
            missing.append({"what": what, "symbol": code, "reason": str(e)[:200]})

    _write(
        out,
        "symbols.json",
        [
            {"code": s.code, "name": s.name, "kind": s.kind, "model_enabled": s.model_enabled}
            for s in symbols.values()
        ],
    )
    for code, sym in symbols.items():
        wrote = False
        for tf in TIMEFRAMES:
            rows = bars_json(read_tf(root, code, tf).tail(BARS_KEPT.get(tf, 300)))
            if rows:
                _write(out, f"bars/{code}_{tf}.json", rows)
                wrote = True
        if wrote:
            ok.append(code)
        else:
            missing.append({"what": "bars", "symbol": code, "reason": "no bars collected yet"})
            continue
        if sym.model_enabled:
            attempt("signal", code, partial(current_signal, root, code, now))
            attempt("forecast", code, partial(forecast_cached, root, code, today, reports_dir))
        for layer in LAYERS:
            src = reports_dir / f"backtest_{code}_{layer}.json"
            if src.exists():
                _write(out, f"backtest/{code}_{layer}.json", _read(src))
        src = reports_dir / f"models_{code}.json"
        if src.exists():
            _write(out, f"models/{code}.json", _read(src) | {"ledger": ledger_summary(root, code)})

    rows = [
        {k: e[k] for k in PUBLIC_FIELDS if k in e}
        for e in JournalStore(journal_path).list(source="imported")
    ]
    _write(out, "journal.json", rows)
    _write(
        out,
        "journal_stats.json",
        {
            "stats": journal_stats(rows, signal_days=[]) | {"skipped": []},
            "calendar": calendar(rows),
        },
    )
    attempt(
        "explain", EXAMPLE["symbol"], partial(explain_day, root, EXAMPLE["symbol"], EXAMPLE["date"])
    )

    meta = {
        "generated": now.astimezone(UTC).isoformat(timespec="seconds"),
        "date": today.isoformat(),
        "symbols_ok": ok,
        "missing": missing,
    }
    _write(out, "meta.json", meta)
    return meta


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path("data_store"))
    p.add_argument("--journal", type=Path, default=None, help="default: <root>/journal.duckdb")
    p.add_argument("--reports", type=Path, default=Path("reports"))
    p.add_argument("--out", type=Path, default=Path("web/public/snapshot"))
    a = p.parse_args(argv)
    meta = export_snapshot(
        a.root,
        a.out,
        journal_path=a.journal or a.root / "journal.duckdb",
        reports_dir=a.reports,
        now=datetime.now(UTC),
    )
    print(f"exported {len(meta['symbols_ok'])} symbols to {a.out}")
    for m in meta["missing"]:
        print(f"  missing {m['what']} for {m['symbol']}: {m['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
