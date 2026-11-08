import pandas as pd

from mnq.data.yahoo import normalise_yahoo

OHLCV = {"Open": [1, 2], "High": [2, 3], "Low": [0, 1], "Close": [1.5, 2.5], "Volume": [10, 20]}


def test_intraday_tz_aware_converted_to_utc():
    idx = pd.DatetimeIndex(["2026-11-02 09:30", "2026-11-02 09:35"]).tz_localize("America/New_York")
    df = normalise_yahoo(pd.DataFrame(OHLCV, index=idx), "MNQ", "5m")
    assert str(df["ts"][0]) == "2026-11-02 14:30:00+00:00"
    assert df.columns == ["ts", "open", "high", "low", "close", "volume", "symbol"]


def test_daily_tz_naive_keeps_calendar_date():
    raw = pd.DataFrame(
        {"Open": [1.0], "High": [2.0], "Low": [0.5], "Close": [1.5], "Volume": [5]},
        index=pd.DatetimeIndex(["2026-11-02"]),
    )
    assert normalise_yahoo(raw, "MNQ", "1d")["ts"][0].date().isoformat() == "2026-11-02"


def test_daily_tz_aware_keeps_exchange_date():
    # yfinance often returns daily futures bars at midnight New York time.
    idx = pd.DatetimeIndex(["2026-11-02"]).tz_localize("America/New_York")
    raw = pd.DataFrame({k: v[:1] for k, v in OHLCV.items()}, index=idx)
    assert normalise_yahoo(raw, "MNQ", "1d")["ts"][0].date().isoformat() == "2026-11-02"


def test_empty_and_null_rows():
    assert normalise_yahoo(pd.DataFrame(), "NVDA", "1h").height == 0
    idx = pd.DatetimeIndex(["2026-11-02 09:30", "2026-11-02 09:35"]).tz_localize("UTC")
    raw = pd.DataFrame({**OHLCV, "Close": [1.5, None]}, index=idx)
    assert normalise_yahoo(raw, "MNQ", "5m").height == 1
