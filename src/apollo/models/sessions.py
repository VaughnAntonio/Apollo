"""One row per New York session, the unit the regime and range models forecast.

v1 session: 09:00 to 16:00 ET, the seven hourly bars that open 09:00 to 15:00. Yahoo's hourly
bars sit on the hour, so 09:30 is not available over the two-year history.
"""

import polars as pl

from apollo.config import Symbol
from apollo.data.rolls import mark_roll_days
from apollo.data.sessions import add_session_columns

LABELS = ("trend_up", "trend_down", "chop", "normal")
FULL_SESSION = 7


def build_sessions(h1: pl.DataFrame, sym: Symbol) -> pl.DataFrame:
    """Session OHLC, label (case-study body-ratio rule), excursions from the open and roll flag."""
    bars = mark_roll_days(add_session_columns(h1.sort("ts")), sym).filter(
        (pl.col("ts_et").dt.weekday() <= 5) & pl.col("ts_et").dt.hour().is_between(9, 15)
    )
    s = (
        bars.group_by(date=pl.col("ts_et").dt.date(), maintain_order=True)
        .agg(
            open=pl.col("open").first(),
            high=pl.col("high").max(),
            low=pl.col("low").min(),
            close=pl.col("close").last(),
            bars=pl.len(),
            near_roll=pl.col("near_roll").any(),
        )
        .sort("date")
    )
    body = (pl.col("close") - pl.col("open")).abs()
    ratio = pl.when(pl.col("high") > pl.col("low")).then(body / (pl.col("high") - pl.col("low")))
    label = (
        pl.when(pl.col("bars") < FULL_SESSION)
        .then(None)
        .when((ratio > 0.6) & (pl.col("close") > pl.col("open")))
        .then(pl.lit("trend_up"))
        .when((ratio > 0.6) & (pl.col("close") < pl.col("open")))
        .then(pl.lit("trend_down"))
        .when(ratio < 0.3)
        .then(pl.lit("chop"))
        .otherwise(pl.lit("normal"))
    )
    nine_et = (pl.col("date").cast(pl.Datetime("us")) + pl.duration(hours=9)).dt.replace_time_zone(
        "America/New_York"
    )
    return s.with_columns(
        forecast_at=nine_et.dt.convert_time_zone("UTC"),
        body_ratio=ratio,
        label=label,
        up_exc=pl.col("high") - pl.col("open"),
        down_exc=pl.col("open") - pl.col("low"),
    )
