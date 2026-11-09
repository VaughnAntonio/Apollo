import pytest

from apollo.config import load_symbols
from apollo.models.sessions import build_sessions

MNQ = load_symbols()["MNQ"]


def test_trend_up_session(ohlc):
    rows = [
        (100, 101, 99.5, 100.8),
        (100.8, 102, 100.5, 101.9),
        (101.9, 103, 101.8, 102.9),
        (102.9, 104, 102.5, 103.8),
        (103.8, 105, 103.6, 104.9),
        (104.9, 106, 104.5, 105.8),
        (105.8, 107, 105.6, 106.9),
    ]
    s = build_sessions(ohlc(rows, "2026-11-03 09:00", "1h"), MNQ).row(0, named=True)
    assert (s["open"], s["high"], s["low"], s["close"]) == (100.0, 107.0, 99.5, 106.9)
    assert s["label"] == "trend_up" and s["up_exc"] == 7.0 and s["down_exc"] == 0.5
    assert str(s["forecast_at"]) == "2026-11-03 14:00:00+00:00" and s["bars"] == 7


@pytest.mark.parametrize(
    ("o", "c", "h", "lo", "label"),
    [
        (100, 100.4, 101, 99, "chop"),  # body 0.4 / range 2 = 0.2
        (100, 98.4, 100.2, 98.2, "trend_down"),  # body 1.6 / range 2 = 0.8
        (100, 100.9, 101, 99, "normal"),  # body 0.9 / range 2 = 0.45
    ],
)
def test_label_thresholds(ohlc, o, c, h, lo, label):
    # Seven bars: the first opens at o, one touches h, one touches lo, the last closes at c.
    rows = [(o, o, o, o), (o, h, o, o), (o, o, lo, o), (o, o, o, o), (o, o, o, o), (o, o, o, o)]
    rows += [(o, max(o, c), min(o, c), c)]
    s = build_sessions(ohlc(rows, "2026-11-04 09:00", "1h"), MNQ)
    assert s["label"][0] == label


def test_short_session_unlabelled(ohlc):
    s = build_sessions(ohlc([(100, 101, 99, 100.5)] * 4, "2026-11-27 09:00", "1h"), MNQ)
    assert s["bars"][0] == 4 and s["label"][0] is None


def test_forecast_time_is_nine_even_without_the_nine_bar(ohlc):
    s = build_sessions(ohlc([(100, 101, 99, 100.5)] * 3, "2026-11-27 10:00", "1h"), MNQ)
    assert str(s["forecast_at"][0]) == "2026-11-27 14:00:00+00:00"


def test_overnight_bars_ignored(ohlc):
    rows = [(90, 120, 80, 95)] * 3 + [(100, 101, 99.5, 100.8)] * 7  # 06:00-08:00 then 09:00-15:00
    s = build_sessions(ohlc(rows, "2026-11-03 06:00", "1h"), MNQ)
    assert s.height == 1 and s["high"][0] == 101.0 and s["open"][0] == 100.0
