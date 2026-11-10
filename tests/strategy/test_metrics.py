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


def test_benchmark_curves_end_at_the_benchmark_totals(ohlc):
    from apollo.strategy.metrics import benchmark_curves

    closes = [100.0 + (i % 7) * 3 - i * 0.2 for i in range(120)]
    d1 = ohlc([(c, c + 1, c - 1, c) for c in closes], "2026-01-04 18:00", "1d")
    start, end = date(2026, 2, 1), date(2026, 4, 30)
    c = benchmark_curves(d1, start, end, MNQ)
    b = benchmarks(d1, start, end, MNQ)
    assert c["buy_hold"][-1]["usd"] == pytest.approx(b["buy_hold_$"])
    assert c["ma_20_50"][-1]["usd"] == pytest.approx(b["ma_20_50_$"])
    days = [p["date"] for p in c["buy_hold"]]
    assert days == sorted(days) and days[0] >= "2026-02-01" and days[-1] <= "2026-04-30"


def test_monthly_table_groups_closed_trades_by_session_month():
    from apollo.strategy.metrics import monthly_table

    t = pl.DataFrame(
        {
            "session": [date(2026, 1, 5), date(2026, 1, 20), date(2026, 2, 2), date(2026, 2, 3)],
            "r": [1.0, -1.0, 2.0, None],
            "net_$": [50.0, -40.0, 90.0, None],
            "skip": [None, None, None, "daily_cap"],
        },
        schema_overrides={"skip": pl.Utf8},
    )
    assert monthly_table(t) == [
        {"month": "2026-01", "n": 2, "r": 0.0, "net_$": 10.0},
        {"month": "2026-02", "n": 1, "r": 2.0, "net_$": 90.0},
    ]
