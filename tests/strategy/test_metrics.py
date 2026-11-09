from datetime import date

import numpy as np
import polars as pl
import pytest

from apollo.config import load_symbols
from apollo.strategy.config import Account
from apollo.strategy.metrics import benchmarks, equity_stats, expectancy_ci, prop_monte_carlo

MNQ = load_symbols()["MNQ"]
ACC = Account("x", 50_000, 2_500, 100, 3_000)


def test_ci_contains_mean_and_shrinks_with_n():
    rng = np.random.default_rng(1)
    small, big = expectancy_ci(rng.normal(0.3, 2, 20)), expectancy_ci(rng.normal(0.3, 2, 2000))
    for ci in (small, big):
        assert ci["low"] <= ci["mean"] <= ci["high"]
    assert (big["high"] - big["low"]) < (small["high"] - small["low"]) / 5
    assert expectancy_ci(np.array([]))["n"] == 0


def test_monte_carlo_extremes():
    assert (
        prop_monte_carlo(np.full(50, 1.0), ACC, 0.01)["p_pass"] == 1.0
    )  # +500 a trade: passes in 6
    assert prop_monte_carlo(np.full(50, 1.0), ACC, 0.01)["median_trades_to_pass"] == 6
    assert prop_monte_carlo(np.full(50, -1.0), ACC, 0.01)["p_breach"] == 1.0


def test_two_pct_breaches_more_often():
    r = np.array([2.0, -1.0, -1.0, 1.5, -1.0, 3.0, -1.0])
    one, two = prop_monte_carlo(r, ACC, 0.01), prop_monte_carlo(r, ACC, 0.02)
    assert two["p_breach"] > one["p_breach"]


def test_equity_stats():
    t = pl.DataFrame(
        {
            "session": [date(2026, 1, 5), date(2026, 1, 6), date(2026, 2, 5)],
            "net_$": [300.0, -500.0, 100.0],
            "r": [0.6, -1.0, 0.2],
            "skip": [None, None, None],
        },
        schema_overrides={"skip": pl.Utf8},
    )
    s = equity_stats(t)
    assert s["net_$"] == -100.0 and s["max_dd_$"] == -500.0 and s["max_dd_r"] == pytest.approx(-1.0)
    assert s["profit_factor"] == pytest.approx(400 / 500)


def test_ma_rule_uses_yesterdays_signal(ohlc):
    # 50 flat days, then a jump: the 20-day average crosses the 50-day on the jump day's close,
    # so the rule is long from the next day only and never earns the jump itself.
    closes = [100.0] * 50 + [200.0, 210.0] + [210.0] * 5
    d1 = ohlc([(c, c, c, c) for c in closes], "2026-01-04 18:00", "1d")
    b = benchmarks(d1, date(2026, 1, 1), date(2026, 12, 31), MNQ)
    assert b["buy_hold_$"] == pytest.approx(110 * 2) and b["ma_20_50_$"] == pytest.approx(10 * 2)
