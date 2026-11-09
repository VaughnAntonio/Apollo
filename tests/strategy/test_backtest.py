import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from apollo.strategy.backtest import check_lock, holdout_start, log_backtest, run_backtest
from apollo.strategy.config import load_trade_config

NY = ZoneInfo("America/New_York")
CFG = load_trade_config()
TS = pl.Datetime("us", "UTC")


def weekdays(start: date, end: date) -> list[date]:
    return [
        start + timedelta(days=i)
        for i in range((end - start).days + 1)
        if (start + timedelta(days=i)).weekday() < 5
    ]


def test_holdout_start():
    days = weekdays(date(2026, 1, 5), date(2026, 11, 6))
    assert holdout_start(days, 3) == date(2026, 8, 6)  # first session on or after 3 months back


def _frames(ohlc, days=(date(2026, 6, 2), date(2026, 10, 6))):
    """Two identical winning setups: one in June (development), one in October (holdout)."""

    def setup(day):
        sig = datetime(2026, day.month, day.day, 10, tzinfo=NY)
        return {
            "c2_ts": sig - timedelta(hours=16),
            "direction": "bull",
            "c1_high": 106.0,
            "c1_low": 90.0,
            "after_c2_cisd_ts": sig,
            "after_c2_protected": 100.0,
        }

    setups = pl.DataFrame(
        [setup(d) for d in days], schema_overrides={"c2_ts": TS, "after_c2_cisd_ts": TS}
    )
    rows = [
        (101, 101.5, 100.5, 101),
        (101, 102, 100.2, 101.8),
        (102, 103, 101.5, 102.5),
        (102.5, 105.5, 102, 105),
    ]
    bars = pl.concat([ohlc(rows, f"{d.isoformat()} 09:00", "1h") for d in days])
    sessions = weekdays(date(2026, 1, 5), date(2026, 11, 6))
    return setups, bars, sessions


def test_non_final_run_never_sees_holdout(ohlc):
    setups, bars, sessions = _frames(ohlc)
    res = run_backtest(
        Path("unused"),
        "MNQ",
        "D-1H",
        "plain",
        CFG,
        setups=setups,
        bars=bars,
        forecasts=pl.DataFrame(),
        d1=None,
        sessions=sessions + weekdays(date(2026, 11, 9), date(2027, 3, 1)),  # more data arrived
    )
    assert res["n_setups"] == 1 and res["expectancy"]["n"] == 1
    assert (
        res["period"]["end"] < CFG.holdout_from and res["holdout_from"] == CFG.holdout_from
    )  # more data: same cut
    final = run_backtest(
        Path("unused"),
        "MNQ",
        "D-1H",
        "plain",
        CFG,
        final=True,
        setups=setups,
        bars=bars,
        forecasts=pl.DataFrame(),
        d1=None,
        sessions=sessions,
    )
    assert final["n_setups"] == 1 and final["period"]["start"] >= CFG.holdout_from
    assert sum(res["skip_counts"].values()) == res["n_setups"]


def test_final_lock_refuses_changed_config_or_code(tmp_path):
    lock = tmp_path / "holdout.lock"
    hold = date(2026, 8, 6)
    first = check_lock(lock, "aaa", ["plain"], commit="c1", dirty=False, holdout_from=hold)
    saved = json.loads(lock.read_text())
    assert saved["commit"] == "c1" and saved["holdout_from"] == "2026-08-06"
    assert saved["lock_hash"] == first
    # the same config and code may re-run (it's logged as a new attempt)
    assert check_lock(lock, "aaa", ["plain"], commit="c1", dirty=False, holdout_from=hold) == first
    with pytest.raises(SystemExit):
        check_lock(lock, "aaa", ["plain"], commit="c2", dirty=False, holdout_from=hold)
    with pytest.raises(SystemExit):
        check_lock(lock, "bbb", ["plain"], commit="c1", dirty=False, holdout_from=hold)


def test_dirty_tree_refused_before_any_lock(tmp_path):
    with pytest.raises(SystemExit):
        check_lock(
            tmp_path / "holdout.lock",
            "aaa",
            ["plain"],
            commit="c1",
            dirty=True,
            holdout_from=date(2026, 8, 6),
        )
    assert not (tmp_path / "holdout.lock").exists()


def test_holdout_date_is_pinned_in_config():
    assert CFG.holdout_from == date(2026, 8, 6)


def test_backtests_log_appends_per_variant(tmp_path):
    p = tmp_path / "backtests.csv"
    res = {
        "code": "MNQ",
        "layer": "D-1H",
        "variant": "plain",
        "config_hash": "x",
        "final": False,
        "expectancy": {"n": 3, "mean": 0.2, "low": -0.5, "high": 0.9, "win_rate": 0.6},
        "equity": {"max_dd_r": -1.5},
        "monte_carlo": {"1%": {"p_pass": 0.4}},
    }
    assert log_backtest(p, res) == 1 and log_backtest(p, res | {"variant": "both"}) == 2
    assert pl.read_csv(p)["variant"].to_list() == ["plain", "both"]


@pytest.mark.skipif(not Path("data_store/context/vol.parquet").exists(), reason="no local data")
def test_real_mnq_plain_smoke():
    res = run_backtest(Path("data_store"), "MNQ", "D-1H", "plain", CFG)
    assert res["expectancy"]["n"] > 0 and sum(res["skip_counts"].values()) == res["n_setups"]
    assert res["period"]["start"] >= date(2024, 11, 11) and res["setups_before_data"] > 0


@pytest.mark.skipif(not Path("data_store/context/vol.parquet").exists(), reason="no local data")
def test_one_holdout_date_for_every_layer():
    a = run_backtest(Path("data_store"), "MNQ", "D-1H", "plain", CFG)
    b = run_backtest(Path("data_store"), "MNQ", "1H-5m", "plain", CFG)
    assert a["holdout_from"] == b["holdout_from"]


def test_strategy_stats_ignore_the_account_breach(ohlc):
    from dataclasses import replace

    setups, bars, sessions = _frames(ohlc, days=(date(2026, 6, 2), date(2026, 6, 9)))
    tiny = replace(CFG, account=replace(CFG.account, drawdown=1.0))  # breaches on the first dip
    res = run_backtest(
        Path("unused"),
        "MNQ",
        "D-1H",
        "plain",
        tiny,
        setups=setups,
        bars=bars,
        forecasts=pl.DataFrame(),
        d1=None,
        sessions=sessions,
    )
    assert res["expectancy"]["n"] == 2  # the strategy's own record keeps both trades
    assert res["account"]["breached_at"] is not None and res["account"]["trades"] == 1
