from dataclasses import replace

from apollo.fractal.cisd import find_cisd
from tests.fractal.conftest import END

START = "2026-11-03 09:30"


def test_bull_cisd_closes_above_run_open(ohlc, bull_setup):
    rows = [
        (101, 101.5, 100.2, 100.5),  # down-close run starts here: open 101
        (100.5, 100.6, 99.5, 99.8),
        (99.8, 99.9, 98.8, 99.0),
        (99.0, 100.0, 98.9, 99.9),
        (99.9, 101.4, 99.8, 101.2),  # closes above 101: CISD
    ]
    c = find_cisd(ohlc(rows, START, "5m"), "5m", bull_setup, END)
    assert c is not None
    assert (c.level, c.protected, c.early, c.eq_broken) == (101.0, 98.8, True, False)
    assert str(c.ts) == "2026-11-03 14:50:00+00:00"


def test_new_low_resets_level(ohlc, bull_setup):
    rows = [
        (101, 101.5, 100.2, 100.5),
        (100.5, 100.6, 99.5, 99.8),
        (99.8, 100.4, 99.6, 100.3),  # up bar: level still 101
        (100.3, 100.35, 99.0, 99.1),  # new low from a fresh down run: level 100.3
        (99.1, 100.8, 99.05, 100.7),
    ]
    c = find_cisd(ohlc(rows, START, "5m"), "5m", bull_setup, END)
    assert c is not None and c.level == 100.3 and str(c.ts) == "2026-11-03 14:50:00+00:00"


def test_no_sweep_no_cisd(ohlc, bull_setup):
    rows = [(101, 101.5, 100.3, 100.5), (100.5, 102, 100.4, 101.8)]
    assert find_cisd(ohlc(rows, START, "5m"), "5m", bull_setup, END) is None


def test_eq_broken_after_c2_close(ohlc, bull_setup):
    rows = [(101, 101.5, 100.2, 100.5), (100.5, 100.6, 99.5, 99.8)]
    rows += [(99.8, 100.0, 99.6, 99.9)] * 11  # 09:40 to 10:30, quiet up bars
    rows += [(99.9, 99.95, 98.5, 98.6), (98.6, 100.2, 98.55, 100.1)]  # 10:35 breaks EQ 99.0
    c = find_cisd(ohlc(rows, START, "5m"), "5m", bull_setup, END)
    assert c is not None and (c.eq_broken, c.early, c.level) == (True, False, 99.9)


def test_bear_mirror(ohlc, bull_setup):
    bear = replace(
        bull_setup,
        direction="bear",
        c1_high=100.0,
        c1_low=98.0,
        c2_low=98.5,
        c2_high=101.2,
        eq=101.0,
    )
    rows = [(99, 99.8, 98.5, 99.5), (99.5, 100.5, 99.4, 100.2), (100.2, 101.2, 100.1, 101.0)]
    rows += [(101.0, 101.1, 100.0, 100.1), (100.1, 100.2, 98.6, 98.8)]  # closes below 99
    c = find_cisd(ohlc(rows, START, "5m"), "5m", bear, END)
    assert c is not None and (c.level, c.protected) == (99.0, 101.2)
