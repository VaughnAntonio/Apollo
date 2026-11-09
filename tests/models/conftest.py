from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl
import pytest

from apollo.config import load_symbols
from apollo.data.quality import _is_open
from apollo.data.sessions import add_session_columns
from apollo.models.sessions import build_sessions

NY = ZoneInfo("America/New_York")
MNQ = load_symbols()["MNQ"]


def _weekdays(start: date, n: int) -> list[date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


DATES_300 = _weekdays(date(2025, 1, 1), 300)
DATES_1000 = _weekdays(date(2022, 1, 3), 1000)


@pytest.fixture
def synthetic_frames():
    """60 days of 1H Globex bars from a seeded random walk, daily bars built from them,
    the session table, and the MNQ symbol."""
    rng = np.random.default_rng(7)
    t0 = datetime(2026, 1, 4, 18, tzinfo=NY)
    stamps = [t for t in (t0 + timedelta(hours=i) for i in range(60 * 24)) if _is_open(t, "future")]
    steps = rng.normal(0, 0.001, len(stamps))
    close = 20000 * np.exp(np.cumsum(steps))
    opn = np.concatenate([[20000.0], close[:-1]])
    wiggle = np.abs(rng.normal(0, 0.0005, len(stamps))) * close
    h1 = pl.DataFrame(
        {
            "ts": [t.astimezone(ZoneInfo("UTC")) for t in stamps],
            "open": opn,
            "high": np.maximum(opn, close) + wiggle,
            "low": np.minimum(opn, close) - wiggle,
            "close": close,
            "volume": [1] * len(stamps),
            "symbol": ["MNQ"] * len(stamps),
        },
        schema_overrides={"ts": pl.Datetime("us", "UTC"), "volume": pl.Int64},
    )
    d1 = (
        add_session_columns(h1)
        .group_by("globex_date", maintain_order=True)
        .agg(
            pl.col("ts").first(),
            pl.col("open").first(),
            pl.col("high").max(),
            pl.col("low").min(),
            pl.col("close").last(),
            pl.col("volume").sum(),
            pl.col("symbol").first(),
        )
        .drop("globex_date")
    )
    return build_sessions(h1, MNQ), h1, d1, MNQ
