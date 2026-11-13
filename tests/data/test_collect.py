import polars as pl

from apollo.config import load_symbols
from apollo.data.collect import collect, main
from apollo.data.store import read_bars


def _two():
    return {k: v for k, v in load_symbols().items() if k in ("MNQ", "NVDA")}


def test_collect_writes_and_reports(tmp_path, bars):
    res = collect(
        tmp_path,
        _two(),
        ["5m"],
        fetch=lambda s, i: bars("2026-11-03 09:30", 5, "5m", symbol=s.code),
    )
    assert res == {"MNQ/5m": 5, "NVDA/5m": 5}
    assert any((tmp_path / "quality").rglob("MNQ_5m.json"))
    assert (tmp_path / "bars" / "NVDA" / "5m" / "2026-11.parquet").exists()


def test_one_failure_does_not_stop_others(tmp_path, bars):
    def fetch(s, i):
        if s.code == "NVDA":
            raise RuntimeError("rate limited")
        return bars("2026-11-03 09:30", 5, "5m")

    assert collect(tmp_path, _two(), ["5m"], fetch=fetch) == {"MNQ/5m": 5, "NVDA/5m": 0}


def test_main_exit_code_when_all_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("apollo.data.collect.fetch_bars", lambda s, i: pl.DataFrame())
    assert main(["--root", str(tmp_path), "--symbols", "MNQ", "--intervals", "1d"]) == 1


def test_store_failure_does_not_stop_others(tmp_path, bars, monkeypatch):
    import apollo.data.collect as c

    real = c.append_bars

    def flaky(root, df, interval):
        if df["symbol"][0] == "NVDA":
            raise OSError("corrupt parquet")
        return real(root, df, interval)

    monkeypatch.setattr(c, "append_bars", flaky)
    res = collect(
        tmp_path,
        _two(),
        ["5m"],
        fetch=lambda s, i: bars("2026-11-03 09:30", 5, "5m", symbol=s.code),
    )
    assert res == {"MNQ/5m": 5, "NVDA/5m": 0}


def test_a_late_run_keeps_the_real_futures_daily_bar(tmp_path, bars):
    # The nightly job often starts after 18:00 ET. By then Yahoo files the new session's first
    # hours under today's date, replacing the finished day. The day is rebuilt from 1H instead.
    hourly = pl.concat(
        [
            bars("2026-11-11 18:00", 23, "1h"),  # the whole Nov 12 session, 18:00 to 17:00 ET
            bars("2026-11-12 18:00", 4, "1h"),  # the first hours of the next one
        ]
    )
    wrong = bars("2026-11-11 18:00", 1, "1d").with_columns(open=pl.lit(5000.0), volume=pl.lit(999))

    def fetch(s, i):
        return hourly if i == "1h" else wrong

    syms = {"MNQ": load_symbols()["MNQ"]}
    collect(tmp_path, syms, ["1d", "1h"], fetch=fetch)
    day = read_bars(tmp_path, "MNQ", "1d")
    assert day.height == 1  # the unfinished next session is not a daily bar yet
    assert day["open"][0] == 99.5  # the first hourly open
    assert day["volume"][0] == sum(range(1, 24))  # all 23 hours, not Yahoo's partial count


def test_the_rebuild_never_replaces_a_day_with_part_of_its_hours(tmp_path, bars):
    # Only the last three hours of the Nov 11 session are stored: that day stays as Yahoo sent it.
    hourly = pl.concat([bars("2026-11-11 14:00", 3, "1h"), bars("2026-11-11 18:00", 23, "1h")])
    yahoo = pl.concat([bars("2026-11-10 18:00", 1, "1d"), bars("2026-11-11 18:00", 1, "1d")])
    yahoo = yahoo.with_columns(volume=pl.lit(10_000))

    def fetch(s, i):
        return hourly if i == "1h" else yahoo

    collect(tmp_path, {"MNQ": load_symbols()["MNQ"]}, ["1d", "1h"], fetch=fetch)
    assert read_bars(tmp_path, "MNQ", "1d")["volume"].to_list() == [10_000, sum(range(1, 24))]
