import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


@dataclass(frozen=True)
class Symbol:
    code: str
    yahoo: str
    name: str
    kind: Literal["future", "stock"]
    point_value: float
    tick_size: float
    roll_rule: Literal["equity_index_quarterly", "none"]
    model_enabled: bool


def load_symbols(path: Path = CONFIG_DIR / "symbols.toml") -> dict[str, Symbol]:
    """Load symbols in file order, keyed by code."""
    rows = tomllib.loads(path.read_text())["symbol"]
    return {r["code"]: Symbol(**r) for r in rows}
