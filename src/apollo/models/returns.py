"""Hourly log returns with the contract-roll jump removed.

Yahoo's continuous `=F` series switches to the next contract once a quarter, which shows up as
one large fake return. Inside each roll window, the single largest move is treated as that jump
when it is more than five times the window's median move, and set to zero.
"""

import polars as pl

from apollo.config import Symbol
from apollo.data.rolls import roll_windows

JUMP_MULTIPLE = 5


def clean_returns(h1: pl.DataFrame, sym: Symbol) -> pl.DataFrame:
    df = h1.sort("ts").with_columns(
        ret=(pl.col("close") / pl.col("close").shift(1)).log().fill_null(0.0),
        et_date=pl.col("ts").dt.convert_time_zone("America/New_York").dt.date(),
        roll_jump=pl.lit(False),
    )
    if sym.roll_rule == "none" or df.is_empty():
        return df.drop("et_date")
    for lo, hi in roll_windows(df["et_date"].min(), df["et_date"].max()):  # type: ignore[arg-type]
        inside = pl.col("et_date").is_between(lo, hi)
        window = df.filter(inside)
        if window.height < 2:
            continue
        size = window["ret"].abs()
        biggest = size.max()
        if biggest > JUMP_MULTIPLE * size.median():  # type: ignore[operator]
            at = window["ts"][int(size.arg_max() or 0)]
            df = df.with_columns(roll_jump=pl.col("roll_jump") | (pl.col("ts") == at))
    return df.with_columns(
        ret=pl.when(pl.col("roll_jump")).then(0.0).otherwise(pl.col("ret"))
    ).drop("et_date")
