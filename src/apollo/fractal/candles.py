"""Candle 2 and Candle 3 of the Fractal Model on the higher timeframe (spec 5.6)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import polars as pl

from apollo.data.yahoo import bar_close
from apollo.fractal.config import FractalConfig
from apollo.fractal.levels import fair_value_gaps, swing_points


@dataclass(frozen=True)
class Setup:
    direction: Literal["bull", "bear"]
    c1_idx: int
    c2_idx: int
    c2_ts: datetime
    c2_close: datetime
    c1_high: float
    c1_low: float
    c2_high: float
    c2_low: float
    eq: float
    poi_kind: Literal["swing", "fvg"]
    poi_level: float
    c3_closed: bool | None


def _poi(
    direction, j, c1_low, c1_high, c2_low, c2_high, swings, gaps, cfg
) -> tuple[Literal["swing", "fvg"], float] | None:
    """The point of interest C2's sweep traded into, preferring the most recent swing."""
    first = j - cfg.poi_lookback
    if "swing" in cfg.poi_kinds:
        kind = "low" if direction == "bull" else "high"
        for idx, level, confirmed in reversed(swings[kind]):
            if confirmed > j - 1 or idx < first:
                continue
            if (direction == "bull" and c2_low <= level <= c1_low) or (
                direction == "bear" and c1_high <= level <= c2_high
            ):
                return "swing", level
    if "fvg" in cfg.poi_kinds:
        for idx, bottom, top, filled in reversed(gaps[direction]):
            if idx > j - 1 or idx < first or (filled is not None and filled < j):
                continue
            if direction == "bull" and c2_low <= top and bottom <= c1_low:
                return "fvg", top
            if direction == "bear" and c2_high >= bottom and top >= c1_high:
                return "fvg", bottom
    return None


def detect_c2(
    htf: pl.DataFrame,
    interval: str,
    tick: float,
    cfg: FractalConfig,
    kind: Literal["future", "stock"] = "future",
) -> tuple[list[Setup], int]:
    """Find C2 reversal closures at a point of interest. Returns setups and skipped outside bars."""
    # shortcut: a plain loop over rows; higher-timeframe frames are a few thousand rows at most.
    df = htf.sort("ts").with_columns(close_ts=bar_close(interval, kind))  # type: ignore[arg-type]
    o, h, lo, c = (df[k].to_list() for k in ("open", "high", "low", "close"))
    ts, close_ts = df["ts"].to_list(), df["close_ts"].to_list()
    sw = swing_points(df)
    swings = {
        k: sw.filter(kind=k).select("idx", "level", "confirmed_idx").rows() for k in ("low", "high")
    }
    fv = fair_value_gaps(df)
    gaps = {
        k: fv.filter(kind=k).select("idx", "bottom", "top", "filled_idx").rows()
        for k in ("bull", "bear")
    }

    def ticks_past(a: float, b: float) -> bool:
        # Count whole ticks so float noise (1.13 - 0.01 = 1.1199...) can't hide a one-tick sweep.
        return round((a - b) / tick, 6) >= cfg.sweep_ticks

    setups, skipped = [], 0
    for j in range(1, df.height):
        c1_low, c1_high = lo[j - 1], h[j - 1]
        swept_low, swept_high = ticks_past(c1_low, lo[j]), ticks_past(h[j], c1_high)
        bull = swept_low and c[j] > c1_low
        bear = swept_high and c[j] < c1_high
        if swept_low and swept_high and c1_low < c[j] < c1_high:
            skipped += 1
            continue
        sides: tuple[tuple[Literal["bull", "bear"], bool], ...] = (("bull", bull), ("bear", bear))
        for direction, hit in sides:
            if not hit:
                continue
            poi = _poi(direction, j, c1_low, c1_high, lo[j], h[j], swings, gaps, cfg)
            if poi is None:
                continue
            if direction == "bull":
                eq = (lo[j] + min(o[j], c[j])) / 2
                c3 = c[j + 1] > h[j] if j + 1 < df.height else None
            else:
                eq = (h[j] + max(o[j], c[j])) / 2
                c3 = c[j + 1] < lo[j] if j + 1 < df.height else None
            setups.append(
                Setup(
                    direction,
                    j - 1,
                    j,
                    ts[j],
                    close_ts[j],
                    c1_high,
                    c1_low,
                    h[j],
                    lo[j],
                    eq,
                    poi[0],
                    poi[1],
                    c3,
                )
            )
    return setups, skipped
