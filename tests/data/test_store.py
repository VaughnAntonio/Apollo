from mnq.data.store import append_bars, read_bars


def test_month_split_and_idempotent(tmp_path, bars):
    df = bars("2026-10-30 09:30", 6 * 24 * 4, "1h")  # crosses into November
    assert append_bars(tmp_path, df, "1h") == df.height
    append_bars(tmp_path, df, "1h")
    files = sorted(p.name for p in (tmp_path / "bars" / "MNQ" / "1h").iterdir())
    assert files == ["2026-10.parquet", "2026-11.parquet"]
    assert read_bars(tmp_path, "MNQ", "1h").height == df.height


def test_later_revision_wins(tmp_path, bars):
    df = bars("2026-11-02 09:30", 3, "5m")
    append_bars(tmp_path, df, "5m")
    append_bars(tmp_path, df.with_columns(close=df["close"] + 1), "5m")
    assert read_bars(tmp_path, "MNQ", "5m")["close"].to_list() == (df["close"] + 1).to_list()


def test_read_missing_symbol_is_empty(tmp_path):
    assert read_bars(tmp_path, "NVDA", "1d").height == 0
