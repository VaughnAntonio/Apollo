from apollo.fractal.config import load_fractal_config
from apollo.fractal.levels import fair_value_gaps, swing_points


def test_swing_low_needs_next_bar(ohlc):
    df = ohlc([(10, 11, 9, 10), (10, 10.5, 8, 9), (9, 10, 8.5, 9.5)])
    s = swing_points(df).filter(kind="low")
    assert s.select("idx", "level", "confirmed_idx").rows() == [(1, 8.0, 2)]
    assert swing_points(df.head(2)).filter(kind="low").height == 0


def test_bull_fvg_and_fill(ohlc):
    rows = [
        (10, 11, 9.5, 10.8),
        (10.8, 13, 10.7, 12.9),
        (12.9, 14, 12, 13.5),
        (13.5, 13.6, 10.9, 11),
    ]
    g = fair_value_gaps(ohlc(rows)).filter(kind="bull")
    assert g.select("idx", "bottom", "top", "filled_idx").rows() == [(2, 11.0, 12.0, 3)]


def test_config_defaults():
    cfg = load_fractal_config()
    assert (cfg.sweep_ticks, cfg.poi_lookback, cfg.poi_kinds, cfg.outside_bar) == (
        1,
        20,
        ("swing", "fvg"),
        "skip",
    )
