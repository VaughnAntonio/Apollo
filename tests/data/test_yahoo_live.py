import pytest

from mnq.config import load_symbols
from mnq.data.yahoo import BAR_SCHEMA, fetch_bars


@pytest.mark.network
def test_fetch_mnq_daily_full_history():
    df = fetch_bars(load_symbols()["MNQ"], "1d")
    assert df.height > 1500
    assert dict(df.schema) == BAR_SCHEMA
