"""Bars in the shape the web app reads, shared by the API and the snapshot."""

from datetime import datetime
from pathlib import Path
from typing import Literal

import polars as pl

from apollo.config import load_symbols
from apollo.data.resample import to_globex_daily
from apollo.data.store import read_bars
from apollo.data.yahoo import bar_close

Timeframe = Literal["1m", "5m", "15m", "1h", "4h", "1d"]
TIMEFRAMES: tuple[Timeframe, ...] = ("1m", "5m", "15m", "1h", "4h", "1d")


def read_tf(
    root: Path, code: str, tf: str, start: datetime | None = None, end: datetime | None = None
) -> pl.DataFrame:
    if tf == "4h":  # built from 1H; only finished 4H bars
        from apollo.fractal.model import complete_4h

        return complete_4h(read_bars(root, code, "1h", start, end))
    stored = read_bars(root, code, tf, start, end)  # type: ignore[arg-type]
    if (
        tf == "1d"
        and stored.is_empty()
        and load_symbols()[code].kind == "future"
        and read_bars(root, code, "1d").is_empty()  # none at all, not just none in this range
    ):
        # Yahoo keeps no daily history for some contracts (MCL=F): build them from 1H instead
        return to_globex_daily(read_bars(root, code, "1h", start, end))
    return stored


def bars_json(
    df: pl.DataFrame,
    tf: Timeframe | None = None,
    kind: Literal["future", "stock"] = "future",
) -> list[dict]:
    if tf is not None:
        df = df.with_columns(close_time=bar_close(tf, kind).dt.epoch("s"))
    return df.select(
        pl.col("ts").dt.epoch("s").alias("time"),
        "open",
        "high",
        "low",
        "close",
        "volume",
        *(["close_time"] if tf is not None else []),
    ).to_dicts()
