from datetime import datetime
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
