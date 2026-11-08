from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from apollo.data.sessions import add_session_columns
from apollo.data.yahoo import MAX_LOOKBACK, drop_unfinished, normalise_yahoo

OHLCV = {"Open": [1, 2], "High": [2, 3], "Low": [0, 1], "Close": [1.5, 2.5], "Volume": [10, 20]}


def test_intraday_tz_aware_converted_to_utc():
    idx = pd.DatetimeIndex(["2026-11-02 09:30", "2026-11-02 09:35"]).tz_localize("America/New_York")
    df = normalise_yahoo(pd.DataFrame(OHLCV, index=idx), "MNQ", "5m")
    assert str(df["ts"][0]) == "2026-11-02 14:30:00+00:00"
    assert df.columns == ["ts", "open", "high", "low", "close", "volume", "symbol"]


def test_daily_tz_naive_stamped_at_globex_open():
    # ts is the bar's open time: day D of a future opens 18:00 ET on D-1, so nothing leaks early.
    raw = pd.DataFrame(
        {"Open": [1.0], "High": [2.0], "Low": [0.5], "Close": [1.5], "Volume": [5]},
        index=pd.DatetimeIndex(["2026-11-02"]),
    )
    df = normalise_yahoo(raw, "MNQ", "1d")
    assert str(df["ts"][0]) == "2026-11-01 23:00:00+00:00"  # 18:00 EST on Sunday
    assert str(add_session_columns(df)["globex_date"][0]) == "2026-11-02"


def test_daily_tz_aware_keeps_exchange_date():
    # yfinance often returns daily futures bars at midnight New York time.
    idx = pd.DatetimeIndex(["2026-11-03"]).tz_localize("America/New_York")
    raw = pd.DataFrame({k: v[:1] for k, v in OHLCV.items()}, index=idx)
    df = normalise_yahoo(raw, "MNQ", "1d")
    assert str(add_session_columns(df)["globex_date"][0]) == "2026-11-03"


def test_daily_stock_stamped_at_rth_open():
    raw = pd.DataFrame(
        {"Open": [1.0], "High": [2.0], "Low": [0.5], "Close": [1.5], "Volume": [5]},
        index=pd.DatetimeIndex(["2026-11-02"]),
    )
    assert (
        str(normalise_yahoo(raw, "NVDA", "1d", kind="stock")["ts"][0])
        == "2026-11-02 14:30:00+00:00"
    )


def test_lookback_inside_yahoo_limits():
    # Yahoo rejects a start that is already past its limit when the request lands.
    assert MAX_LOOKBACK["5m"] == MAX_LOOKBACK["15m"] == timedelta(days=59)
    one_min, one_hour = MAX_LOOKBACK["1m"], MAX_LOOKBACK["1h"]
    assert one_min is not None and one_min < timedelta(days=7)
    assert one_hour is not None and one_hour < timedelta(days=730)


def test_empty_and_null_rows():
    assert normalise_yahoo(pd.DataFrame(), "NVDA", "1h").height == 0
    idx = pd.DatetimeIndex(["2026-11-02 09:30", "2026-11-02 09:35"]).tz_localize("UTC")
    raw = pd.DataFrame({**OHLCV, "Close": [1.5, None]}, index=idx)
    assert normalise_yahoo(raw, "MNQ", "5m").height == 1


def test_unfinished_bars_dropped(bars):
    # Yahoo serves the bar that is still trading; storing it would freeze a partial bar.
    now = datetime(2026, 11, 3, 9, 42, tzinfo=ZoneInfo("America/New_York"))
    m = bars("2026-11-03 09:30", 3, "5m")  # 09:30, 09:35 closed; 09:40 still open
    assert drop_unfinished(m, "5m", now).height == 2
    d = bars("2026-11-01 18:00", 2, "1d")  # Globex days dated Mon 2 and Tue 3 November
    assert drop_unfinished(d, "1d", now).height == 1


def test_daily_futures_weekend_label_dropped(bars):
    # Yahoo labels the session that opens Sunday 18:00 ET with Sunday's date while it trades.
    now = datetime(2026, 11, 10, 12, 0, tzinfo=ZoneInfo("America/New_York"))
    d = bars("2026-11-07 18:00", 1, "1d")  # dated Sunday 8 November
    assert drop_unfinished(d, "1d", now).height == 0
