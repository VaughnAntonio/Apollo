"""Turn Fractal Model setups into candidate trades (spec 5.6), each with a skip reason or none.

Only the CISD that confirms after C2 has closed is traded; the fill is the open of the next
lower-timeframe bar, which is what a live order would get.

On the Daily -> 1H layer most CISDs confirm as the daily C2 closes at 17:00 ET, outside the New
York session. Those are entered at the next session open instead, the way a day trader would
take them, as long as price hasn't reached the stop or the target in between and the setup's C3
day is still running (its window_end).
"""

from datetime import time
from typing import Any, Literal
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

from apollo.config import Symbol
from apollo.strategy.config import TradeConfig, Variant

NY = ZoneInfo("America/New_York")
FOMC_CUTOFF = time(13, 30)
SKIP_REASONS = (
    "no_cisd",
    "outside_window",
    "invalidated",
    "no_forecast",
    "regime",
    "range_room",
    "rr",
    "stop_too_tight",
    "stop_too_wide",
    "fomc_cutoff",
)
SCHEMA = {
    "setup_ts": pl.Datetime("us", "UTC"),
    "direction": pl.Utf8,
    "signal_ts": pl.Datetime("us", "UTC"),
    "entry_ts": pl.Datetime("us", "UTC"),
    "session": pl.Date,
    "entry": pl.Float64,
    "stop": pl.Float64,
    "target": pl.Float64,
    "target_capped": pl.Boolean,
    "rr": pl.Float64,
    "planned_stop_pts": pl.Float64,
    "half_size": pl.Boolean,
    "skip": pl.Utf8,
}


def _zone(f: dict[str, Any] | None) -> tuple[float, float, float] | None:
    """(open, up_bound, down_bound) of the session's range forecast, if there is one."""
    if (
        f is None
        or f.get("open") is None
        or f.get("up_bound") is None
        or f.get("down_bound") is None
    ):
        return None
    return float(f["open"]), float(f["up_bound"]), float(f["down_bound"])


def build_candidates(
    setups: pl.DataFrame,
    ltf: pl.DataFrame,
    forecasts: pl.DataFrame,
    sym: Symbol,
    cfg: TradeConfig,
    variant: Variant,
    layer: Literal["D-1H", "1H-5m"],
) -> pl.DataFrame:
    bars = ltf.sort("ts")
    bar_ts = bars["ts"].to_list()
    stamps = np.array([t.timestamp() for t in bar_ts])
    opens, highs, lows = bars["open"].to_list(), bars["high"].to_list(), bars["low"].to_list()
    can_defer = layer == "D-1H" and "window_end" in setups.columns
    fc: dict[Any, dict[str, Any]] = {r["date"]: r for r in forecasts.iter_rows(named=True)}
    win_lo, win_hi = cfg.windows[layer]
    tick = sym.tick_size
    rows = []

    for s in setups.iter_rows(named=True):
        bull = s["direction"] == "bull"
        row = dict.fromkeys(SCHEMA)
        row |= {
            "setup_ts": s["c2_ts"],
            "direction": s["direction"],
            "half_size": False,
            "target_capped": False,
        }
        sig = s["after_c2_cisd_ts"]
        if sig is None:
            rows.append(row | {"skip": "no_cisd"})
            continue
        row["signal_ts"] = sig
        k = int(np.searchsorted(stamps, sig.timestamp(), side="right"))  # the bar after the signal
        if k >= len(bar_ts):
            rows.append(row | {"skip": "outside_window"})
            continue

        def in_window(j: int) -> bool:
            t = bar_ts[j].astimezone(NY)
            return t.weekday() < 5 and win_lo <= t.time() < win_hi

        same_day = bar_ts[k].astimezone(NY).date() == sig.astimezone(NY).date()
        if not (same_day and in_window(k)):
            j = next((j for j in range(k, len(bar_ts)) if in_window(j)), None)
            limit = s.get("window_end") if can_defer else None
            if j is None or limit is None or bar_ts[j] >= limit:
                rows.append(row | {"skip": "outside_window"})
                continue
            # deferred to the next session open: still valid only if nothing was hit meanwhile
            stop0 = s["after_c2_protected"] - (1 if bull else -1) * cfg.stop_ticks_beyond * tick
            target0 = s["c1_high"] if bull else s["c1_low"]
            hit = any(
                (lows[i] <= stop0 or highs[i] >= target0)
                if bull
                else (highs[i] >= stop0 or lows[i] <= target0)
                for i in range(k, j)
            )
            if hit:
                rows.append(row | {"entry_ts": bar_ts[j], "skip": "invalidated"})
                continue
            k = j
        entry_ts, entry = bar_ts[k], opens[k]
        local = entry_ts.astimezone(NY)
        row |= {"entry_ts": entry_ts, "entry": entry, "session": local.date()}

        f: dict[str, Any] | None = fc.get(local.date())
        zone = _zone(f)
        if (variant.regime and f is None) or (variant.range and zone is None):
            rows.append(row | {"skip": "no_forecast"})
            continue
        if variant.regime and f is not None:
            up, down = (
                (f["p_trend_up"], f["p_trend_down"])
                if bull
                else (f["p_trend_down"], f["p_trend_up"])
            )
            if not (f["p_chop"] < 0.5 and down < up):
                rows.append(row | {"skip": "regime"})
                continue

        sign = 1.0 if bull else -1.0
        stop = s["after_c2_protected"] - sign * cfg.stop_ticks_beyond * tick
        target = s["c1_high"] if bull else s["c1_low"]
        width = zone[1] + zone[2] if zone else None
        if variant.range and zone is not None and width is not None:
            opn, up_b, down_b = zone
            edge = opn + up_b if bull else opn - down_b
            past = sign * (target - edge)
            if past > cfg.range_room * width:
                rows.append(row | {"stop": stop, "target": target, "skip": "range_room"})
                continue
            if past > 0:
                target, row["target_capped"] = edge, True

        risk = sign * (entry - stop)
        rr = sign * (target - entry) / risk if risk > 0 else float("-inf")
        row |= {"stop": stop, "target": target, "rr": rr, "planned_stop_pts": risk}
        if rr < cfg.min_rr:
            rows.append(row | {"skip": "rr"})
            continue
        if variant.risk_rules and round(risk / tick, 6) < cfg.min_stop_ticks:
            rows.append(row | {"skip": "stop_too_tight"})
            continue
        if variant.risk_rules and width is not None and risk > cfg.max_stop_zone_frac * width:
            rows.append(row | {"skip": "stop_too_wide"})
            continue
        if (
            variant.fomc_cutoff
            and f is not None
            and f["ev_fomc"] == 1.0
            and local.time() >= FOMC_CUTOFF
        ):
            rows.append(row | {"skip": "fomc_cutoff"})
            continue
        row["half_size"] = bool(variant.event_half and f is not None and f["ev_any"] == 1.0)
        rows.append(row)
    return pl.DataFrame(rows, schema=SCHEMA)
