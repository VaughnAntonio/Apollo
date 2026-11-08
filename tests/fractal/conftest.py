from datetime import datetime
from itertools import pairwise
from zoneinfo import ZoneInfo

import pytest

from apollo.fractal.candles import Setup

NY = ZoneInfo("America/New_York")
END = datetime(2026, 11, 3, 11, 30, tzinfo=NY)  # C3 closes


@pytest.fixture
def bull_setup():
    return Setup(
        direction="bull",
        c1_idx=0,
        c2_idx=1,
        c2_ts=datetime(2026, 11, 3, 9, 30, tzinfo=NY),
        c2_close=datetime(2026, 11, 3, 10, 30, tzinfo=NY),
        c1_high=102.0,
        c1_low=100.0,
        c2_high=101.5,
        c2_low=98.8,
        eq=99.0,
        poi_kind="swing",
        poi_level=99.5,
        c3_closed=None,
    )


def _split(o: float, h: float, lo: float, c: float) -> list[tuple[float, float, float, float]]:
    """Twelve 5m bars for one 1h bar: six down-closes to the low, six up-closes to the close."""
    path = [o + (lo - o) * k / 6 for k in range(7)] + [lo + (c - lo) * k / 6 for k in range(1, 7)]
    bars = [(a, max(a, b), min(a, b), b) for a, b in pairwise(path)]
    first = bars[0]
    bars[0] = (first[0], max(first[1], h), first[2], first[3])
    return bars


@pytest.fixture
def ohlc_long(ohlc):
    """30 1h bars with two bullish setups (C2 at rows 4 and 19) and matching 5m bars."""
    base = [(100, 101, 98, 99), (99, 99.5, 95, 97), (97, 100, 96, 99.5), (99.5, 100, 96.5, 97.5)]
    pattern = base + [(97.5, 99, 94.5, 98.5), (98.5, 102, 98, 101)]
    filler = [(101, 101.5, 100.5, 101)] * 9

    def up(rows, d):
        return [tuple(x + d for x in r) for r in rows]

    rows = pattern + filler + up(pattern, 10) + up(filler, 10)
    htf = ohlc(rows, "2026-11-03 01:00", "1h")
    ltf_rows = [b for r in rows for b in _split(*r)]
    return htf, ohlc(ltf_rows, "2026-11-03 01:00", "5m")
