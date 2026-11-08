import pytest

from mnq.config import load_symbols
from mnq.data.yahoo import BAR_SCHEMA, fetch_bars


@pytest.mark.network
def test_fetch_mnq_daily_full_history():
    df = fetch_bars(load_symbols()["MNQ"], "1d")
    assert df.height > 1500
    assert dict(df.schema) == BAR_SCHEMA


@pytest.mark.network
def test_fetch_mnq_5m_returns_recent_bars():
    assert fetch_bars(load_symbols()["MNQ"], "5m").height > 1000
