"""Point-in-time market context per session (spec 5.14).

Volatility comes from the last close dated before the session. Releases count on the day they
are scheduled, which is public well ahead of time.
"""

import polars as pl

KINDS = ("fomc", "cpi", "nfp", "other")
CONTEXT_FEATURES = (
    "vix",
    "vix_chg5",
    "vix_term",
    "vxn",
    "vxn_vix",
    *(f"ev_{k}" for k in KINDS),
    "ev_any",
)


def context_features(
    sessions: pl.DataFrame, vol: pl.DataFrame, events: pl.DataFrame
) -> pl.DataFrame:
    v = vol.sort("date").with_columns(
        vix_chg5=(pl.col("vix") / pl.col("vix").shift(5)).log(),
        vix_term=pl.col("vix") / pl.col("vix3m"),
        vxn_vix=pl.col("vxn") / pl.col("vix"),
        # a close is usable from the next calendar day on
        usable=pl.col("date") + pl.duration(days=1),
    )
    s = sessions.select("date").sort("date")
    out = s.join_asof(
        v.select("usable", "vix", "vix_chg5", "vix_term", "vxn", "vxn_vix"),
        left_on="date",
        right_on="usable",
        strategy="backward",
    )
    flags = events.select("date", "kind").unique().with_columns(hit=pl.lit(1.0))
    wide = (
        flags.pivot(on="kind", index="date", values="hit")
        if flags.height
        else pl.DataFrame({"date": []}, schema={"date": pl.Date})
    )
    out = out.join(wide, on="date", how="left")
    for k in KINDS:
        col = f"ev_{k}"
        out = out.with_columns(
            (pl.col(k) if k in out.columns else pl.lit(None))
            .cast(pl.Float64)
            .fill_null(0.0)
            .alias(col)
        )
    out = out.with_columns(ev_any=pl.max_horizontal(*(f"ev_{k}" for k in KINDS)))
    return out.select("date", *CONTEXT_FEATURES)
