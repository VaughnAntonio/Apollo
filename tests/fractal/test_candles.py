from apollo.fractal.candles import detect_c2
from apollo.fractal.config import load_fractal_config

CFG = load_fractal_config()
TICK = 0.25
# Rows are (open, high, low, close). Row 1 is a swing low at 95 and row 3 is C1, so a row 4
# that trades below 96.5 and 95, then closes back above 96.5, is a bullish C2 at a swing.
BASE = [(100, 101, 98, 99), (99, 99.5, 95, 97), (97, 100, 96, 99.5), (99.5, 100, 96.5, 97.5)]


def mirror(rows):
    return [(200 - o, 200 - lo, 200 - h, 200 - c) for o, h, lo, c in rows]


def test_bullish_c2_at_swing(ohlc):
    setups, skipped = detect_c2(
        ohlc(BASE + [(97.5, 99, 94.5, 98.5), (98.5, 102, 98, 101)]), "1h", TICK, CFG
    )
    (s,) = setups
    assert (s.direction, s.c1_idx, s.c2_idx, s.poi_kind, s.poi_level) == (
        "bull",
        3,
        4,
        "swing",
        95.0,
    )
    assert s.eq == (94.5 + 97.5) / 2 and s.c3_closed is True and skipped == 0
    assert (s.c1_low, s.c1_high, s.c2_low, s.c2_high) == (96.5, 100.0, 94.5, 99.0)


def test_bearish_mirror(ohlc):
    rows = mirror(BASE + [(97.5, 99, 94.5, 98.5), (98.5, 102, 98, 101)])
    (s,) = detect_c2(ohlc(rows), "1h", TICK, CFG)[0]
    assert (s.direction, s.poi_level, s.c3_closed) == ("bear", 105.0, True)


def test_no_poi_no_setup(ohlc):
    rows = [(100, 101, 98, 99), (99, 100, 97, 99.5), (99.5, 100, 96.5, 97.5), (97.5, 99, 96, 98.5)]
    assert detect_c2(ohlc(rows), "1h", TICK, CFG)[0] == []


def test_equal_low_is_not_a_sweep(ohlc):
    assert detect_c2(ohlc(BASE + [(97.5, 99, 96.5, 98.5)]), "1h", TICK, CFG)[0] == []


def test_outside_bar_skipped_and_counted(ohlc):
    setups, skipped = detect_c2(ohlc(BASE + [(97.5, 100.5, 94.5, 98)]), "1h", TICK, CFG)
    assert setups == [] and skipped == 1


def test_c3_pending_on_last_bar(ohlc):
    (s,) = detect_c2(ohlc(BASE + [(97.5, 99, 94.5, 98.5)]), "1h", TICK, CFG)[0]
    assert s.c3_closed is None


def test_fvg_poi(ohlc):
    # Rows 0-2 leave a bull gap 96..97.5; row 4 sweeps C1 (row 3) into the gap.
    rows = [
        (95, 96, 94, 95.8),
        (95.8, 99, 95.7, 98.8),
        (98.8, 99.5, 97.5, 99),
        (99, 99.2, 98, 98.2),
    ]
    (s,) = detect_c2(ohlc(rows + [(98.2, 98.6, 97.2, 98.4)]), "1h", TICK, CFG)[0]
    assert (s.poi_kind, s.poi_level) == ("fvg", 97.5)


def test_one_tick_stock_sweep_with_float_prices(ohlc):
    # 1.13 - 0.01 is 1.1199999... in floats; a one-tick sweep to 1.12 must still count.
    rows = [
        (1.20, 1.21, 1.16, 1.18),
        (1.18, 1.19, 1.125, 1.15),  # swing low 1.125
        (1.15, 1.20, 1.14, 1.19),
        (1.19, 1.20, 1.13, 1.15),  # C1
        (1.15, 1.17, 1.12, 1.16),  # C2 sweeps 1.13 by one tick
    ]
    setups = detect_c2(ohlc(rows), "1h", 0.01, CFG)[0]
    assert [s.c2_idx for s in setups] == [4]


def test_stock_daily_close_is_six_and_a_half_hours(ohlc):
    rows = BASE + [(97.5, 99, 94.5, 98.5)]
    (s,) = detect_c2(ohlc(rows, "2026-11-02 09:30", "1d"), "1d", TICK, CFG, kind="stock")[0]
    assert (s.c2_close - s.c2_ts).total_seconds() == 6.5 * 3600
