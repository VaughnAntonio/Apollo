# Apollo Predictor, Plan 2 of 7: Fractal Model Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect the TTrades Fractal Model mechanically on stored bars
(C1/C2/C3, points of interest, EQ, lower-timeframe CISD) and publish a review
page where Vaughn checks every detection on real MNQ charts and marks it
right or wrong.

**Architecture:**
- A new `apollo.fractal` package of pure Polars functions:
  - `levels`: swing points and fair value gaps;
  - `candles`: C2/C3 detection;
  - `cisd`: lower-timeframe confirmation;
  - `model`: the pipeline across a timeframe pairing.
- All rule values live in `config/strategy.toml`.
- A small `apollo.review` module writes one self-contained HTML page per
  symbol and pairing: TradingView Lightweight Charts from a CDN, the data
  embedded as JSON, and no server.

**Tech Stack:** Python 3.13, Polars, tomllib, lightweight-charts 4.2.0
(browser CDN script, not a Python dependency). No new Python dependencies.

**Spec:** `docs/superpowers/specs/2026-11-08-apollo-predictor-design.md`
(section 5.6 terms, pairings and entry rules; section 9 review gate; 5.2
tokens for the page).

## Global Constraints

- **No lookahead.** `ts` is a bar's open time; a bar is known only at its
  close.
  - Daily futures bar: close = ts + 23h.
  - 4H bar: close = ts + 4h, except the bucket opening 14:00 ET, which
    closes at 17:00 ET (3h).
  - Other bars: close = ts + interval.
  - A swing point or fair value gap is usable only after the bar that
    confirms it has closed.
- **Pairings, exactly:** `D-1H` (1d → 1h), `4H-15m` (4h built with
  `to_4h` from 1h → 15m), `1H-5m` (1h → 5m).
- **Ticks:** sweep threshold = `sweep_ticks × Symbol.tick_size`, default
  1 tick.
- Rules are **defaults Vaughn must review** (spec section 9). Every number
  goes in `config/strategy.toml` under `[fractal]`, never hard-coded.
- **Page look:** Portfoliov2 tokens from spec 5.2 (light `#e8eaec`/`#262933`,
  brand `#3d5a4a`, down `#a32d2d`; dark set as listed in the spec), Geist +
  Geist Mono, hairlines and no cards, light/dark/auto. Lightweight Charts
  script pinned at `https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js`.
  Load the `dataviz` skill before Task 5.
- **Prose** (docstrings, comments, page copy, commit messages): use the
  project's `humanizer` skill in embedded mode.
- Commit messages end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- No new dependencies. Ask Vaughn before any push.

## Review Focus

1. **An outside bar sweeps both C1's high and low and closes inside C1.** No
   setup is emitted for that bar (ambiguous direction); it is counted in
   `skipped_outside`. *(Pinned in Task 2.)*
2. **The C2 low exactly equals the C1 low, or undercuts it by less than one
   tick.** This is not a sweep, so no setup. *(Pinned in Task 2.)*
3. **A setup older than the stored LTF history** (5m and 15m only reach back
   about 60 days). The pipeline returns the setup with `ltf_missing=True`
   and null CISD fields; no crash. *(Pinned in Task 4.)*
4. **Appending future bars changes nothing already detected.** Running on a
   prefix of the data gives exactly the same rows for every setup whose C2
   closed inside the prefix. *(Pinned in Task 4.)*
5. **A new lower low prints after a CISD level was set, before confirmation.**
   The CISD level moves to the open of the new run; the old level can no
   longer confirm. *(Pinned in Task 3.)*

---

## File structure

```
config/strategy.toml               [fractal] defaults
src/apollo/data/yahoo.py           + bar_close(interval, kind) -> pl.Expr   (modify)
src/apollo/fractal/__init__.py
src/apollo/fractal/config.py       FractalConfig, load_fractal_config()
src/apollo/fractal/levels.py       swing_points(), fair_value_gaps()
src/apollo/fractal/candles.py      Setup, detect_c2()
src/apollo/fractal/cisd.py         Cisd, find_cisd()
src/apollo/fractal/model.py        PAIRINGS, run_model()
src/apollo/review/__init__.py
src/apollo/review/page.py          build_page(), main()  (python -m apollo.review.page)
src/apollo/review/template.html    the page; Python fills one JSON placeholder
tests/conftest.py                  + ohlc fixture   (modify)
tests/fractal/test_*.py, tests/review/test_page.py
```

---

