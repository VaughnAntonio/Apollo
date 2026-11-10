from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from apollo.data.serve import read_tf
from apollo.data.store import append_bars

ET = ZoneInfo("America/New_York")


def test_a_future_without_daily_bars_gets_them_from_its_hourly_bars(tmp_path, bars):
    # Yahoo keeps no daily history for MCL=F, so its D chart would be empty
    h = bars("2026-11-02 18:00", 46, "1h", symbol="MCL")  # Mon 18:00 to Wed 15:00 ET
    append_bars(tmp_path, h, "1h")
    d = read_tf(tmp_path, "MCL", "1d")
    assert d.height == 1  # Wednesday's session hasn't closed yet
    row = d.row(0, named=True)
    assert row["ts"].astimezone(ET) == datetime(2026, 11, 2, 18, tzinfo=ET)  # the Globex open
    tue = h.filter(h["ts"] < datetime(2026, 11, 3, 18, tzinfo=ET).astimezone(UTC))
    assert (row["open"], row["close"]) == (tue["open"][0], tue["close"][-1])
    assert (row["high"], row["low"]) == (tue["high"].max(), tue["low"].min())


def test_stored_daily_bars_are_used_as_they_are(tmp_path, bars):
    append_bars(tmp_path, bars("2026-11-02 18:00", 46, "1h"), "1h")
    stored = bars("2026-10-26 18:00", 3, "1d")
    append_bars(tmp_path, stored, "1d")
    assert read_tf(tmp_path, "MNQ", "1d")["close"].to_list() == stored["close"].to_list()


def test_a_symbol_with_daily_bars_never_mixes_in_hourly_ones(tmp_path, bars):
    # the chart asks for bars after the last one it has; "nothing new" must stay empty
    append_bars(tmp_path, bars("2026-11-02 18:00", 46, "1h"), "1h")
    append_bars(tmp_path, bars("2026-10-26 18:00", 3, "1d"), "1d")
    after = datetime(2026, 11, 1, 4, tzinfo=UTC)
    assert read_tf(tmp_path, "MNQ", "1d", start=after).is_empty()
