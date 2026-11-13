"""Download new bars for every configured symbol and store them.

Run: python -m apollo.data.collect --root data_store --symbols all --intervals 1m,5m,15m,1h,1d
"""

import argparse
import logging
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

import polars as pl

from apollo.config import Symbol, load_symbols
from apollo.data.quality import check_quality
from apollo.data.resample import to_globex_daily
from apollo.data.store import append_bars, read_bars
from apollo.data.yahoo import Interval, fetch_bars

log = logging.getLogger(__name__)
Fetch = Callable[[Symbol, Interval], pl.DataFrame]


def collect(
    root: Path,
    symbols: dict[str, Symbol],
    intervals: list[Interval],
    fetch: Fetch = fetch_bars,
    today: date | None = None,
) -> dict[str, int]:
    """Fetch, store and quality-check each symbol/interval pair. One failure skips only that pair."""
    out_dir = root / "quality" / (today or date.today()).isoformat()
    written: dict[str, int] = {}
    for sym in symbols.values():
        for interval in intervals:
            key = f"{sym.code}/{interval}"
            written[key] = 0
            try:
                df = fetch(sym, interval)
                if df.is_empty():
                    log.warning("%s: no data", key)
                    continue
                written[key] = append_bars(root, df, interval)
                out_dir.mkdir(parents=True, exist_ok=True)
                report = check_quality(df, interval, kind=sym.kind, now=datetime.now(UTC))
                (out_dir / f"{sym.code}_{interval}.json").write_text(report.to_json())
                log.info("%s: %d rows", key, written[key])
            except Exception as e:  # noqa: BLE001 - any error must skip only this pair
                log.warning("%s: failed: %s", key, e)
        if sym.kind == "future" and {"1d", "1h"} <= set(intervals):
            try:
                _daily_from_hourly(root, sym.code)
            except Exception as e:  # noqa: BLE001
                log.warning("%s/1d: rebuild from 1h failed: %s", sym.code, e)
    return written


def _daily_from_hourly(root: Path, code: str) -> None:
    """Replace the last week's futures daily bars with ones built from the stored 1H bars.

    The nightly job often starts after 18:00 ET. By then Yahoo files the new session's first hours
    under today's date, and that partial bar would replace the finished day. Hourly bars carry no
    such label, so the days they cover are rebuilt from them. A first day whose hours start after
    its 18:00 ET open is only part of a session, so it is left as it was.
    """
    hourly = read_bars(root, code, "1h").tail(24 * 7)
    daily = to_globex_daily(hourly)
    if not daily.is_empty() and hourly["ts"][0] > daily["ts"][0]:
        daily = daily.slice(1)
    append_bars(root, daily, "1d")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default="data_store", type=Path)
    p.add_argument("--symbols", default="all", help="comma list of codes, or 'all'")
    p.add_argument("--intervals", default="1m,5m,15m,1h,1d")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    syms = load_symbols()
    if a.symbols != "all":
        syms = {c: syms[c] for c in a.symbols.split(",")}
    intervals = cast(list[Interval], a.intervals.split(","))
    written = collect(a.root, syms, intervals, fetch=fetch_bars)
    return 1 if not any(written.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