### Task 1: Bar close times, config and levels (swings and FVGs)

**Files:**
- Modify: `src/apollo/data/yahoo.py`, `tests/conftest.py`
- Create: `config/strategy.toml`, `src/apollo/fractal/__init__.py`,
  `src/apollo/fractal/config.py`, `src/apollo/fractal/levels.py`
- Test: `tests/data/test_bar_close.py`, `tests/fractal/test_levels.py`

**Interfaces:**
- Consumes: `BAR_SCHEMA`, `_DURATION`, `ET` (Plan 1).
- Produces:
  - `bar_close(interval: Literal["5m","15m","1h","4h","1d"], kind:
    Literal["future","stock"] = "future") -> pl.Expr`: the bar's close time
    computed from `pl.col("ts")`.
  - `@dataclass(frozen=True) FractalConfig` with fields `sweep_ticks: int`,
    `poi_lookback: int`, `poi_kinds: tuple[str, ...]`,
    `outside_bar: Literal["skip"]`, and
    `load_fractal_config(path=CONFIG_DIR/"strategy.toml") -> FractalConfig`.
  - `swing_points(df) -> pl.DataFrame` with columns `idx` (row number in
    df), `kind` ("high"|"low"), `level`, `confirmed_idx` (= idx + 1).
  - `fair_value_gaps(df) -> pl.DataFrame` with columns `idx` (third
    candle), `kind` ("bull"|"bear"), `bottom`, `top`, `confirmed_idx`
    (= idx), `filled_idx` (first later row that fully fills it, else null).
  - Fixture `ohlc(rows: list[tuple[float,float,float,float]], start:
    str = "2026-11-02 18:00", every: str = "1h")`: a `BAR_SCHEMA` frame
    with the given open/high/low/close, symbol "MNQ".
- `config/strategy.toml`:
  ```toml
  [fractal]
  sweep_ticks = 1        # C2 must trade this many ticks beyond C1
  poi_lookback = 20      # HTF bars back to look for swings and gaps
  poi_kinds = ["swing", "fvg"]
  outside_bar = "skip"   # a bar that sweeps both sides is ambiguous
  ```
- **Definitions** (3-bar fractal and 3-candle gap, spec 5.6):
  - Swing low at i: `low[i] < low[i-1]` and `low[i] < low[i+1]`; the swing
    high mirrors it.
  - Bull FVG at k: `high[k-2] < low[k]`, giving the zone
    `[high[k-2], low[k]]`. It is filled at the first j > k with
    `low[j] <= high[k-2]`. The bear FVG mirrors it.

- [ ] **Step 1: Write the failing tests**

```python
# tests/data/test_bar_close.py
from apollo.data.yahoo import bar_close

def test_daily_future_closes_23h_later(bars):
    d = bars("2026-11-01 18:00", 1, "1d").with_columns(c=bar_close("1d"))
    assert str(d["c"][0]) == "2026-11-02 22:00:00+00:00"  # Mon 17:00 EST

def test_4h_last_bucket_is_3h(bars):
    h = bars("2026-11-02 14:00", 1, "1h").with_columns(c=bar_close("4h"))
    assert str(h["c"][0]) == "2026-11-02 22:00:00+00:00"  # 17:00 EST, not 18:00
```

```python
# tests/fractal/test_levels.py
from apollo.fractal.levels import fair_value_gaps, swing_points

def test_swing_low_needs_next_bar(ohlc):
    df = ohlc([(10, 11, 9, 10), (10, 10.5, 8, 9), (9, 10, 8.5, 9.5)])
    s = swing_points(df).filter(kind="low")
    assert s.select("idx", "level", "confirmed_idx").rows() == [(1, 8.0, 2)]
    assert swing_points(df.head(2)).filter(kind="low").height == 0

def test_bull_fvg_and_fill(ohlc):
    df = ohlc([(10, 11, 9.5, 10.8), (10.8, 13, 10.7, 12.9), (12.9, 14, 12, 13.5), (13.5, 13.6, 10.9, 11)])
    g = fair_value_gaps(df).filter(kind="bull")
    assert g.select("idx", "bottom", "top", "filled_idx").rows() == [(2, 11.0, 12.0, 3)]
```

