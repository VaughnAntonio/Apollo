import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from apollo.config import CONFIG_DIR


@dataclass(frozen=True)
class FractalConfig:
    sweep_ticks: int
    poi_lookback: int
    poi_kinds: tuple[str, ...]
    outside_bar: Literal["skip"]


def load_fractal_config(path: Path = CONFIG_DIR / "strategy.toml") -> FractalConfig:
    raw = tomllib.loads(path.read_text())["fractal"]
    return FractalConfig(
        sweep_ticks=raw["sweep_ticks"],
        poi_lookback=raw["poi_lookback"],
        poi_kinds=tuple(raw["poi_kinds"]),
        outside_bar=raw["outside_bar"],
    )
