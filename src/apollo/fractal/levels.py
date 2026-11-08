"""Price levels the Fractal Model treats as points of interest."""

import polars as pl


def swing_points(df: pl.DataFrame) -> pl.DataFrame:
    """3-bar fractals. A swing at row i is only known once row i+1 has closed."""
    lo, hi = pl.col("low"), pl.col("high")
    flagged = df.with_row_index("idx").with_columns(
        is_low=(lo < lo.shift(1)) & (lo < lo.shift(-1)),
        is_high=(hi > hi.shift(1)) & (hi > hi.shift(-1)),
    )
    lows = flagged.filter("is_low").select("idx", kind=pl.lit("low"), level="low")
    highs = flagged.filter("is_high").select("idx", kind=pl.lit("high"), level="high")
    return (
        pl.concat([lows, highs])
        .with_columns(pl.col("idx").cast(pl.Int64), confirmed_idx=pl.col("idx").cast(pl.Int64) + 1)
        .sort("idx")
    )


def fair_value_gaps(df: pl.DataFrame) -> pl.DataFrame:
    """3-candle gaps, known when the third candle closes, with the row that first fills each."""
    high, low = df["high"].to_list(), df["low"].to_list()
    rows = []
    for k in range(2, df.height):
        if high[k - 2] < low[k]:
            bottom, top = high[k - 2], low[k]
            fill = next((j for j in range(k + 1, df.height) if low[j] <= bottom), None)
            rows.append((k, "bull", bottom, top, k, fill))
        if low[k - 2] > high[k]:
            bottom, top = high[k], low[k - 2]
            fill = next((j for j in range(k + 1, df.height) if high[j] >= top), None)
            rows.append((k, "bear", bottom, top, k, fill))
    schema = {
        "idx": pl.Int64,
        "kind": pl.Utf8,
        "bottom": pl.Float64,
        "top": pl.Float64,
        "confirmed_idx": pl.Int64,
        "filled_idx": pl.Int64,
    }
    return pl.DataFrame(rows, schema=schema, orient="row")
