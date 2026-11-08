"""Change in state of delivery (CISD) on the lower timeframe (spec 5.6)."""

from dataclasses import dataclass
from datetime import UTC, datetime

import polars as pl

from apollo.data.yahoo import bar_close
from apollo.fractal.candles import Setup


@dataclass(frozen=True)
class Cisd:
    ts: datetime
    confirmed_at: datetime
    level: float
    protected: float
    early: bool
    eq_broken: bool


def find_cisd(
    ltf: pl.DataFrame,
    ltf_interval: str,
    setup: Setup,
    window_end: datetime,
    not_before: datetime | None = None,
) -> Cisd | None:
    """Find the first CISD after C2's sweep, up to `window_end`.

    With `not_before`, only a confirmation that closes at or after it counts (for example C2's
    close, when the setup itself is known).

    Bullish: once the lower timeframe trades below C1's low, a candle that closes above the open
    of the down-close run that made the lowest low confirms it. Bearish mirrors this, so it runs
    on negated prices.
    """
    w = (
        ltf.sort("ts")
        .with_columns(close_ts=bar_close(ltf_interval))  # type: ignore[arg-type]
        .filter(
            # One HTF bar of history before C2 so a down run that began earlier keeps its start.
            (pl.col("ts") >= (setup.c2_ts - (setup.c2_close - setup.c2_ts)).astimezone(UTC))
            & (pl.col("close_ts") <= window_end.astimezone(UTC))
        )
    )
    sign = 1.0 if setup.direction == "bull" else -1.0
    # In bear mode, high becomes the negated low, so "low" always means the extreme being swept.
    o = [sign * x for x in w["open"]]
    c = [sign * x for x in w["close"]]
    lo = [sign * x for x in (w["low"] if sign > 0 else w["high"])]
    c1 = sign * (setup.c1_low if sign > 0 else setup.c1_high)
    eq = sign * setup.eq
    ts, close_ts = w["ts"].to_list(), w["close_ts"].to_list()

    low_so_far, level, eq_broken = float("inf"), None, False
    start_i = next((i for i, t in enumerate(ts) if t >= setup.c2_ts), len(ts))
    for i in range(start_i, len(c)):
        if lo[i] <= low_so_far:
            low_so_far = lo[i]
            end = i if c[i] < o[i] else i - 1  # the run of down closes that made this low
            start = end
            while start - 1 >= 0 and c[start - 1] < o[start - 1]:
                start -= 1
            level = o[start] if end >= 0 and c[end] < o[end] else level
        if ts[i] >= setup.c2_close and lo[i] < eq:
            eq_broken = True
        ready = not_before is None or close_ts[i] >= not_before
        if level is not None and low_so_far < c1 and c[i] > level and ready:
            return Cisd(
                ts=ts[i],
                confirmed_at=close_ts[i],
                level=sign * level,
                protected=sign * low_so_far,
                early=close_ts[i] < setup.c2_close,
                eq_broken=eq_broken,
            )
    return None
