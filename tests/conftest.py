from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import polars as pl
import pytest

STEPS = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "1d": 1440}


@pytest.fixture
def bars():
    """Synthetic bars: n rows `every` apart from local `start`, close = 100, 101, ..."""

    def make(start: str, n: int, every: str, tz: str = "America/New_York", symbol: str = "MNQ"):
        t0 = datetime.fromisoformat(start).replace(tzinfo=ZoneInfo(tz)).astimezone(ZoneInfo("UTC"))
        step = timedelta(minutes=STEPS[every])
        close = [100.0 + i for i in range(n)]
        return pl.DataFrame(
            {
                "ts": [t0 + i * step for i in range(n)],
                "open": [c - 0.5 for c in close],
                "high": [c + 1 for c in close],
                "low": [c - 1 for c in close],
                "close": close,
                "volume": list(range(1, n + 1)),
                "symbol": [symbol] * n,
            },
            schema_overrides={"ts": pl.Datetime("us", "UTC"), "volume": pl.Int64},
        )

    return make
