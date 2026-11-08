from mnq.data.resample import to_4h, to_rth_daily

ET = "America/New_York"


def test_4h_aggregates_and_anchors(bars):
    h = bars("2026-11-03 18:00", 8, "1h")  # Tuesday 18:00 ET to Wednesday 01:00 ET
    out = to_4h(h)
    assert out.height == 2 and out["bars_in"].to_list() == [4, 4]
    assert out["open"][0] == h["open"][0] and out["close"][0] == h["close"][3]
    assert out["high"][0] == h["high"][:4].max() and out["low"][0] == h["low"][:4].min()
    assert out["volume"][0] == h["volume"][:4].sum()


def test_4h_across_dst(bars):
    h = bars("2026-10-31 18:00", 30, "1h")  # crosses the 2026-11-01 fall-back
    starts = to_4h(h)["ts"].dt.convert_time_zone(ET).dt.hour()
    assert set(starts.to_list()) <= {18, 22, 2, 6, 10, 14}


def test_rth_daily_uses_only_session(bars):
    m = bars("2026-11-02 08:00", 12 * 10, "5m")  # 08:00 to 17:55 ET
    d = to_rth_daily(m)
    hhmm = m["ts"].dt.convert_time_zone(ET).dt.strftime("%H:%M")
    rth = m.filter((hhmm >= "09:30") & (hhmm < "16:00"))
    assert d.height == 1 and str(d["ny_date"][0]) == "2026-11-02"
    assert d["open"][0] == rth["open"][0] and d["close"][0] == rth["close"][-1]
    assert d["high"][0] == rth["high"].max()
