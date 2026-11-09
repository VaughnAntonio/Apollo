from datetime import time
from pathlib import Path

import pytest

from apollo.strategy.config import load_trade_config


def test_config_defaults():
    c = load_trade_config()
    assert (c.risk_pct, c.min_rr, c.max_trades, c.flat_at) == (0.01, 1.5, 2, time(16, 0))
    assert c.account.name == "APEX 50k" and c.account.drawdown == 2500 and c.account.lock == 100
    assert c.account.profit_target == 3000 and c.holdout_months == 3
    assert set(c.variants) == {
        "plain",
        "regime",
        "range",
        "both",
        "plain+risk",
        "both+risk",
        "both+risk+be",
        "both+risk+fomc",
        "both+risk+event",
    }
    assert c.variants["both+risk+be"].breakeven and not c.variants["both+risk"].breakeven
    assert c.variants["plain"] == c.variants["plain"].__class__(
        False, False, False, False, False, False
    )
    assert c.windows["D-1H"] == (time(9, 0), time(15, 0)) and c.windows["1H-5m"] == (
        time(9, 30),
        time(12, 0),
    )
    assert c.commission == {"micro": 0.62, "emini": 2.25} and c.slip_ticks == 1


@pytest.mark.skipif(not Path("data_store/context/vol.parquet").exists(), reason="no local data")
def test_forecast_frame_is_out_of_sample_only():
    from apollo.models.report import forecast_frame

    f = forecast_frame(Path("data_store"), "MNQ")
    assert {
        "date",
        "open",
        "p_trend_up",
        "p_trend_down",
        "p_chop",
        "p_normal",
        "up_bound",
        "down_bound",
        "ev_fomc",
        "ev_any",
    } <= set(f.columns)
    assert (
        f.height == 239 and f.head(30)["up_bound"].is_null().all() and f["up_bound"][30] is not None
    )
