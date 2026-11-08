from apollo.data.yahoo import bar_close


def test_daily_future_closes_23h_later(bars):
    d = bars("2026-11-01 18:00", 1, "1d").with_columns(c=bar_close("1d"))
    assert str(d["c"][0]) == "2026-11-02 22:00:00+00:00"  # Monday 17:00 EST


def test_4h_last_bucket_is_3h(bars):
    h = bars("2026-11-02 14:00", 1, "1h").with_columns(c=bar_close("4h"))
    assert str(h["c"][0]) == "2026-11-02 22:00:00+00:00"  # 17:00 EST, not 18:00


def test_intraday_and_stock_daily(bars):
    m = bars("2026-11-02 09:30", 1, "5m").with_columns(c=bar_close("5m"))
    assert str(m["c"][0]) == "2026-11-02 14:35:00+00:00"
    s = bars("2026-11-02 09:30", 1, "1d").with_columns(c=bar_close("1d", "stock"))
    assert str(s["c"][0]) == "2026-11-02 21:00:00+00:00"  # 16:00 EST
