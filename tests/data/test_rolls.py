from datetime import date

from mnq.config import load_symbols
from mnq.data.rolls import mark_roll_days, roll_windows
from mnq.data.sessions import add_session_columns


def test_2026_windows():
    w = roll_windows(date(2026, 1, 1), date(2026, 12, 31))
    assert len(w) == 4
    assert w[0] == (date(2026, 3, 12), date(2026, 3, 20))
    assert w[3] == (date(2026, 12, 10), date(2026, 12, 18))


def test_index_flags(bars):
    df = add_session_columns(
        bars("2026-03-15 19:00", 2, "1h").vstack(bars("2026-04-01 10:00", 1, "1h"))
    )
    out = mark_roll_days(df, load_symbols()["MNQ"])
    assert out["near_roll"].to_list() == [True, True, False]


def test_none_rule_never_flags(bars):
    df = add_session_columns(bars("2026-03-15 19:00", 2, "1h", symbol="MGC"))
    assert not mark_roll_days(df, load_symbols()["MGC"])["near_roll"].any()
