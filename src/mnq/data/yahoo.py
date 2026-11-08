from datetime import UTC, datetime, timedelta
from typing import Literal

import pandas as pd
import polars as pl

from mnq.config import Symbol

Interval = Literal["1m", "5m", "15m", "1h", "1d"]

# How far back Yahoo serves each interval. None means full history.
MAX_LOOKBACK: dict[Interval, timedelta | None] = {
    "1m": timedelta(days=7),
    "5m": timedelta(days=60),
    "15m": timedelta(days=60),
    "1h": timedelta(days=729),
    "1d": None,
}

BAR_SCHEMA = {
    "ts": pl.Datetime("us", "UTC"),
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Int64,
    "symbol": pl.Utf8,
}


def normalise_yahoo(raw: pd.DataFrame, code: str, interval: Interval) -> pl.DataFrame:
    """Turn a yfinance history frame into BAR_SCHEMA with UTC timestamps."""
    if raw.empty:
        return pl.DataFrame(schema=BAR_SCHEMA)
    idx = pd.DatetimeIndex(raw.index)
    if interval == "1d":
        # A daily bar is a calendar date: keep the exchange's date, stamp it 00:00 UTC.
        idx = (idx.tz_localize(None) if idx.tz else idx).normalize().tz_localize("UTC")
    else:
        idx = idx.tz_convert("UTC") if idx.tz else idx.tz_localize("UTC")
    df = pl.DataFrame(
        {
            "ts": pl.from_pandas(pd.Series(idx)),
            "open": raw["Open"].to_numpy(dtype=float),
            "high": raw["High"].to_numpy(dtype=float),
            "low": raw["Low"].to_numpy(dtype=float),
            "close": raw["Close"].to_numpy(dtype=float),
            "volume": raw["Volume"].fillna(0).to_numpy(dtype="int64"),
            "symbol": [code] * len(raw),
        },
        schema=BAR_SCHEMA,
    )
    return df.drop_nans(["open", "high", "low", "close"]).sort("ts")


def fetch_bars(sym: Symbol, interval: Interval, start: datetime | None = None) -> pl.DataFrame:
    """Download bars from Yahoo, starting at the oldest bar Yahoo keeps unless `start` is given."""
    import yfinance as yf

    lookback = MAX_LOOKBACK[interval]
    kwargs: dict = {"interval": interval, "auto_adjust": False}
    if start is not None:
        kwargs["start"] = start
    elif lookback is None:
        kwargs["period"] = "max"
    else:
        kwargs["start"] = datetime.now(UTC) - lookback
    return normalise_yahoo(yf.Ticker(sym.yahoo).history(**kwargs), sym.code, interval)
