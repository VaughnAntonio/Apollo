"""Bars in the shape the web app reads, shared by the API and the snapshot."""

from datetime import datetime
from pathlib import Path

import polars as pl

from apollo.data.store import read_bars

TIMEFRAMES = ("1m", "5m", "15m", "1h", "4h", "1d")


def read_tf(
    root: Path, code: str, tf: str, start: datetime | None = None, end: datetime | None = None
) -> pl.DataFrame:
    if tf == "4h":  # built from 1H; only finished 4H bars
        from apollo.fractal.model import complete_4h

        return complete_4h(read_bars(root, code, "1h", start, end))
    return read_bars(root, code, tf, start, end)  # type: ignore[arg-type]


def bars_json(df: pl.DataFrame) -> list[dict]:
    return [
        {"time": int(t.timestamp()), "open": o, "high": h, "low": lo, "close": c, "volume": v}
        for t, o, h, lo, c, v in df.select(
            "ts", "open", "high", "low", "close", "volume"
        ).iter_rows()
    ]
