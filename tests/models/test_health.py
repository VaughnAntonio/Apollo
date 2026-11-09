from datetime import timedelta

import numpy as np
import polars as pl
import pytest

from apollo.models.health import FEATURES, _stats, health_features


def test_features_known_values():
    f = _stats(np.array([0.01, -0.01] * 60))  # alternating: rms 0.01, crest 1, kurtosis -2
    assert f["rms"] == pytest.approx(0.01) and f["crest"] == pytest.approx(1.0)
    assert f["kurt"] == pytest.approx(-2.0)


def test_spike_raises_crest_and_spectral_kurtosis():
    r = np.random.default_rng(0).normal(0, 0.001, 120)
    s = r.copy()
    s[110] = 0.02
    assert _stats(s)["crest"] > 3 * _stats(r)["crest"]
    assert _stats(s)["sk_high"] > _stats(r)["sk_high"]


def test_columns_and_warmup(synthetic_frames):
    sess, h1, d1, sym = synthetic_frames
    f = health_features(sess, h1, d1, sym)
    assert f.columns == ["date", *FEATURES] and f.height == sess.height
    assert f["rms"][0] is None and f["rms"][-1] is not None  # 120 clean returns needed first


def test_no_lookahead(synthetic_frames):
    sess, h1, d1, sym = synthetic_frames
    base = health_features(sess, h1, d1, sym)
    day = sess["forecast_at"][-10]
    later = pl.col("ts") >= day  # 1H bars opening at or after 09:00 on that day
    dated_later = (pl.col("ts") + timedelta(hours=6)).dt.date() >= day.date()  # its daily bar on

    def bump(cond):
        return pl.when(cond).then(pl.col("close") * 1.1).otherwise(pl.col("close")).alias("close")

    mod = health_features(
        sess, h1.with_columns(bump(later)), d1.with_columns(bump(dated_later)), sym
    )
    keep = pl.col("date") <= day.date()
    assert base.filter(keep).equals(mod.filter(keep))
    assert not base.filter(~keep).equals(mod.filter(~keep))  # and later rows do see the change
