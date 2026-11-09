"""Market context from OpenBB's keyless providers (spec 5.14).

Volatility indices come from Cboe and scheduled US releases from Nasdaq's economic calendar.
Nasdaq lists every US event one day late and mixes ET and CT times, so release dates here are
the listed date minus one day, and listed times are ignored.
"""

import os
from datetime import date, timedelta
from typing import Any

import polars as pl

EVENT_KINDS: dict[str, tuple[str, ...]] = {
    "fomc": ("Fed Interest Rate Decision",),
    "cpi": ("CPI", "Core CPI"),
    "nfp": ("Nonfarm Payrolls",),
    "other": (
        "PCE Prices",
        "Core PCE Prices",
        "GDP",
        "Retail Sales",
        "ISM Manufacturing PMI",
    ),
}
VOL_SYMBOLS = {"vix": "VIX", "vix3m": "VIX3M", "vxn": "VXN"}
CHUNK_DAYS = 28


def _obb() -> Any:  # OpenBB builds its menus at runtime, so they have no static types
    """OpenBB, imported on first use. The python.org macOS build ships without root certificates."""
    import certifi

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    from openbb import obb

    return obb


def normalise_events(raw: pl.DataFrame) -> pl.DataFrame:
    """US high-impact releases, one row per (release date, kind)."""
    names = {n.lower(): kind for kind, ns in EVENT_KINDS.items() for n in ns}
    return (
        raw.filter(pl.col("country").str.contains("United States"))
        .with_columns(kind=pl.col("event").str.to_lowercase().replace_strict(names, default=None))
        .drop_nulls("kind")
        .with_columns(date=pl.col("date").cast(pl.Date) - timedelta(days=1))
        .unique(["date", "kind"], keep="first", maintain_order=True)
        .select("date", "kind", "event")
        .sort("date", "kind")
    )


def _chunk(df) -> pl.DataFrame:
    """One calendar response as date-time, country, event. Some come back with plain dates."""
    return pl.from_pandas(df.reset_index()).select(
        pl.col("date").cast(pl.Datetime("us")),
        pl.col("country").cast(pl.Utf8),
        pl.col("event").cast(pl.Utf8),
    )


def _first_friday(year: int, month: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(4 - first.weekday()) % 7)


def with_payrolls(events: pl.DataFrame, start: date, end: date) -> pl.DataFrame:
    """Add a payrolls date for every month in [start, end].

    Nasdaq lists the headline payrolls release only a few times a year, so each month defaults to
    the BLS rule (first Friday). A date Nasdaq does list for that month replaces the rule's date,
    which covers holiday moves such as 2025-07-03.
    """
    listed = {(d.year, d.month): d for d in events.filter(pl.col("kind") == "nfp")["date"]}
    rows, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        d = listed.get((y, m), _first_friday(y, m))
        if start <= d <= end:
            rows.append((d, "nfp", "Nonfarm Payrolls"))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    nfp = pl.DataFrame(rows, schema=events.schema, orient="row")
    return pl.concat([events.filter(pl.col("kind") != "nfp"), nfp]).sort("date", "kind")


def fetch_vol(start: date) -> pl.DataFrame:
    """Daily closes of VIX, VIX3M and VXN since `start`, one row per date."""
    obb = _obb()
    out = None
    for col, symbol in VOL_SYMBOLS.items():
        df = obb.index.price.historical(symbol, provider="cboe", start_date=start.isoformat())
        part = pl.from_pandas(df.to_dataframe().reset_index()).select(
            pl.col("date").cast(pl.Date), pl.col("close").alias(col)
        )
        out = part if out is None else out.join(part, on="date", how="left")
    assert out is not None
    return out.sort("date")


def fetch_events(start: date, end: date) -> pl.DataFrame:
    """High-impact US releases with true dates in [start, end]."""
    obb = _obb()
    parts = []
    lo = start
    stop = end + timedelta(days=1)  # an event on `end` is listed on end + 1
    while lo <= stop:
        hi = min(lo + timedelta(days=CHUNK_DAYS - 1), stop)
        df = obb.economy.calendar(
            provider="nasdaq", start_date=lo.isoformat(), end_date=hi.isoformat()
        )
        parts.append(_chunk(df.to_dataframe()))
        lo = hi + timedelta(days=1)
    ev = with_payrolls(normalise_events(pl.concat(parts)), start, end)
    return ev.filter(pl.col("date").is_between(start, end))
