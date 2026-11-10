import shutil
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from apollo.explain import EXAMPLE, explain_day

NY = ZoneInfo("America/New_York")
REAL = Path("data_store")
DAY = date(2026, 4, 22)
pytestmark = pytest.mark.skipif(
    not (REAL / "bars/MNQ/1h").exists() or not (REAL / "context/vol.parquet").exists(),
    reason="no local data",
)


@pytest.fixture(scope="module")
def first():
    return explain_day(REAL, "MNQ", DAY)


def shifted_copy(tmp: Path, after: datetime, by: float) -> Path:
    """A copy of the MNQ data where every bar from `after` on is moved by `by` points."""
    root = tmp / "data"
    shutil.copytree(REAL / "context", root / "context")
    for tf in ("1h", "1d", "5m"):
        src = REAL / "bars/MNQ" / tf
        if not src.exists():
            continue
        dst = root / "bars/MNQ" / tf
        dst.mkdir(parents=True)
        for f in src.glob("*.parquet"):
            df = pl.read_parquet(f)
            later = pl.col("ts") >= after.astimezone(ZoneInfo("UTC"))
            df = df.with_columns(
                [
                    pl.when(later).then(pl.col(c) + by).otherwise(pl.col(c)).alias(c)
                    for c in ("open", "high", "low", "close")
                ]
            )
            df.write_parquet(dst / f.name)
    return root


def test_the_configured_example_is_a_plain_d1h_trade_day():
    assert EXAMPLE == {"symbol": "MNQ", "date": DAY}


def test_explain_day_has_a_complete_setup(first):
    s = first["fractal"]["setup"]
    assert s["c1_ts"] < s["c2_ts"] < s["cisd_ts"]
    assert s["direction"] in ("bull", "bear")
    assert len({s["stop"], s["entry"], s["target"]}) == 3
    assert first["fractal"]["htf"] and first["fractal"]["ltf"]
    assert set(first["fractal"]["ltf"][0]) == {"time", "open", "high", "low", "close", "volume"}


def test_explain_day_regime_and_range(first):
    g, r = first["regime"], first["range"]
    assert set(g["proba"]) == {"trend_up", "trend_down", "chop", "normal"}
    assert abs(sum(g["proba"].values()) - 1) < 1e-6 and g["label"] in g["proba"]
    assert "kurt" in g["features"]
    assert r["up_bound"] > 0 and r["down_bound"] > 0 and r["low"] <= r["open"] <= r["high"]
    assert 0 < len(r["coverage_60"]) <= 60 and r["coverage_60"][-1]["date"] == DAY.isoformat()


def test_explain_day_uses_only_data_known_at_the_cutoff(first, tmp_path):
    # move every bar from the end of that session on; the forecasts for the day must not change
    after = datetime.combine(DAY + timedelta(days=1), time(0), tzinfo=NY)
    b = explain_day(shifted_copy(tmp_path, after, 500.0), "MNQ", DAY)
    assert b["regime"] == first["regime"]
    assert b["range"]["up_bound"] == first["range"]["up_bound"]
    assert b["range"]["down_bound"] == first["range"]["down_bound"]


def test_a_day_without_a_trade_is_refused():
    with pytest.raises(ValueError, match="no plain D-1H trade"):
        explain_day(REAL, "MNQ", date(2026, 4, 25))  # a Saturday
