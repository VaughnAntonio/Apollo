"""Walk one trade bar by bar. Shared by the backtest and the journal's auto-close, so both use
the same rules: a bar that touches the stop and the target is a stop, the breakeven stop moves
only from the bar after +1R, and a position is flat at the close of the last bar opening before
`flat_at` ET on the trade's session date.
"""

from collections.abc import Callable
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


def walk_trade(
    ts: list[datetime],
    close_ts: list[datetime],
    hi: list[float],
    lo: list[float],
    cl: list[float],
    k: int,
    session: date,
    entry: float,
    stop: float,
    target: float,
    sign: float,
    planned_pts: float,
    flat_at: time,
    breakeven: bool = False,
    on_bar: Callable[[int, float, float], None] | None = None,
    flat_ts: datetime | None = None,
) -> tuple[float | None, datetime | None, str]:
    """Return (exit price, exit time, reason). The reason is "open" when the bars run out first.

    `on_bar(i, worst, best)` runs on every bar the trade is open, before the exit checks.
    `flat_ts` replaces the session rule: the trade is flat at the first bar opening at or after it.
    """
    reached_1r = False
    for i in range(k, len(ts)):
        local = ts[i].astimezone(NY)
        if (
            ts[i] >= flat_ts
            if flat_ts is not None
            else local.date() != session or local.time() >= flat_at
        ):
            if i == k:  # the trade never had a bar inside the session
                return None, None, "open"
            return cl[i - 1], close_ts[i - 1], "flat"
        if reached_1r and breakeven and sign * (entry - stop) > 0:
            stop = entry
        worst, best = (lo[i], hi[i]) if sign > 0 else (hi[i], lo[i])
        if on_bar is not None:
            on_bar(i, worst, best)
        if sign * (worst - stop) <= 0:
            return stop, close_ts[i], "breakeven" if stop == entry else "stop"
        if sign * (best - target) >= 0:
            return target, close_ts[i], "target"
        if sign * (best - entry) >= planned_pts:
            reached_1r = True  # takes effect from the next bar
    return None, None, "open"
