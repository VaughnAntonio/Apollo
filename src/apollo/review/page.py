"""Build a detection review page: every Fractal Model setup on real charts, with verdict buttons.

Run: python -m apollo.review.page --symbol MNQ --pairing D-1H --last 60
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import cast

import polars as pl

from apollo.fractal.model import PAIRINGS, Pairing, load_pair, run_model

TEMPLATE = Path(__file__).with_name("template.html")


def _load(root: Path, code: str, pairing: Pairing) -> tuple[pl.DataFrame, pl.DataFrame]:
    return load_pair(root, code, pairing)


def _unix(t: datetime | None) -> int | None:
    return int(t.timestamp()) if t is not None else None


def _bars(df: pl.DataFrame) -> list[dict]:
    return [
        {"time": _unix(t), "open": o, "high": h, "low": lo, "close": c}
        for t, o, h, lo, c in df.select("ts", "open", "high", "low", "close").iter_rows()
    ]


def build_page(
    root: Path, code: str, pairing: Pairing, last: int = 60, out_dir: Path = Path("review")
) -> Path:
    """Write review/<code>_<pairing>.html for the latest `last` setups and return its path."""
    htf, ltf = _load(root, code, pairing)
    setups = run_model(root, code, pairing, htf=htf, ltf=ltf).tail(last)
    if setups.height:
        first = setups["c1_ts"].min()
        htf_view = htf.filter(pl.col("ts") >= first - (setups["c2_close"][0] - first) * 40)  # type: ignore[operator]
        ltf_view = ltf.filter(pl.col("ts") >= first)
    else:
        htf_view, ltf_view = htf.tail(200), ltf.tail(0)
    rows = [
        {k: _unix(v) if isinstance(v, datetime) else v for k, v in r.items()}
        for r in setups.iter_rows(named=True)
    ]
    data = {
        "code": code,
        "pairing": pairing,
        "htf_interval": PAIRINGS[pairing][0],
        "ltf_interval": PAIRINGS[pairing][1],
        "generated": datetime.now().astimezone().isoformat(timespec="minutes"),
        "htf": _bars(htf_view),
        "ltf": _bars(ltf_view),
        "setups": rows,
    }
    html = TEMPLATE.read_text().replace("/*__DATA__*/", json.dumps(data, separators=(",", ":")))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{code}_{pairing}.html"
    path.write_text(html)
    return path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default="data_store", type=Path)
    p.add_argument("--symbol", default="MNQ")
    p.add_argument("--pairing", default="D-1H", choices=list(PAIRINGS))
    p.add_argument("--last", default=60, type=int)
    try:
        a = p.parse_args(argv)
    except SystemExit as e:  # argparse exits on bad input; return its code instead
        return int(e.code or 0)
    path = build_page(a.root, a.symbol, cast(Pairing, a.pairing), a.last)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
