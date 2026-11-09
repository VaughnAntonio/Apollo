from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from apollo.config import load_symbols
from apollo.strategy.candidates import SCHEMA
from apollo.strategy.config import load_trade_config
from apollo.strategy.simulate import simulate

NY = ZoneInfo("America/New_York")
MNQ = load_symbols()["MNQ"]
CFG = load_trade_config()
PLAIN, RISK = CFG.variants["plain"], CFG.variants["plain+risk"]
BE = replace(PLAIN, breakeven=True)
PER_CONTRACT_COSTS = 2 * (0.62 + 0.25 * 2)  # commission + 1 tick slippage, both sides


def cand(day, hour, entry=102.0, stop=99.75, target=105.0, half=False):
    t = datetime(2026, 11, day, hour, tzinfo=NY)
    row = dict.fromkeys(SCHEMA) | {
        "setup_ts": t,
        "direction": "bull",
        "signal_ts": t,
        "entry_ts": t,
        "session": t.date(),
        "entry": entry,
        "stop": stop,
        "target": target,
        "target_capped": False,
        "rr": (target - entry) / (entry - stop),
        "planned_stop_pts": entry - stop,
        "half_size": half,
    }
    return row


def cands(*rows):
    return pl.DataFrame(list(rows), schema=SCHEMA)


QUIET = (102.0, 103.0, 101.5, 102.5)  # touches neither the stop (99.75) nor the target (105)
LOSER = (102.0, 102.2, 99.0, 99.5)  # stop


def test_target_hit(ohlc):
    t, _ = simulate(
        cands(cand(3, 11)),
        ohlc([QUIET, (102.5, 105.5, 102, 105)], "2026-11-03 11:00", "1h"),
        MNQ,
        CFG,
        PLAIN,
    )
    r = t.row(0, named=True)
    assert (r["contracts"], r["exit_reason"], r["exit"]) == (111, "target", 105.0)
    assert r["gross_$"] == pytest.approx(111 * 3 * 2) and r["costs_$"] == pytest.approx(
        111 * PER_CONTRACT_COSTS
    )
    assert r["r"] == pytest.approx((666 - 111 * PER_CONTRACT_COSTS) / 499.5)


def test_same_bar_stop_wins(ohlc):
    t, _ = simulate(
        cands(cand(3, 11)), ohlc([(102, 111, 99, 105)], "2026-11-03 11:00", "1h"), MNQ, CFG, PLAIN
    )
    r = t.row(0, named=True)
    assert (r["exit_reason"], r["exit"]) == ("stop", 99.75)
    assert r["net_$"] == pytest.approx(-499.5 - 111 * PER_CONTRACT_COSTS)


def test_flat_at_four(ohlc):
    bars = ohlc(
        [QUIET, QUIET, (102.5, 104, 101, 103.3)], "2026-11-03 14:00", "1h"
    )  # 14:00, 15:00, 16:00
    r = simulate(cands(cand(3, 14)), bars, MNQ, CFG, PLAIN)[0].row(0, named=True)
    assert (r["exit_reason"], r["exit"], str(r["exit_ts"])) == (
        "flat",
        102.5,
        "2026-11-03 21:00:00+00:00",
    )


def test_breakeven_moves_stop_next_bar_only(ohlc):
    # bar 0 reaches +1R (104.25) and dips to 101.9, below entry: the stop must not move yet
    bars = ohlc([(102, 104.5, 101.9, 104), (104, 104.2, 101.5, 102)], "2026-11-03 11:00", "1h")
    r = simulate(cands(cand(3, 11)), bars, MNQ, CFG, BE)[0].row(0, named=True)
    assert (r["exit_reason"], r["exit"], str(r["exit_ts"])) == (
        "breakeven",
        102.0,
        "2026-11-03 18:00:00+00:00",
    )


def test_daily_cap_after_minus_two_r(ohlc):
    cfg = replace(CFG, max_trades=5, cushion_frac=1.0)  # isolate rule 1 from rule 2
    bars = ohlc([LOSER, LOSER, LOSER], "2026-11-03 11:00", "1h")
    three = cands(cand(3, 11), cand(3, 12), cand(3, 13))
    with_rules = simulate(three, bars, MNQ, cfg, RISK)[0]
    assert with_rules["skip"].to_list() == [None, None, "daily_cap"]
    assert simulate(three, bars, MNQ, cfg, PLAIN)[0]["skip"].to_list() == [None, None, None]


def _two_days(ohlc, first, second):
    return pl.concat(
        [ohlc([first], "2026-11-03 11:00", "1h"), ohlc([second], "2026-11-04 11:00", "1h")]
    )


def test_cushion_rule_skips_big_risk(ohlc):
    # after one full loss the cushion is 2500 - 748.6 = 1751; 25% of it (438) < the 499.5 planned loss
    bars = _two_days(ohlc, LOSER, QUIET)
    two = cands(cand(3, 11), cand(4, 11))
    assert simulate(two, bars, MNQ, CFG, RISK)[0]["skip"].to_list() == [None, "cushion"]
    assert simulate(two, bars, MNQ, CFG, PLAIN)[0]["skip"].to_list() == [None, None]


