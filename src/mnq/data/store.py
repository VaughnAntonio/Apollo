from datetime import datetime
from pathlib import Path

import polars as pl

from mnq.data.yahoo import BAR_SCHEMA, Interval


def _dir(root: Path, code: str, interval: Interval) -> Path:
    return root / "bars" / code / interval


def append_bars(root: Path, df: pl.DataFrame, interval: Interval) -> int:
    """Merge bars into monthly Parquet files. A newer copy of a bar replaces the old one."""
    if df.is_empty():
        return 0
    df = df.select(BAR_SCHEMA.keys()).cast(BAR_SCHEMA)  # type: ignore[arg-type]
    for (code, month), part in df.group_by(
        "symbol", pl.col("ts").dt.strftime("%Y-%m").alias("month")
    ):
        path = _dir(root, str(code), interval) / f"{month}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            part = pl.concat([pl.read_parquet(path), part])
        part.unique("ts", keep="last", maintain_order=True).sort("ts").write_parquet(
            path, compression="zstd"
        )
    return df.height


def read_bars(
    root: Path,
    code: str,
    interval: Interval,
    start: datetime | None = None,
    end: datetime | None = None,
) -> pl.DataFrame:
    """Read all stored months for one symbol and interval, optionally clipped to [start, end)."""
    files = sorted(_dir(root, code, interval).glob("*.parquet"))
    if not files:
        return pl.DataFrame(schema=BAR_SCHEMA)
    lf = pl.scan_parquet(files)
    if start is not None:
        lf = lf.filter(pl.col("ts") >= start)
    if end is not None:
        lf = lf.filter(pl.col("ts") < end)
    return lf.sort("ts").collect()
