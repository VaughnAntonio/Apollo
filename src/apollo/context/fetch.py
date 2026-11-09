"""Market context from OpenBB's keyless providers (spec 5.14).

Volatility indices come from Cboe and scheduled US releases from Nasdaq's economic calendar.
Nasdaq lists every US event one day late and mixes ET and CT times, so release dates here are
the listed date minus one day, and listed times are ignored.
"""

import logging
import os
import tomllib
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import polars as pl

from apollo.config import CONFIG_DIR

log = logging.getLogger(__name__)

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


def payroll_dates(path: Path = CONFIG_DIR / "payrolls.toml") -> list[date]:
    """Official BLS Employment Situation release dates, kept in config/payrolls.toml."""
    return [date.fromisoformat(d) for d in tomllib.loads(path.read_text())["dates"]]


def with_payrolls(events: pl.DataFrame, start: date, end: date) -> pl.DataFrame:
    """Replace Nasdaq's payrolls rows with the BLS schedule.

    Nasdaq lists the headline release only a few times a year, and no simple rule gets the dates
    right (2024-03-08, 2025-01-10 and 2026-01-09 are not first Fridays; October 2025 had none).
    """
    table = payroll_dates()
    if end > table[-1]:
        log.warning("config/payrolls.toml ends %s; add the next BLS dates", table[-1])
    rows = [(d, "nfp", "Nonfarm Payrolls") for d in table if start <= d <= end]
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