- [ ] **Step 2:** Run `.venv/bin/pytest tests/data/test_bar_close.py tests/fractal -q`. Expected: FAIL with import errors.
- [ ] **Step 3:** Add `bar_close` to `yahoo.py`. Reuse `_DURATION` for the intraday intervals; add `"4h"`, with 3h when the ET open hour is 14; `"1d"` is 23h for futures and 6.5h for stocks. Make `drop_unfinished` use `bar_close`, so the two can't disagree. Write `config/strategy.toml`, `fractal/config.py` and `levels.py` (vectorised with `shift`). The fill search can loop over the gaps, since there are few.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`. Expected: everything passes, including Plan 1's `drop_unfinished` tests.
- [ ] **Step 5: Commit** `feat(fractal): bar close times, strategy config, swings and FVGs`.

---

### Task 2: C2 and C3 detection on the higher timeframe

**Files:**
- Create: `src/apollo/fractal/candles.py`
- Test: `tests/fractal/test_candles.py`

**Interfaces:**
- Consumes: `swing_points`, `fair_value_gaps`, `FractalConfig`,
  `bar_close`.
- Produces:
  - `@dataclass(frozen=True) class Setup` with fields:
    - `direction: Literal["bull","bear"]`;
    - `c1_idx: int`, `c2_idx: int`;
    - `c2_ts: datetime` (open), `c2_close: datetime`;
    - `c1_high: float`, `c1_low: float`, `c2_high: float`, `c2_low: float`;
    - `eq: float`;
    - `poi_kind: Literal["swing","fvg"]`, `poi_level: float` (swing level,
      or the FVG edge nearest to C1);
    - `c3_closed: bool | None` (None while C3 hasn't closed).
  - `detect_c2(htf: pl.DataFrame, interval: str, tick: float, cfg:
    FractalConfig) -> tuple[list[Setup], int]`: the setups in time order
    and `skipped_outside`.
- **Rules for bar j (C1 = j−1), bullish** (bearish mirrors):
  1. Sweep: `low[j] <= c1_low - sweep_ticks*tick`, and `close[j] > c1_low`.
  2. If `high[j] >= c1_high + sweep_ticks*tick` and close is inside
     `(c1_low, c1_high)`, it's an outside bar: skip it and count it.
  3. POI: among levels with `confirmed_idx <= j-1` and `idx >= j -
     poi_lookback`, either a swing low with `low[j] <= level <= c1_low`, or
     a bull FVG unfilled as of j−1 with `low[j] <= top` and `bottom <=
     c1_low`. Prefer a swing; use the most recent. No POI → no setup.
  4. `eq = (low[j] + min(open[j], close[j])) / 2`.
  5. `c3_closed = close[j+1] > high[j]` if row j+1 exists, else None.

- [ ] **Step 1: Write the failing tests** (rows are `(open, high, low, close)`; tick 0.25)

```python
from apollo.fractal.candles import detect_c2
from apollo.fractal.config import load_fractal_config

CFG = load_fractal_config()
# row 1 is a swing low at 95; row 3 = C1; row 4 sweeps C1's low and that swing, closes back inside
BASE = [(100, 101, 98, 99), (99, 99.5, 95, 97), (97, 100, 96, 99.5), (99.5, 100, 96.5, 97.5)]

def test_bullish_c2_at_swing(ohlc):
    df = ohlc(BASE + [(97.5, 99, 94.5, 98.5), (98.5, 102, 98, 101)])
    setups, skipped = detect_c2(df, "1h", 0.25, CFG)
    (s,) = setups
    assert (s.direction, s.c1_idx, s.c2_idx, s.poi_kind, s.poi_level) == ("bull", 3, 4, "swing", 95.0)
    assert s.eq == (94.5 + 97.5) / 2 and s.c3_closed is True and skipped == 0

def test_no_poi_no_setup(ohlc):
    rows = [(100, 101, 98, 99), (99, 100, 97, 99.5), (99.5, 100, 96.5, 97.5), (97.5, 99, 96, 98.5)]
    assert detect_c2(ohlc(rows), "1h", 0.25, CFG)[0] == []

def test_equal_low_is_not_a_sweep(ohlc):
    df = ohlc(BASE + [(97.5, 99, 96.5, 98.5)])
    assert detect_c2(df, "1h", 0.25, CFG)[0] == []

def test_outside_bar_skipped_and_counted(ohlc):
    df = ohlc(BASE + [(97.5, 100.5, 94.5, 98)])
    setups, skipped = detect_c2(df, "1h", 0.25, CFG)
    assert setups == [] and skipped == 1

def test_c3_pending_on_last_bar(ohlc):
    assert detect_c2(ohlc(BASE + [(97.5, 99, 94.5, 98.5)]), "1h", 0.25, CFG)[0][0].c3_closed is None
```

  Add `test_bearish_mirror`: the same rows mirrored around 100 (each price
  p becomes 200 − p, with high and low swapped) give one `"bear"` setup
  with `poi_level == 105.0`.
- [ ] **Step 2:** Run `.venv/bin/pytest tests/fractal/test_candles.py -q`. Expected: FAIL, import error.
- [ ] **Step 3:** Implement `detect_c2` as one pass over the rows. HTF frames are small (≤ 3,000 rows), so a plain loop is fine; leave a `# shortcut:` note.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5: Commit** `feat(fractal): C2 and C3 detection with POI and EQ`.

---

### Task 3: CISD on the lower timeframe

**Files:**
- Create: `src/apollo/fractal/cisd.py`
- Test: `tests/fractal/test_cisd.py`

**Interfaces:**
- Consumes: `Setup` (Task 2), `bar_close`.
- Produces:
  - `@dataclass(frozen=True) class Cisd` with fields `ts: datetime` (open
    of the confirming LTF bar), `confirmed_at: datetime` (its close),
    `level: float` (the run open crossed), `protected: float` (lowest low,
    or highest high for bear, up to confirmation), `early: bool`
    (confirmed_at < setup.c2_close), `eq_broken: bool`.
  - `find_cisd(ltf: pl.DataFrame, ltf_interval: str, setup: Setup,
    window_end: datetime) -> Cisd | None`.
- **Window:** LTF bars with `ts >= setup.c2_ts` and close `<= window_end`.
  The pipeline passes the close of C3 (or C2's close + one HTF bar when C3
  is missing).
- **Bullish algorithm** (bear mirrors):
  1. Walk the bars in order, keeping `low_so_far`.
  2. Whenever a bar prints a new low (`low <= low_so_far`), set the run: the
     maximal block of consecutive down-close bars (`close < open`) ending at
     that bar. If that bar closed up, use the block ending just before it.
     Set `level` = open of the run's first bar. With no down bar before it,
     there is no level yet.
  3. The first later bar with `close > level`, once `low_so_far <
     setup.c1_low` (the sweep has happened on the LTF), confirms the CISD.
  4. `eq_broken` = any bar after `setup.c2_close` and before confirmation
     with `low < setup.eq`.

- [ ] **Step 1: Write the failing tests** (5m rows from 2026-11-03 09:30 ET; setup built with `Setup(...)`, C1 low 100, C2 open 09:30, C2 close 10:30, eq 99.0)

```python
def test_bull_cisd_closes_above_run_open(ohlc, bull_setup):
    rows = [(101, 101.5, 100.2, 100.5), (100.5, 100.6, 99.5, 99.8), (99.8, 99.9, 98.8, 99.0),  # down run opens 101
            (99.0, 100.0, 98.9, 99.9), (99.9, 101.4, 99.8, 101.2)]                           # closes > 101
    c = find_cisd(ohlc(rows, "2026-11-03 09:30", "5m"), "5m", bull_setup, END)
    assert (c.level, c.protected, c.early, c.eq_broken) == (101.0, 98.8, True, False)
    assert str(c.ts) == "2026-11-03 14:50:00+00:00"

def test_new_low_resets_level(ohlc, bull_setup):
    rows = [(101, 101.5, 100.2, 100.5), (100.5, 100.6, 99.5, 99.8), (99.8, 100.4, 99.6, 100.3),  # up bar, level 101
            (100.3, 100.35, 99.0, 99.1), (99.1, 100.8, 99.05, 100.7)]                         # new low; level now 100.3
    c = find_cisd(ohlc(rows, "2026-11-03 09:30", "5m"), "5m", bull_setup, END)
    assert c.level == 100.3 and str(c.ts) == "2026-11-03 14:50:00+00:00"

def test_no_sweep_no_cisd(ohlc, bull_setup):
    rows = [(101, 101.5, 100.3, 100.5), (100.5, 102, 100.4, 101.8)]
    assert find_cisd(ohlc(rows, "2026-11-03 09:30", "5m"), "5m", bull_setup, END) is None
```

  Add the fixtures `bull_setup` and `END` (C3 close, 2026-11-03 11:30 ET) in
  `tests/fractal/conftest.py`. Add `test_eq_broken_after_c2_close`: a bar at
  10:35 ET with low 98.5 before confirmation gives `eq_broken is True` and
  `early is False`.
- [ ] **Step 2:** Run `.venv/bin/pytest tests/fractal/test_cisd.py -q`. Expected: FAIL, import error.
- [ ] **Step 3:** Implement `find_cisd` as a single loop over the window rows.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5: Commit** `feat(fractal): lower-timeframe CISD`.

---

### Task 4: The pipeline across a pairing

**Files:**
- Create: `src/apollo/fractal/model.py`
- Test: `tests/fractal/test_model.py`

**Interfaces:**
- Consumes: `read_bars`, `to_4h`, `add_session_columns`, `mark_roll_days`,
  `load_symbols`, `detect_c2`, `find_cisd`, `bar_close`.
- Produces:
  - `Pairing = Literal["D-1H","4H-15m","1H-5m"]`, and `PAIRINGS:
    dict[Pairing, tuple[str, str]]` = `{"D-1H": ("1d","1h"), "4H-15m":
    ("4h","15m"), "1H-5m": ("1h","5m")}`.
  - `run_model(root: Path, code: str, pairing: Pairing, htf: pl.DataFrame |
    None = None, ltf: pl.DataFrame | None = None) -> pl.DataFrame`, with
    frames injectable for tests. One row per setup, columns:
    - `code`, `pairing`, `direction`, `c1_ts`, `c2_ts`, `c2_close`;
    - `c1_high`, `c1_low`, `c2_high`, `c2_low`, `eq`;
    - `poi_kind`, `poi_level`, `c3_closed`, `near_roll`;
    - `ltf_missing`, `cisd_ts`, `cisd_confirmed_at`, `cisd_level`,
      `protected`, `early`, `eq_broken`;
    - `skipped_outside`: the outside-bar count from `detect_c2`, repeated
      on every row.
  - `ltf_missing` = true when the earliest LTF bar is later than `c2_ts`.

- [ ] **Step 1: Write the failing tests**

```python
def test_prefix_stability(ohlc_long):
    htf, ltf = ohlc_long  # fixture: 30 synthetic 1h bars + matching 5m bars with two setups
    full = run_model(Path("unused"), "MNQ", "1H-5m", htf=htf, ltf=ltf)
    cut = htf["ts"][20]
    part = run_model(Path("unused"), "MNQ", "1H-5m", htf=htf.filter(pl.col("ts") < cut),
                     ltf=ltf.filter(pl.col("ts") < cut))
    done = full.filter(pl.col("cisd_confirmed_at") < cut)
    volatile = ["c3_closed", "skipped_outside"]  # these legitimately change as bars arrive
    assert done.drop(volatile).equals(part.filter(pl.col("c2_ts").is_in(done["c2_ts"])).drop(volatile))

def test_ltf_missing_for_old_setup(ohlc_long):
    htf, ltf = ohlc_long
    out = run_model(Path("unused"), "MNQ", "1H-5m", htf=htf, ltf=ltf.filter(pl.col("ts") > htf["ts"][25]))
    old = out.filter(pl.col("c2_ts") < htf["ts"][25])
    assert old["ltf_missing"].all() and old["cisd_ts"].is_null().all()
```

  Build `ohlc_long` in `tests/fractal/conftest.py` from Task 2's `BASE`
  pattern, repeated twice with an offset, and 5m bars made by splitting each
  1h bar into 12 (first 6 make the low, last 6 recover through the run
  open). Add `test_real_mnq_runs` with
  `@pytest.mark.skipif(not Path("data_store/bars/MNQ").exists(), reason="no local data")`:
  `run_model(Path("data_store"), "MNQ", "D-1H")` returns more than 0 rows
  with exactly the columns listed above.
- [ ] **Step 2:** Run `.venv/bin/pytest tests/fractal/test_model.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement `run_model`:
  - read the HTF interval, building `"4h"` via `to_4h(read_bars(...,"1h"))`;
  - add session columns and `mark_roll_days` (C2's globex date);
  - `detect_c2`, then for each setup `find_cisd` with `window_end` = C3's
    close.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(fractal): pairing pipeline with prefix-stability test`.

---

### Task 5: Review page

**Files:**
- Create: `src/apollo/review/__init__.py`, `src/apollo/review/page.py`,
  `src/apollo/review/template.html`
- Test: `tests/review/test_page.py`

**Interfaces:**
- Consumes: `run_model`, `read_bars`, `PAIRINGS`, `bar_close`.
- Produces:
  - `build_page(root: Path, code: str, pairing: Pairing, last: int = 60,
    out_dir: Path = Path("review")) -> Path`: writes
    `review/<code>_<pairing>.html` and returns its path.
  - `main(argv) -> int`: `python -m apollo.review.page --symbol MNQ
    --pairing D-1H --last 60`.
- **Page content** (template filled at one `/*__DATA__*/` placeholder with
  JSON):
  - Header: `APOLLO©` wordmark, symbol, pairing, setup count, and
    "Detection review. Mark each setup, then download your verdicts."
  - Left: the setup list (date, direction, POI kind, CISD found / not found
    / LTF missing, verdict dot).
  - Right, top: the HTF chart (40 bars around the setup), with:
    - markers C1, C2, C3;
    - a dashed POI line;
    - an EQ line;
    - a C1 low/high line.
  - Right, bottom: the LTF chart over the CISD window, with:
    - the sweep level;
    - the CISD level line;
    - the protected low/high line;
    - a CISD marker labelled "CISD" (and "early" when early);
    - EQ shown in the down colour when broken.
  - Footer per setup:
    - three buttons, **Right**, **Wrong**, **Unsure**, plus a note field;
    - the keys `j`/`k` move to the next/previous setup;
    - verdicts are saved in `localStorage` under `apollo-review-<code>-<pairing>`;
    - **Download verdicts** saves `verdicts-<code>-<pairing>.json`
      (`c2_ts`, `direction`, `verdict`, `note`).
  - Tokens, fonts and theme (light/dark/auto) as in Global Constraints.
    Empty state: "No setups in this range."

- [ ] **Step 1: Write the failing test**

```python
def test_page_embeds_setups_and_pinned_chart(tmp_path, ohlc_long, monkeypatch):
    htf, ltf = ohlc_long
    monkeypatch.setattr("apollo.review.page._load", lambda root, code, pairing: (htf, ltf))
    p = build_page(tmp_path, "MNQ", "1H-5m", out_dir=tmp_path)
    html = p.read_text()
    assert p.name == "MNQ_1H-5m.html" and "lightweight-charts@4.2.0" in html
    data = json.loads(html.split("const DATA = ")[1].split(";\n")[0])
    assert len(data["setups"]) >= 1 and {"htf", "ltf", "setups"} <= data.keys()
    assert "/*__DATA__*/" not in html
```

- [ ] **Step 2:** Run `.venv/bin/pytest tests/review -q`. Expected: FAIL, import error.
- [ ] **Step 3:** Implement `page.py`:
  - `_load(root, code, pairing)` returns the HTF and LTF frames, so tests can
    swap it.
  - Serialise times as UNIX seconds (Lightweight Charts format).
  - Write `template.html` following the content list above.
  - Add `review/` to `.gitignore`: generated pages are local, since the
    snapshot plan publishes the public one.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`, then `.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/pyright`. Expected: all clean.
- [ ] **Step 5: Real pages.** Refresh local data with `.venv/bin/python -m apollo.data.collect --symbols MNQ --intervals 5m,15m,1h,1d`, then
  `.venv/bin/python -m apollo.review.page --symbol MNQ --pairing D-1H` and
  `--pairing 1H-5m`. Expected: two HTML files with more than 0 setups. Open
  each in the browser pane, and check light and dark mode, the `j`/`k`
  keys, a verdict that survives a reload, and the download.
- [ ] **Step 6: Commit** `feat(review): Fractal Model detection review page`.
- [ ] **Step 7: Hand-off.** Send Vaughn both pages. Ask him to mark at least
  20 setups per pairing and send the verdict files back. His verdicts decide
  the rule changes in `config/strategy.toml` before Plan 4 runs any backtest.

---

## Self-review notes

- **Spec 5.6 coverage:**
  - C1/C2 sweep + reversal close: Task 2.
  - POI swing/FVG: Tasks 1–2.
  - C3 closure: Task 2.
  - EQ, and EQ broken before entry: Tasks 2–3.
  - CISD with protected level: Task 3.
  - Pairings: Task 4.
  - Spec section 9 review gate: Task 5.
- **Left for later plans:**
  - Entry, stop, target, R:R, the 09:30–12:00 window, sizing and the
    positional entry: Plan 4.
  - Combining the pairings into the top-down checklist: Plan 4.
  - Correlated-asset SMT: spec v2.
- **Rulings already taken in this plan** (Vaughn can override them on the
  review page):
  - An outside bar is skipped.
  - A swing POI is preferred over an FVG.
  - The CISD window runs from C2's open to C3's close.
  - The FVG POI requires `bottom <= c1_low`.
