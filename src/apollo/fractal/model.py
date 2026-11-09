"""Run the Fractal Model over one timeframe pairing: C2/C3 on the higher, CISD on the lower."""

from datetime import timedelta
from pathlib import Path
from typing import Literal, cast

import polars as pl

from apollo.config import load_symbols
from apollo.data.resample import to_4h
from apollo.data.rolls import mark_roll_days
from apollo.data.sessions import add_session_columns
from apollo.data.store import read_bars
from apollo.data.yahoo import Interval, bar_close
from apollo.fractal.candles import detect_c2
from apollo.fractal.cisd import find_cisd
from apollo.fractal.config import load_fractal_config

Pairing = Literal["D-1H", "4H-15m", "1H-5m"]
PAIRINGS: dict[Pairing, tuple[str, str]] = {
    "D-1H": ("1d", "1h"),
    "4H-15m": ("4h", "15m"),
    "1H-5m": ("1h", "5m"),
}

_TS = pl.Datetime("us", "UTC")
SCHEMA = {
    "code": pl.Utf8,
    "pairing": pl.Utf8,
    "direction": pl.Utf8,
    "c1_ts": _TS,
    "c2_ts": _TS,
    "c2_close": _TS,
    "c1_high": pl.Float64,
    "c1_low": pl.Float64,
    "c2_high": pl.Float64,
    "c2_low": pl.Float64,
    "eq": pl.Float64,
    "poi_kind": pl.Utf8,
    "poi_level": pl.Float64,
    "c3_closed": pl.Boolean,
    "near_roll": pl.Boolean,
    "ltf_missing": pl.Boolean,
    "cisd_ts": _TS,
    "cisd_confirmed_at": _TS,
    "cisd_level": pl.Float64,
    "protected": pl.Float64,
    "early": pl.Boolean,
    "eq_broken": pl.Boolean,
    "window_end": _TS,
    "after_c2_cisd_ts": _TS,
    "after_c2_cisd_confirmed_at": _TS,
    "after_c2_cisd_level": pl.Float64,
    "after_c2_protected": pl.Float64,
    "skipped_outside": pl.Int64,
}
COLUMNS = list(SCHEMA)


def complete_4h(h1: pl.DataFrame) -> pl.DataFrame:
    """4H bars built from 1H, without a last bucket that is still filling."""
    if h1.is_empty():
        return to_4h(h1)
    last_close = h1["ts"].max() + timedelta(hours=1)  # type: ignore[operator]
    return to_4h(h1).filter(bar_close("4h") <= last_close)


def load_pair(root: Path, code: str, pairing: Pairing) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Read the stored higher- and lower-timeframe bars for a pairing."""
    htf_i, ltf_i = PAIRINGS[pairing]
    if htf_i == "4h":
        htf = complete_4h(read_bars(root, code, "1h"))
    else:
        htf = read_bars(root, code, cast(Interval, htf_i))
    return htf, read_bars(root, code, cast(Interval, ltf_i))


def run_model(
    root: Path,
    code: str,
    pairing: Pairing,
    htf: pl.DataFrame | None = None,
    ltf: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """One row per C2 setup, with its CISD if the lower timeframe confirmed it."""
    if htf is None or ltf is None:
        htf, ltf = load_pair(root, code, pairing)
    htf_i, ltf_i = PAIRINGS[pairing]
    sym = load_symbols()[code]
    htf = htf.sort("ts").with_columns(close_ts=bar_close(htf_i, sym.kind))  # type: ignore[arg-type]
    setups, skipped = detect_c2(htf, htf_i, sym.tick_size, load_fractal_config(), sym.kind)
    rolls = mark_roll_days(add_session_columns(htf), sym)["near_roll"].to_list()
    ts, close_ts = htf["ts"].to_list(), htf["close_ts"].to_list()
    first_ltf = ltf["ts"].min() if ltf.height else None

    rows = []
    for s in setups:
        missing = first_ltf is None or first_ltf > s.c2_ts  # type: ignore[operator]
        if s.c2_idx + 1 < len(ts):
            window_end = close_ts[s.c2_idx + 1]
        else:
            window_end = s.c2_close + (s.c2_close - s.c2_ts)
        cisd = None if missing else find_cisd(ltf, ltf_i, s, window_end)
        late = None if missing else find_cisd(ltf, ltf_i, s, window_end, not_before=s.c2_close)
        rows.append(
            {
                "code": code,
                "pairing": pairing,
                "direction": s.direction,
                "c1_ts": ts[s.c1_idx],
                "c2_ts": s.c2_ts,
                "c2_close": s.c2_close,
                "c1_high": s.c1_high,
                "c1_low": s.c1_low,
                "c2_high": s.c2_high,
                "c2_low": s.c2_low,
                "eq": s.eq,
                "poi_kind": s.poi_kind,
                "poi_level": s.poi_level,
                "c3_closed": s.c3_closed,
                "near_roll": rolls[s.c2_idx],
                "ltf_missing": missing,
                "cisd_ts": cisd.ts if cisd else None,
                "cisd_confirmed_at": cisd.confirmed_at if cisd else None,
                "cisd_level": cisd.level if cisd else None,
                "protected": cisd.protected if cisd else None,
                "early": cisd.early if cisd else None,
                "eq_broken": cisd.eq_broken if cisd else None,
                "window_end": window_end,
                "after_c2_cisd_ts": late.ts if late else None,
                "after_c2_cisd_confirmed_at": late.confirmed_at if late else None,
                "after_c2_cisd_level": late.level if late else None,
                "after_c2_protected": late.protected if late else None,
                "skipped_outside": skipped,
            }
        )
    return pl.DataFrame(rows, schema=SCHEMA)
