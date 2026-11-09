from datetime import date, datetime

import polars as pl
import pytest

from apollo.context.collect import collect_context
from apollo.context.fetch import fetch_events, fetch_vol, normalise_events

RAW = pl.DataFrame(
    {
        "date": [
            datetime(2024, 12, 12, 8, 30),
            datetime(2024, 12, 12, 8, 30),
            datetime(2024, 12, 12, 8, 30),
            datetime(2024, 12, 19, 14, 0),
            datetime(2025, 7, 4, 7, 30),
            datetime(2025, 7, 4, 7, 30),
            datetime(2024, 12, 12, 9, 0),
        ],
        "country": ["United States"] * 6 + ["Germany"],
        "event": [
            "CPI",
            "Core CPI",
            "Core CPI Index",
            "Fed Interest Rate Decision",
            "Nonfarm Payrolls",
            "Private Nonfarm Payrolls",
            "CPI",
        ],
    }
)
VOL3 = pl.DataFrame(
    {
        "date": [date(2026, 11, 4), date(2026, 11, 5), date(2026, 11, 6)],
        "vix": [20.0, 21.0, 22.0],
        "vix3m": [21.0, 21.5, 22.5],
        "vxn": [25.0, 26.0, 27.0],
    }
)


def test_normalise_shifts_and_dedupes():
    out = normalise_events(RAW)
    assert out.select("date", "kind").rows() == [
        (date(2024, 12, 11), "cpi"),
        (date(2024, 12, 18), "fomc"),
        (date(2025, 7, 3), "nfp"),
    ]


def test_collect_keeps_cache_when_provider_fails(tmp_path):
    collect_context(
        tmp_path,
        date(2026, 11, 9),
        fetch_vol=lambda s: VOL3,
        fetch_events=lambda s, e: normalise_events(RAW),
    )

    def boom(*a):
        raise ConnectionError("cboe down")

    counts = collect_context(tmp_path, date(2026, 11, 10), fetch_vol=boom, fetch_events=boom)
    assert counts == {"vol": 3, "events": 3}
    assert pl.read_parquet(tmp_path / "context" / "vol.parquet").height == 3


def test_events_merge_with_cache(tmp_path):
    first = normalise_events(RAW)
    collect_context(
        tmp_path, date(2026, 11, 9), fetch_vol=lambda s: VOL3, fetch_events=lambda s, e: first
    )
    new = pl.DataFrame(
        {"date": [date(2026, 12, 9)], "kind": ["fomc"], "event": ["Fed Interest Rate Decision"]}
    )
    counts = collect_context(
        tmp_path, date(2026, 11, 10), fetch_vol=lambda s: VOL3, fetch_events=lambda s, e: new
    )
    assert counts["events"] == 4


@pytest.mark.network
def test_live_calendar_matches_known_release_dates():
    got = set(fetch_events(date(2024, 11, 1), date(2025, 7, 10)).select("date", "kind").rows())
    known = [
        (date(2024, 12, 11), "cpi"),
        (date(2025, 6, 11), "cpi"),
        (date(2025, 7, 3), "nfp"),
        (date(2024, 11, 7), "fomc"),
        (date(2024, 12, 18), "fomc"),
        (date(2025, 1, 29), "fomc"),
    ]
    missing = [k for k in known if k not in got]
    assert not missing, missing


@pytest.mark.network
def test_live_vol_has_history():
    v = fetch_vol(date(2019, 1, 1))
    assert (
        v.height > 1800
        and v["vix"].null_count() == 0
        and v.columns == ["date", "vix", "vix3m", "vxn"]
    )


@pytest.mark.network
def test_live_other_kinds_present():
    ev = fetch_events(date(2025, 5, 26), date(2025, 6, 30))
    names = set(ev.filter(pl.col("kind") == "other")["event"])
    assert {"PCE Prices", "GDP", "ISM Manufacturing PMI", "Retail Sales"} & names


def test_chunks_with_date_or_datetime_columns_combine():
    import pandas as pd

    from apollo.context.fetch import _chunk

    a = pd.DataFrame(
        {"country": ["United States"], "event": ["CPI"]},
        index=pd.Index([pd.Timestamp("2024-12-12 08:30")], name="date"),
    )
    b = pd.DataFrame(
        {"country": ["United States"], "event": ["GDP"]},
        index=pd.Index([date(2025, 1, 31)], name="date"),
    )
    both = pl.concat([_chunk(a), _chunk(b)])
    assert both.schema["date"] == pl.Datetime("us") and both.height == 2


def test_payrolls_first_friday_with_listed_dates_winning():
    from apollo.context.fetch import with_payrolls

    listed = pl.DataFrame(
        {"date": [date(2025, 7, 3)], "kind": ["nfp"], "event": ["Nonfarm Payrolls"]}
    )
    out = with_payrolls(listed, date(2025, 6, 1), date(2025, 8, 31))
    nfp = out.filter(pl.col("kind") == "nfp")["date"].to_list()
    assert nfp == [
        date(2025, 6, 6),
        date(2025, 7, 3),
        date(2025, 8, 1),
    ]  # July moved for the holiday
