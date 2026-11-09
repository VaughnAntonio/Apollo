"""Refresh the market-context cache in <root>/context/.

Run: python -m apollo.context.collect --root data_store

A provider outage keeps the existing files, logs it and still exits 0, so a Cboe or Nasdaq hiccup
can't stop the nightly or pre-open jobs.
"""

import argparse
import logging
from datetime import date, timedelta
from pathlib import Path

import polars as pl

from apollo.context.fetch import fetch_events, fetch_vol

log = logging.getLogger(__name__)
VOL_START = date(2019, 1, 1)
EVENTS_START = date(2024, 1, 1)
WINDOW = timedelta(days=60)


def _rows(path: Path) -> int:
    return pl.read_parquet(path).height if path.exists() else 0


def collect_context(
    root: Path, today: date, fetch_vol=fetch_vol, fetch_events=fetch_events
) -> dict[str, int]:
    out = root / "context"
    out.mkdir(parents=True, exist_ok=True)
    vol_path, ev_path = out / "vol.parquet", out / "events.parquet"

    try:
        vol = fetch_vol(VOL_START)
        if vol_path.exists() and vol.height < pl.read_parquet(vol_path).height:
            raise ValueError(f"short response ({vol.height} rows); keeping the longer cache")
        vol.write_parquet(vol_path)
    except Exception as e:  # noqa: BLE001 - an outage must keep yesterday's file
        log.warning("vol: kept cached file: %s", e)

    try:
        start, end = (today - WINDOW if ev_path.exists() else EVENTS_START), today + WINDOW
        new = fetch_events(start, end)
        # The fresh fetch is the truth for its window, so moved or cancelled releases drop out.
        kept = (
            pl.read_parquet(ev_path).filter(~pl.col("date").is_between(start, end))
            if ev_path.exists()
            else None
        )
        merged = new if kept is None else pl.concat([kept, new])
        merged.unique(["date", "kind"], keep="last").sort("date", "kind").write_parquet(ev_path)
    except Exception as e:  # noqa: BLE001
        log.warning("events: kept cached file: %s", e)

    return {"vol": _rows(vol_path), "events": _rows(ev_path)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default="data_store", type=Path)
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print(collect_context(a.root, date.today()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
