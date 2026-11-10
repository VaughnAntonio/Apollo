from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from apollo.journal.store import JournalStore

OPEN = datetime(2026, 11, 3, 15, 0, tzinfo=UTC)
CLOSE = datetime(2026, 11, 3, 17, 0, tzinfo=UTC)
NY = ZoneInfo("America/New_York")
BULL = {
    "opened_at": OPEN,
    "symbol": "MNQ",
    "side": "long",
    "entry": 102.0,
    "stop": 99.75,
    "target": 110.0,
    "size": 2,
    "fees": 4.48,
    "account": "APEX 50k",
    "stage": "eval",
    "source": "manual",
}


def test_add_get_derived(tmp_path):
    s = JournalStore(tmp_path / "j.duckdb")
    i = s.add(dict(BULL))
    e = s.get(i)
    assert e is not None
    assert e["risk_$"] == 9.0 and e["r"] is None and e["pnl_$"] is None  # open: no P&L yet
    s.update(i, {"exit": 106.5, "closed_at": CLOSE})
    e = s.get(i)
    assert e is not None
    assert e["pnl_$"] == pytest.approx(4.5 * 2 * 2 - 4.48)
    assert e["r"] == pytest.approx((18 - 4.48) / 9) and e["win"] is True


def test_short_side_sign(tmp_path):
    s = JournalStore(tmp_path / "j.duckdb")
    i = s.add(dict(BULL, side="short", entry=100.0, stop=102.0, target=94.0, fees=0.0))
    e = s.update(i, {"exit": 101.0, "closed_at": CLOSE})
    assert e["pnl_$"] == pytest.approx(-1 * 2 * 2) and e["r"] == pytest.approx(-4 / 8)


def test_moving_the_stop_does_not_change_r(tmp_path):
    s = JournalStore(tmp_path / "j.duckdb")
    i = s.add(dict(BULL, fees=0.0))
    s.update(i, {"stop": 101.0})  # trailed the stop after entry
    e = s.update(i, {"exit": 101.0, "closed_at": CLOSE})
    assert e["initial_stop"] == 99.75 and e["stop"] == 101.0
    assert e["r"] == pytest.approx(-1 * 2 * 2 / 9)  # measured against the original 2.25-point risk


@pytest.mark.parametrize(
    "field",
    [
        "model_snapshot",
        "initial_stop",
        "source",
        "opened_at",
        "imported_r",
        "imported_pnl",
        "scaled",
    ],
)
def test_frozen_fields(tmp_path, field):
    s = JournalStore(tmp_path / "j.duckdb")
    i = s.add(dict(BULL))
    with pytest.raises(ValueError):
        s.update(i, {field: None})


@pytest.mark.parametrize(
    "bad",
    [
        {"size": -1},
        {"size": 0},
        {"side": "sideways"},
        {"screenshot": "../x.png"},
        {"screenshot": "/etc/passwd"},
        {"symbol": "NOPE"},
        {"grade": "Z"},
        {"stage": "lucky"},
    ],
)
def test_rejects_bad_input(tmp_path, bad):
    with pytest.raises(ValueError):
        JournalStore(tmp_path / "j.duckdb").add(dict(BULL, **bad))


def test_list_filters_and_order(tmp_path):
    s = JournalStore(tmp_path / "j.duckdb")
    a = s.add(dict(BULL))
    b = s.add(dict(BULL, symbol="MES", opened_at=CLOSE))
    c = s.add(dict(BULL, opened_at=datetime(2026, 11, 4, 15, tzinfo=UTC)))
    assert [e["id"] for e in s.list()] == [c, b, a]
    assert [e["id"] for e in s.list(symbol="MNQ")] == [c, a]
    assert s.delete(b) is True and s.get(b) is None and s.delete(b) is False


def test_tags_and_snapshot_roundtrip(tmp_path):
    s = JournalStore(tmp_path / "j.duckdb")
    i = s.add(dict(BULL, tags=["Gamba", "FOMC"], model_snapshot={"proba": {"chop": 0.6}}))
    e = s.get(i)
    assert e is not None
    assert e["tags"] == ["Gamba", "FOMC"] and e["model_snapshot"] == {"proba": {"chop": 0.6}}


def test_naive_times_are_new_york(tmp_path):
    s = JournalStore(tmp_path / "j.duckdb")
    i = s.add(dict(BULL, opened_at=datetime(2026, 11, 10, 10)))
    e = s.get(i)
    assert e is not None and e["opened_at"] == datetime(2026, 11, 10, 10, tzinfo=NY)
    assert s.list(start=datetime(2026, 11, 10, 9, 59), end=datetime(2026, 11, 10, 10, 1))
