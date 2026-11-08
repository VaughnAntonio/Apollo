import polars as pl

from apollo.config import load_symbols
from apollo.data.collect import collect, main


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
