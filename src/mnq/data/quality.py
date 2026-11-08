import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from itertools import pairwise
from typing import Literal
from zoneinfo import ZoneInfo

import polars as pl

from mnq.data.sessions import ET, add_session_columns
from mnq.data.yahoo import Interval

TZ = ZoneInfo(ET)
MINUTES = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "1d": 1440}


@dataclass
class QualityReport:
    symbol: str
    interval: str
    rows: int
    duplicates: int
    gaps: list[tuple[str, str]] = field(default_factory=list)
    bad_ticks: list[str] = field(default_factory=list)
    bad_days: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def _is_open(t: datetime, kind: str) -> bool:
    """True when the market trades at ET time `t` (ignores holidays)."""
    t = t.astimezone(TZ)
    wd, hm = t.weekday(), t.hour * 60 + t.minute
    if kind == "stock":
        return wd < 5 and 570 <= hm < 960
    if wd == 5:  # Saturday
        return False
    if wd == 6:  # Sunday opens 18:00
        return hm >= 1080
    if wd == 4:  # Friday closes 17:00
        return hm < 1020
    return not 1020 <= hm < 1080  # daily break 17:00 to 18:00


def _slots(start: datetime, end: datetime, step: timedelta, kind: str) -> list[datetime]:
    """Bar start times in [start, end) when the market is open."""
    out, t = [], start
    while t < end:
        if _is_open(t, kind):
            out.append(t)
        t += step
    return out


def check_quality(
    df: pl.DataFrame, interval: Interval, kind: Literal["future", "stock"] = "future"
) -> QualityReport:
    """Report duplicates, holes during trading hours, bad ticks and sparse days."""
    df = df.sort("ts")
    sym = df["symbol"][0] if df.height else ""
    report = QualityReport(sym, interval, df.height, df.height - df["ts"].n_unique())
    if df.is_empty():
        return report

    prev = pl.col("close").shift(1)
    tr = pl.max_horizontal(
        pl.col("high") - pl.col("low"), (pl.col("high") - prev).abs(), (pl.col("low") - prev).abs()
    )
    atr = tr.rolling_mean(14).shift(1)  # ATR of the bars before, so a spike can't hide itself
    ticks = df.filter((pl.col("close") - prev).abs() > 8 * atr)["ts"]
    report.bad_ticks = [t.isoformat() for t in ticks]

    if interval == "1d":
        return report
    step = timedelta(minutes=MINUTES[interval])
    ts = df["ts"].to_list()
    for a, b in pairwise(ts):
        if b - a > 2 * step and _slots(a + step, b, step, kind):
            report.gaps.append(((a + step).isoformat(), b.isoformat()))

    s = add_session_columns(df)
    for d, n in s.group_by("globex_date").len().sort("globex_date").iter_rows():
        if kind == "stock":
            lo = datetime(d.year, d.month, d.day, 9, 30, tzinfo=TZ)
            hi = lo.replace(hour=16, minute=0)
        else:
            hi = datetime(d.year, d.month, d.day, 17, tzinfo=TZ)
            lo = hi - timedelta(hours=23)
        expected = len(_slots(lo, hi, step, kind))
        if expected and n < 0.8 * expected:
            report.bad_days.append(d.isoformat())
    return report
