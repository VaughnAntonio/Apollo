import polars as pl

from apollo.data.sessions import add_session_columns

_OHLCV = [
    pl.col("open").first(),
    pl.col("high").max(),
    pl.col("low").min(),
    pl.col("close").last(),
    pl.col("volume").sum(),
    pl.col("symbol").first(),
]


def to_4h(df_1h: pl.DataFrame) -> pl.DataFrame:
    """Build 4H bars from 1H bars, anchored to the 18:00 ET Globex open.

    Buckets start at 18, 22, 02, 06, 10 and 14 ET, so none spans the 17:00 to 18:00 break.
    """
    s = add_session_columns(df_1h.sort("ts"))
    bucket = ((s["ts_et"].dt.hour().cast(pl.Int32) - 18) % 24) // 4
    return (
        s.with_columns(bucket=bucket)
        .group_by("symbol", "globex_date", "bucket", maintain_order=True)
        .agg(pl.col("ts").first(), *_OHLCV[:-1], pl.len().cast(pl.Int32).alias("bars_in"))
        .select("ts", "open", "high", "low", "close", "volume", "symbol", "bars_in")
        .sort("ts")
    )


def to_rth_daily(df_intraday: pl.DataFrame) -> pl.DataFrame:
    """One row per New York regular session (09:30 to 16:00 ET)."""
    s = add_session_columns(df_intraday.sort("ts")).filter(pl.col("is_rth"))
    return s.group_by("ny_date", maintain_order=True).agg(*_OHLCV).sort("ny_date")
