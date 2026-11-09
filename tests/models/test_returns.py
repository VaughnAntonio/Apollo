import polars as pl
import pytest

from apollo.config import load_symbols
from apollo.models.returns import clean_returns

SYMS = load_symbols()


def _jumped(bars, start, symbol="MNQ"):
    h = bars(start, 200, "1h", symbol=symbol)
    jump = pl.when(pl.int_range(pl.len()) >= 100).then(pl.col("close") + 300)
    return h.with_columns(jump.otherwise(pl.col("close")).alias("close"))


def test_roll_jump_zeroed(bars):
    out = clean_returns(_jumped(bars, "2026-03-12 09:00"), SYMS["MNQ"])  # March 2026 window
    assert out["roll_jump"].sum() == 1 and out.filter("roll_jump")["ret"][0] == 0.0
    assert float(out["ret"].abs().max()) < 0.02  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("start", "code"), [("2026-05-04 09:00", "MNQ"), ("2026-03-12 09:00", "MGC")]
)
def test_no_flag_outside_window_or_for_none_rule(bars, start, code):
    out = clean_returns(_jumped(bars, start, code), SYMS[code])
    assert out["roll_jump"].sum() == 0 and float(out["ret"].abs().max()) > 0.5  # type: ignore[arg-type]
