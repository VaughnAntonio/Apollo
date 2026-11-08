from datetime import UTC, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

import pandas as pd
import polars as pl

from apollo.config import Symbol

Interval = Literal["1m", "5m", "15m", "1h", "1d"]

# How far back to request each interval: a day inside Yahoo's limit (7, 60, 730 days), because a
# start exactly on the limit is already too old when the request lands. None means full history.
MAX_LOOKBACK: dict[Interval, timedelta | None] = {
    "1m": timedelta(days=6),
    "5m": timedelta(days=59),
    "15m": timedelta(days=59),
    "1h": timedelta(days=729),
    "1d": None,
}

# `ts` is always the bar's open time in UTC. A bar is only known once it closes, at ts + interval
# (daily futures bars close at 17:00 ET; Yahoo's daily close is CME's ~16:00 ET settlement).
BAR_SCHEMA = {
    "ts": pl.Datetime("us", "UTC"),
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Int64,
    "symbol": pl.Utf8,
}


def normalise_yahoo(
    raw: pd.DataFrame,
    code: str,
    interval: Interval,
    kind: Literal["future", "stock"] = "future",
) -> pl.DataFrame:
    """Turn a yfinance history frame into BAR_SCHEMA with UTC open-time timestamps."""
    if raw.empty:
        return pl.DataFrame(schema=BAR_SCHEMA)
    idx = pd.DatetimeIndex(raw.index)
    if interval == "1d":
        # Yahoo labels a daily bar with its trading date D. Stamp it at its open: 18:00 ET on D-1
        # for futures (the Globex day), 09:30 ET on D for stocks.
        days = (idx.tz_localize(None) if idx.tz else idx).normalize()
        opens = days - pd.Timedelta(hours=6) if kind == "future" else days + pd.Timedelta(hours=9.5)
        idx = opens.tz_localize("America/New_York").tz_convert("UTC")
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


_DURATION = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
}


def drop_unfinished(
    df: pl.DataFrame,
    interval: Interval,
    now: datetime,
    kind: Literal["future", "stock"] = "future",
) -> pl.DataFrame:
    """Keep only bars that have closed by `now`.

    Daily bars are kept only for dates before today in New York, because Yahoo serves the
    session still trading as a partial bar. Weekend-dated futures bars are such partials.
    """
    if interval != "1d":
        return df.filter(pl.col("ts") + _DURATION[interval] <= now.astimezone(UTC))
    et = pl.col("ts").dt.convert_time_zone("America/New_York")
    label = (et + timedelta(hours=6) if kind == "future" else et).dt.date()
    today = now.astimezone(ZoneInfo("America/New_York")).date()
    keep = label < today
    if kind == "future":
        keep = keep & (label.dt.weekday() <= 5)
    return df.filter(keep)


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
    raw = yf.Ticker(sym.yahoo).history(**kwargs)
    df = normalise_yahoo(raw, sym.code, interval, sym.kind)
    return drop_unfinished(df, interval, datetime.now(UTC), sym.kind)
