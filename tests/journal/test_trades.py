from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from apollo.journal.trades import auto_close, close_trade, take_trade

from apollo.journal.store import JournalStore

NY = ZoneInfo("America/New_York")
SIGNAL = {
    "symbol": "MNQ",
    "status": "trigger",
    "direction": "bull",
    "entry": 102.0,
    "stop": 99.75,
    "target": 105.0,
    "contracts": 2,
    "risk_of_limit": 0.0036,
    "variant": "plain",
    "account": "APEX 50k",
    "as_of": datetime(2026, 11, 3, 11, tzinfo=NY),
    "checklist": [{"step": "daily_bias", "status": "pass", "detail": "bull C2 at a swing"}],
    "research_only": True,
}
FORECAST = {"proba": {"trend_up": 0.4}, "up_bound": 300.0, "down_bound": 250.0}


def test_take_trade_records_snapshot(tmp_path):
    s = JournalStore(tmp_path / "j.duckdb")
    e = s.get(take_trade(s, SIGNAL, FORECAST))
    assert e is not None and e["source"] == "signal" and e["side"] == "long" and e["size"] == 2
    snap = e["model_snapshot"]
    assert snap["checklist"][0]["step"] == "daily_bias" and snap["forecast"] == FORECAST
    assert snap["signal"]["entry"] == 102.0 and "snapshot_at" in snap


def test_take_trade_overrides_fill_and_size(tmp_path):
    s = JournalStore(tmp_path / "j.duckdb")
    e = s.get(take_trade(s, SIGNAL, None, fill=102.25, size=1))
    assert e is not None and (e["entry"], e["size"]) == (102.25, 1)
    assert e["model_snapshot"]["signal"]["entry"] == 102.0  # the snapshot keeps what the model said


def test_take_trade_refuses_without_trigger(tmp_path):
    with pytest.raises(ValueError):
        take_trade(JournalStore(tmp_path / "j.duckdb"), dict(SIGNAL, status="waiting"), None)


def test_close_trade(tmp_path):
    s = JournalStore(tmp_path / "j.duckdb")
    i = take_trade(s, SIGNAL, None)
    e = close_trade(s, i, 105.0, datetime(2026, 11, 3, 17, tzinfo=UTC), "target")
    assert e["exit_reason"] == "target" and e["r"] is not None and e["r"] > 0


def test_auto_close_stop_first_and_flat(tmp_path, ohlc):
    s = JournalStore(tmp_path / "j.duckdb")
    a = take_trade(s, SIGNAL, None)  # opened 11:00 ET on Nov 3
    b = take_trade(s, dict(SIGNAL, as_of=datetime(2026, 11, 4, 14, tzinfo=NY)), None)  # 14:00 Nov 4
    bars = pl.concat(
        [
            ohlc(
                [(102, 103, 101.5, 102.5), (102.5, 106, 99, 104)], "2026-11-03 11:00", "1h"
            ),  # both hit: stop
            ohlc(
                [(102, 103, 101.5, 102.5), (102.5, 103, 101.5, 102.7), (102.7, 104, 101, 103)],
                "2026-11-04 14:00",
                "1h",
            ),
        ]
    )
    closed = auto_close(s, {"MNQ": bars}, datetime(2026, 11, 4, 22, tzinfo=UTC))
    ea, eb = s.get(a), s.get(b)
    assert set(closed) == {a, b} and ea is not None and eb is not None
    assert (ea["exit_reason"], ea["exit"]) == ("stop_auto", 99.75)
    assert (eb["exit_reason"], eb["exit"]) == ("flat_auto", 102.7)  # the 15:00 bar's close
    assert ea["needs_confirm"] and eb["needs_confirm"]


def test_auto_close_leaves_running_trades_open(tmp_path, ohlc):
    s = JournalStore(tmp_path / "j.duckdb")
    i = take_trade(s, SIGNAL, None)
    bars = ohlc([(102, 103, 101.5, 102.5)], "2026-11-03 11:00", "1h")
    assert auto_close(s, {"MNQ": bars}, datetime(2026, 11, 3, 16, 30, tzinfo=UTC)) == []
    e = s.get(i)
    assert e is not None and e["exit"] is None