def test_step_down_size_after_drawdown(ohlc):
    acct = replace(CFG.account, drawdown=1400.0)
    cfg = replace(CFG, account=acct, cushion_frac=1.0)  # isolate rule 3 from rule 2
    t = simulate(cands(cand(3, 11), cand(4, 11)), _two_days(ohlc, LOSER, QUIET), MNQ, cfg, RISK)[0]
    assert t["contracts"].to_list() == [111, 55]  # 0.5% of 50k = 250 -> floor(250 / 4.5)


def test_breach_stops_trading(ohlc):
    cfg = replace(CFG, account=replace(CFG.account, drawdown=500.0))
    t, state = simulate(
        cands(cand(3, 11), cand(4, 11)), _two_days(ohlc, LOSER, QUIET), MNQ, cfg, PLAIN
    )
    assert t["skip"].to_list() == [None, "account_breached"]
    assert str(state["breached_at"]) == "2026-11-03 17:00:00+00:00"


def test_one_position_and_max_trades(ohlc):
    bars = ohlc(
        [QUIET, QUIET, (102.5, 105.5, 102, 105), QUIET, (102, 105.5, 101, 105), QUIET],
        "2026-11-03 10:00",
        "1h",
    )
    # first trade enters 10:00 and exits at the 12:00 bar; a 11:00 entry overlaps it
    four = cands(cand(3, 10), cand(3, 11), cand(3, 13), cand(3, 15))
    assert simulate(four, bars, MNQ, CFG, PLAIN)[0]["skip"].to_list() == [
        None,
        "in_position",
        None,
        "max_trades",
    ]


def test_half_size(ohlc):
    t = simulate(
        cands(cand(3, 11, half=True)),
        ohlc([QUIET, (102.5, 105.5, 102, 105)], "2026-11-03 11:00", "1h"),
        MNQ,
        CFG,
        PLAIN,
    )[0]
    assert t["contracts"][0] == 55  # floor(250 / 4.5)


def test_rule_two_as_proposed_halts_after_one_loss(ohlc):
    # Documents a flaw in proposed rule 2: after one 1% loss on APEX 50k the cushion is 1751,
    # 25% of it (438) is below a full 1% trade (499.5), and nothing can ever rebuild it.
    days = [ohlc([LOSER], "2026-11-03 11:00", "1h")] + [
        ohlc([QUIET], f"2026-11-{d:02d} 11:00", "1h") for d in (4, 5, 6)
    ]
    t = simulate(
        cands(cand(3, 11), cand(4, 11), cand(5, 11), cand(6, 11)), pl.concat(days), MNQ, CFG, RISK
    )[0]
    assert t["skip"].to_list() == [None, "cushion", "cushion", "cushion"]


def test_open_profit_trails_the_threshold(ohlc):
    # The trade runs to +4 points (111 contracts: +888) before stopping out. APEX trails on that
    # open peak, so the threshold rises from -2500 to min(888 - 2500, 100) = -1612.
    bars = ohlc([(102, 106, 101.5, 105.5), (105.5, 105.6, 99, 99.5)], "2026-11-03 11:00", "1h")
    _, state = simulate(cands(cand(3, 11, target=110.0)), bars, MNQ, CFG, PLAIN)
    assert state["peak"] == pytest.approx(111 * 4 * 2) and state["threshold"] == pytest.approx(
        888 - 2500
    )


def test_breach_inside_a_trade_counts(ohlc):
    cfg = replace(CFG, account=replace(CFG.account, drawdown=700.0))
    # runs +888 open (threshold -> 100, the lock), then the stop takes equity below it
    bars = pl.concat(
        [
            ohlc([(102, 106, 101.5, 105.5), (105.5, 105.6, 99, 99.5)], "2026-11-03 11:00", "1h"),
            ohlc([QUIET], "2026-11-04 11:00", "1h"),
        ]
    )
    t, state = simulate(cands(cand(3, 11, target=110.0), cand(4, 11)), bars, MNQ, cfg, PLAIN)
    assert state["breached_at"] is not None and t["skip"].to_list() == [None, "account_breached"]


def test_five_minute_bars_with_a_gap_at_the_start(ohlc):
    # the first two 5m bars are 10 minutes apart; the bar size must still read as 5m
    first = ohlc([QUIET], "2026-11-03 09:30", "5m")
    rest = ohlc([QUIET, (102.5, 105.5, 102, 105)], "2026-11-03 09:40", "5m")
    t, _ = simulate(
        cands(cand(3, 9)), pl.concat([first, rest]).with_columns(pl.col("ts")), MNQ, CFG, PLAIN
    )
    assert str(t["exit_ts"][0]) == "2026-11-03 14:50:00+00:00"  # the 09:45 bar closes 09:50 ET
