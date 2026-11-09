"""Machine-health indicators applied to price, measured before each session's 09:00 ET forecast.

Vibration analysis watches a machine's signal for the statistics that rise before a failure:
energy (RMS) and its trend, peakiness (kurtosis, crest factor), the envelope of the signal, and
spectral kurtosis, which flags impulsive bursts in a frequency band. Here the signal is the last
120 hourly returns, and the "failure" is a change of market regime.
"""

import warnings

import numpy as np
import polars as pl
from scipy import signal, stats

from apollo.config import Symbol
from apollo.models.returns import clean_returns
from apollo.models.sessions import LABELS

WINDOW_STATS = (
    "rms",
    "rms_slope",
    "kurt",
    "skew",
    "crest",
    "env_mean",
    "env_kurt",
    "sk_low",
    "sk_mid",
    "sk_high",
)
FEATURES = (
    *WINDOW_STATS,
    "rng_24h",
    "gap",
    "d_ma50",
    "d_atr",
    *(f"prev_label_{lab}" for lab in LABELS),
)


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x**2)))


def _moment(fn, x: np.ndarray) -> float:
    """Skew or kurtosis, as 0 when the window is too flat to measure (e.g. a holiday)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return float(np.nan_to_num(fn(x)))


def _stats(r: np.ndarray) -> dict[str, float]:
    """Health statistics for one window of returns."""
    rms = _rms(r)
    env = np.abs(signal.hilbert(r))
    _, _, z = signal.stft(r, nperseg=24, noverlap=12)
    p = np.abs(z)[1:]  # drop the zero-frequency row
    with np.errstate(invalid="ignore", divide="ignore"):
        sk = np.nan_to_num(np.mean(p**4, axis=1) / np.mean(p**2, axis=1) ** 2 - 2)
    bands = np.array_split(sk, 3)
    prior = _rms(r[:-24])
    return {
        "rms": rms,
        "rms_slope": _rms(r[-24:]) / prior - 1 if prior else 0.0,
        "kurt": _moment(stats.kurtosis, r),
        "skew": _moment(stats.skew, r),
        "crest": float(np.max(np.abs(r)) / rms) if rms else 0.0,
        "env_mean": float(np.mean(env)),
        "env_kurt": _moment(stats.kurtosis, env),
        "sk_low": float(bands[0].mean()),
        "sk_mid": float(bands[1].mean()),
        "sk_high": float(bands[2].mean()),
    }


def _daily_context(d1: pl.DataFrame, sym: Symbol) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Trading date of each daily bar, distance from its 50-day average, and ATR as a fraction."""
    shift = 6 if sym.kind == "future" else 0  # futures daily bars open 18:00 ET the day before
    d = d1.sort("ts").with_columns(
        day=(
            pl.col("ts").dt.convert_time_zone("America/New_York") + pl.duration(hours=shift)
        ).dt.date(),
        tr=pl.max_horizontal(
            pl.col("high") - pl.col("low"),
            (pl.col("high") - pl.col("close").shift(1)).abs(),
            (pl.col("low") - pl.col("close").shift(1)).abs(),
        ),
    )
    d = d.with_columns(
        d_ma50=pl.col("close") / pl.col("close").rolling_mean(50) - 1,
        d_atr=pl.col("tr").rolling_mean(14) / pl.col("close"),
    )
    return d["day"].to_numpy(), d["d_ma50"].to_numpy(), d["d_atr"].to_numpy()


def health_features(
    sessions: pl.DataFrame, h1: pl.DataFrame, d1: pl.DataFrame, sym: Symbol, window: int = 120
) -> pl.DataFrame:
    """One feature row per session, from bars that closed by its 09:00 ET forecast time."""
    cr = clean_returns(h1, sym)
    close_ts = cr["ts"].dt.epoch("us").to_numpy() + 3_600_000_000  # an hourly bar closes 1h later
    open_ts = cr["ts"].dt.epoch("us").to_numpy()
    ret, opn = cr["ret"].to_numpy(), cr["open"].to_numpy()
    hi, lo, cl = cr["high"].to_numpy(), cr["low"].to_numpy(), cr["close"].to_numpy()
    days, ma50, atr = _daily_context(d1, sym)

    rows, prev = [], None
    for date, at, label in sessions.select("date", "forecast_at", "label").iter_rows():
        t = int(at.timestamp() * 1_000_000)
        cut = int(np.searchsorted(close_ts, t, side="right"))  # bars [0, cut) closed by 09:00
        row: dict[str, object] = {"date": date, **dict.fromkeys(FEATURES)}
        if cut - window >= 1:  # ret[0] has no previous close
            row.update(_stats(ret[cut - window : cut]))
            row["rng_24h"] = float(
                np.mean((hi[cut - 24 : cut] - lo[cut - 24 : cut]) / cl[cut - 24 : cut])
            )
            nine = int(np.searchsorted(open_ts, t))
            if nine < len(open_ts) and open_ts[nine] == t:
                row["gap"] = float(opn[nine] / cl[cut - 1] - 1)
        k = int(np.searchsorted(days, np.datetime64(date), side="left"))  # daily bars before D
        if k >= 1:
            row["d_ma50"] = None if np.isnan(ma50[k - 1]) else float(ma50[k - 1])
            row["d_atr"] = None if np.isnan(atr[k - 1]) else float(atr[k - 1])
        for lab in LABELS:
            row[f"prev_label_{lab}"] = 1.0 if prev == lab else 0.0
        rows.append(row)
        prev = label
    schema = {"date": pl.Date, **dict.fromkeys(FEATURES, pl.Float64)}
    return pl.DataFrame(rows, schema=schema)
