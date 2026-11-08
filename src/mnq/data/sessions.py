import polars as pl

ET = "America/New_York"


def add_session_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Add ET time, the CME Globex trading date and New York regular-session flags.

    A Globex day runs 18:00 ET to 17:00 ET, so anything from 18:00 ET belongs to the next date.
    The regular session (RTH) is 09:30 to 16:00 ET, Monday to Friday.
    """
    et = pl.col("ts").dt.convert_time_zone(ET)
    minutes = et.dt.hour().cast(pl.Int32) * 60 + et.dt.minute().cast(pl.Int32)
    is_rth = (minutes >= 9 * 60 + 30) & (minutes < 16 * 60) & (et.dt.weekday() <= 5)
    return df.with_columns(
        ts_et=et,
        globex_date=pl.when(et.dt.hour() >= 18)
        .then(et.dt.date().dt.offset_by("1d"))
        .otherwise(et.dt.date()),
        is_rth=is_rth,
        ny_date=pl.when(is_rth).then(et.dt.date()),
    )
