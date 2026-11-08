from datetime import date, timedelta

import polars as pl

from apollo.config import Symbol


def _third_friday(year: int, month: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(4 - first.weekday()) % 7 + 14)


def roll_windows(start: date, end: date) -> list[tuple[date, date]]:
    """Quarterly equity-index roll windows: third Friday minus 8 days, to the third Friday."""
    out = []
    for year in range(start.year, end.year + 1):
        for month in (3, 6, 9, 12):
            expiry = _third_friday(year, month)
            if start <= expiry <= end:
                out.append((expiry - timedelta(days=8), expiry))
    return out


def mark_roll_days(df: pl.DataFrame, sym: Symbol) -> pl.DataFrame:
    """Add `near_roll`: true on Globex dates inside a roll window. Needs `globex_date`."""
    if sym.roll_rule == "none" or df.is_empty():
        # shortcut: MGC and MCL roll monthly and are not modelled in v1; add their calendars
        # when those symbols get models.
        return df.with_columns(near_roll=pl.lit(False))
    d = df["globex_date"]
    flag = pl.lit(False)
    for lo, hi in roll_windows(d.min(), d.max() + timedelta(days=8)):  # type: ignore[operator]
        flag = flag | pl.col("globex_date").is_between(lo, hi)
    return df.with_columns(near_roll=flag)
