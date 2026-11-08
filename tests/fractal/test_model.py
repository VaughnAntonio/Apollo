from pathlib import Path

import polars as pl
import pytest

from apollo.fractal.model import COLUMNS, run_model

NOWHERE = Path("unused")


def test_finds_both_setups_with_cisd(ohlc_long):
    htf, ltf = ohlc_long
    out = run_model(NOWHERE, "MNQ", "1H-5m", htf=htf, ltf=ltf)
    assert out.columns == COLUMNS
    two = out.filter(pl.col("c2_ts").is_in([htf["ts"][4], htf["ts"][19]]))
    assert two.height == 2 and two["cisd_ts"].is_not_null().all()
    assert two["early"].all() and not two["ltf_missing"].any()


def test_prefix_stability(ohlc_long):
    htf, ltf = ohlc_long
    full = run_model(NOWHERE, "MNQ", "1H-5m", htf=htf, ltf=ltf)
    cut = htf["ts"][20]
    part = run_model(
        NOWHERE,
        "MNQ",
        "1H-5m",
        htf=htf.filter(pl.col("ts") < cut),
        ltf=ltf.filter(pl.col("ts") < cut),
    )
    done = full.filter(pl.col("cisd_confirmed_at") < cut)
    volatile = ["c3_closed", "skipped_outside"]  # these change as later bars arrive
    assert done.height == 2
    same = part.filter(pl.col("c2_ts").is_in(done["c2_ts"].implode()))
    assert done.drop(volatile).equals(same.drop(volatile))


def test_ltf_missing_for_old_setup(ohlc_long):
    htf, ltf = ohlc_long
    out = run_model(NOWHERE, "MNQ", "1H-5m", htf=htf, ltf=ltf.filter(pl.col("ts") > htf["ts"][25]))
    old = out.filter(pl.col("c2_ts") < htf["ts"][25])
    assert old.height >= 2 and old["ltf_missing"].all() and old["cisd_ts"].is_null().all()


@pytest.mark.skipif(not Path("data_store/bars/MNQ").exists(), reason="no local data")
def test_real_mnq_runs():
    out = run_model(Path("data_store"), "MNQ", "D-1H")
    assert out.height > 0 and out.columns == COLUMNS
