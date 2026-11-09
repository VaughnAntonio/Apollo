# Apollo Predictor, Plan 1: Data Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested Python package that downloads free Yahoo bars for
every configured symbol, stores them as deduplicated monthly Parquet files,
tags sessions, 4H bars, roll days and data-quality problems, and collects new
data automatically every weekday.

**Architecture:**
- A `src/apollo/data` package of small pure functions: normalise, store,
  sessions, resample, rolls, quality.
- A thin network wrapper around `yfinance`.
- A collector CLI that takes the fetcher as a parameter, so tests never hit
  the network.
- GitHub Actions for CI (every push) and collection (weekdays, results
  committed to a `data` branch).

**Tech Stack:** Python 3.13, Polars, PyArrow, yfinance, pytest, ruff,
pyright, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-08-apollo-predictor-design.md`
(sections 3, 5.3, 5.13 data-quality, 6, 7).

## Roadmap (this plan is 1 of 7, plus optional Plan 8)

The spec covers seven subsystems. Each gets its own plan, written when the
previous one has shipped, so later plans can use the real interfaces:

1. **Data foundation** (this plan).
2. **Fractal Model detection + review page:** C1/C2/C3, POIs, CISD, and a
   static chart page so Vaughn can check the detections against his own
   reading.
3. **Models:** health features, regime detector, asymmetric conformal range,
   forecast ledger.
4. **Strategy, backtester and rigour:** checklist, sizing, costs,
   walk-forward, ablation, Monte Carlo, holdout and run log, quantstats.
5. **API + journal:** DuckDB, case-study import, Take trade, FastAPI
   endpoints.
6. **Web app:** chart, rail, menu, ticker picker, themes, journal sheet,
   trade drawing.
7. **Guide, pages, snapshot and README:** guided tour, explainers,
   Models/Backtest/Case study pages, static export, GitHub Pages, model cards.
8. **Optional, after 7: security and bug pass** with VulnClaw (offline code
   scan; local-only pentest via Ollama), plus `pip-audit`, `npm audit`,
   `bandit` and a whole-repo review. Spec 5.16.

## Global Constraints

- Cost is zero. No paid APIs, no API keys. Data source: `yfinance` only.
- Licences: dependencies must be MIT/BSD/Apache. Runtime deps for this plan:
  `polars`, `pyarrow`, `yfinance`, `pandas` (only because yfinance returns
  it). Dev deps: `pytest`, `ruff`, `pyright`.
- Python `>=3.13`, plain `venv` + `pyproject.toml` (PyCharm Community
  compatible). No uv/poetry.
- All timestamps are stored in **UTC** (`pl.Datetime("us", "UTC")`).
  Exchange time is `America/New_York`.
- Yahoo lookback limits: 1m = 7 days, 5m and 15m = 60 days, 1h = 729 days, 1d =
  unlimited.
- CME Globex day starts at 18:00 ET (previous calendar day) and ends at
  17:00 ET. NY regular session = 09:30–16:00 ET.
- Never print or commit credentials. `.superpowers/`, `journal_media/` and
  `*.duckdb` are git-ignored.
- Commit messages end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Mark deliberate shortcuts with `# shortcut:` comments (ponytail); make the
  smallest change that passes the test (karpathy-guidelines).
- Ask Vaughn before adding any dependency not listed here, and before any
  `git push`.

## Review Focus

1. **Yahoo returns an empty frame** (holiday, delisted or misspelt stock
   symbol, rate limit). The collector logs it, writes nothing for that pair
   and carries on with the other symbols. Exit code 0 unless *every* pair
   failed. *(Pinned in Task 8.)*
2. **Daily bars arrive tz-naive while intraday bars arrive tz-aware.** Both
   normalise to UTC without shifting the daily date. *(Pinned in Task 3.)*
3. **DST transition days** (2026-03-08, 2026-11-01). Session dates and 4H
   buckets stay correct, with no 4H bar split across the change. *(Pinned in
   Tasks 4 and 5.)*
4. **Overlapping fetch windows** (the same bars fetched on consecutive days).
   Appending is idempotent, and a later revision of a bar replaces the
   earlier one. *(Pinned in Task 3.)*
5. **Weekend and daily-maintenance gaps** are not reported as missing bars;
   real intraday holes are. *(Pinned in Task 7.)*

---

## File structure

```
pyproject.toml                         project + tool config
.gitignore
config/symbols.toml                    the 14 symbols with point values and ticks
src/apollo/__init__.py
src/apollo/config.py                      Symbol dataclass, load_symbols()
src/apollo/data/__init__.py
src/apollo/data/yahoo.py                  normalise_yahoo(), fetch_bars(), MAX_LOOKBACK
src/apollo/data/store.py                  append_bars(), read_bars()
src/apollo/data/sessions.py               add_session_columns()
src/apollo/data/resample.py               to_4h(), to_rth_daily()
src/apollo/data/rolls.py                  roll_windows(), mark_roll_days()
src/apollo/data/quality.py                QualityReport, check_quality()
src/apollo/data/collect.py                collect(), main()
tests/conftest.py                      bar-frame factory fixture
tests/data/test_*.py                   one per module
.github/workflows/ci.yml
.github/workflows/collect.yml
```

---

### Task 1: Repository scaffold and CI

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/apollo/__init__.py`,
  `src/apollo/data/__init__.py`, `tests/test_smoke.py`,
  `.github/workflows/ci.yml`

**Interfaces:**
- Produces: importable package `apollo` with `__version__ = "0.1.0"`;
  `pytest`, `ruff check`, `ruff format --check`, `pyright` all runnable from
  the repo root.

- [ ] **Step 1:** `git init -b main` in `/Users/vaughnantonio/Desktop/Apollo Predictor`. Create `.gitignore` with: `.venv/`, `__pycache__/`, `.superpowers/`, `*.duckdb`, `journal_media/`, `data_store/`, `.pytest_cache/`, `.ruff_cache/`, `node_modules/`, `dist/`.
- [ ] **Step 2: Write the failing test** `tests/test_smoke.py`

```python
import apollo

def test_version():
    assert apollo.__version__ == "0.1.0"
```

- [ ] **Step 3:** Run `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`. This fails because `pyproject.toml` doesn't exist yet. Expected: an error.
- [ ] **Step 4:** Create `pyproject.toml`:
  - `src/` layout, `requires-python = ">=3.13"`;
  - deps: `polars`, `pyarrow`, `yfinance`, `pandas`;
  - optional `dev` deps: `pytest`, `ruff`, `pyright`;
  - `[tool.pytest.ini_options] testpaths=["tests"]`,
    `markers=["network: hits Yahoo"]`, `addopts="-m 'not network'"`;
  - `[tool.ruff] line-length=100`;
  - `[tool.pyright] include=["src","tests"]`.

  Create `src/apollo/__init__.py` with `__version__ = "0.1.0"`.
- [ ] **Step 5:** Run `.venv/bin/pip install -e ".[dev]" && .venv/bin/pytest -q`. Expected: `1 passed`.
- [ ] **Step 6:** Create `.github/workflows/ci.yml`:
  - trigger on push and pull_request;
  - ubuntu-latest, Python 3.13;
  - steps: `pip install -e ".[dev]"`, `ruff check .`, `ruff format --check .`,
    `pyright`, `pytest -q`.

  Run the same four commands locally. Expected: all exit 0.
- [ ] **Step 7: Commit**, including the spec and this plan:

```bash
git add .gitignore pyproject.toml src tests .github docs
git commit -m "chore: scaffold apollo package, CI, spec and plan 1"
```

---

### Task 2: Symbol config

**Files:**
- Create: `config/symbols.toml`, `src/apollo/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Symbol` with fields `code: str`,
    `yahoo: str`, `name: str`, `kind: Literal["future","stock"]`,
    `point_value: float`, `tick_size: float`, `roll_rule:
    Literal["equity_index_quarterly","none"]`, `model_enabled: bool`.
  - `load_symbols(path: Path = CONFIG_DIR / "symbols.toml") ->
    dict[str, Symbol]`, keyed by `code`, in file order.

- [ ] **Step 1: Write the failing test**

```python
from apollo.config import load_symbols

def test_symbols_loaded_with_spec_values():
    s = load_symbols()
    assert list(s)[:8] == ["MNQ", "MES", "M2K", "MYM", "NQ", "ES", "MGC", "MCL"]
    assert set(s) >= {"NVDA", "AAPL", "MSFT", "TSLA", "AMZN", "META"}
    assert s["MNQ"].yahoo == "MNQ=F" and s["MNQ"].point_value == 2.0 and s["MNQ"].tick_size == 0.25
    assert s["MYM"].point_value == 0.5 and s["MCL"].point_value == 100.0
    assert s["NVDA"].kind == "stock" and s["NVDA"].point_value == 1.0 and s["NVDA"].tick_size == 0.01
    assert [c for c, x in s.items() if x.model_enabled] == ["MNQ", "MES", "M2K", "MYM"]
    assert s["MNQ"].roll_rule == "equity_index_quarterly" and s["MGC"].roll_rule == "none"
```

- [ ] **Step 2:** Run `.venv/bin/pytest tests/test_config.py -v`. Expected: FAIL, `ModuleNotFoundError: apollo.config`.
- [ ] **Step 3:** Write `config/symbols.toml` (one `[[symbol]]` table each; tomllib is in the standard library) with these values from spec 5.6 ("eq" = `equity_index_quarterly`):

  | code | yahoo | point | tick | roll | model |
  |---|---|---|---|---|---|
  | MNQ | MNQ=F | 2 | 0.25 | equity_index_quarterly | true |
  | MES | MES=F | 5 | 0.25 | eq | true |
  | M2K | M2K=F | 5 | 0.10 | eq | true |
  | MYM | MYM=F | 0.5 | 1.0 | eq | true |
  | NQ | NQ=F | 20 | 0.25 | eq | false |
  | ES | ES=F | 50 | 0.25 | eq | false |
  | MGC | MGC=F | 10 | 0.10 | none | false |
  | MCL | MCL=F | 100 | 0.01 | none | false |
  | NVDA, AAPL, MSFT, TSLA, AMZN, META | same as code | 1 | 0.01 | none | false |

  Then implement `src/apollo/config.py` (`CONFIG_DIR` = repo `config/` resolved
  from `__file__`).
- [ ] **Step 4:** Run the test. Expected: PASS.
- [ ] **Step 5: Commit** `feat: symbol config with point values and ticks`.

---

### Task 3: Yahoo normalisation and the Parquet store

**Files:**
- Create: `src/apollo/data/yahoo.py`, `src/apollo/data/store.py`,
  `tests/conftest.py`
- Test: `tests/data/test_yahoo.py`, `tests/data/test_store.py`

**Interfaces:**
- Consumes: `Symbol` (Task 2).
- Produces:
  - `Interval = Literal["1m","5m","15m","1h","1d"]`;
  - `MAX_LOOKBACK: dict[Interval, timedelta | None]`, with values `1m` 7 days,
    `5m` 60 days, `15m` 60 days, `1h` 729 days, `1d` None;
  - `BAR_SCHEMA`: columns `ts` (Datetime us UTC), `open`, `high`, `low`,
    `close` (Float64), `volume` (Int64), `symbol` (Utf8);
  - `normalise_yahoo(raw: pandas.DataFrame, code: str, interval: Interval) ->
    pl.DataFrame` in `BAR_SCHEMA`, sorted by `ts`, rows with null OHLC
    dropped;
  - `fetch_bars(sym: Symbol, interval: Interval, start: datetime | None =
    None) -> pl.DataFrame`, a thin wrapper around
    `yfinance.Ticker(sym.yahoo).history(interval=..., start=..., auto_adjust=False)`;
  - `append_bars(root: Path, df: pl.DataFrame, interval: Interval) -> int`
    (rows written);
  - `read_bars(root: Path, code: str, interval: Interval, start: datetime |
    None = None, end: datetime | None = None) -> pl.DataFrame`;
  - fixture `bars(start: str, n: int, every: str, tz="America/New_York", symbol="MNQ")`
    in `tests/conftest.py`: makes a synthetic `BAR_SCHEMA` frame starting at
    `start` local time, `n` rows spaced `every` apart, with a monotonic close
    (100, 101, ...), high = close + 1, low = close − 1.

- [ ] **Step 1: Write the failing tests**

```python
# tests/data/test_yahoo.py
import pandas as pd
from apollo.data.yahoo import normalise_yahoo

def test_intraday_tz_aware_converted_to_utc():
    idx = pd.DatetimeIndex(["2026-11-02 09:30", "2026-11-02 09:35"]).tz_localize("America/New_York")
    raw = pd.DataFrame({"Open": [1, 2], "High": [2, 3], "Low": [0, 1], "Close": [1.5, 2.5], "Volume": [10, 20]}, index=idx)
    df = normalise_yahoo(raw, "MNQ", "5m")
    assert str(df["ts"][0]) == "2026-11-02 14:30:00+00:00"
    assert df.columns == ["ts", "open", "high", "low", "close", "volume", "symbol"]

def test_daily_tz_naive_keeps_calendar_date():
    raw = pd.DataFrame({"Open": [1.0], "High": [2.0], "Low": [0.5], "Close": [1.5], "Volume": [5]},
                       index=pd.DatetimeIndex(["2026-11-02"]))
    df = normalise_yahoo(raw, "MNQ", "1d")
    assert df["ts"][0].date().isoformat() == "2026-11-02"

def test_empty_and_null_rows():
    assert normalise_yahoo(pd.DataFrame(), "NVDA", "1h").height == 0
```

```python
# tests/data/test_store.py
from apollo.data.store import append_bars, read_bars

def test_month_split_and_idempotent(tmp_path, bars):
    df = bars("2026-10-30 09:30", 6 * 24 * 4, "1h")  # crosses into November
    assert append_bars(tmp_path, df, "1h") == df.height
    append_bars(tmp_path, df, "1h")
    files = sorted(p.name for p in (tmp_path / "bars" / "MNQ" / "1h").iterdir())
    assert files == ["2026-10.parquet", "2026-11.parquet"]
    assert read_bars(tmp_path, "MNQ", "1h").height == df.height

def test_later_revision_wins(tmp_path, bars):
    df = bars("2026-11-02 09:30", 3, "5m")
    append_bars(tmp_path, df, "5m")
    append_bars(tmp_path, df.with_columns(close=df["close"] + 1), "5m")
    assert read_bars(tmp_path, "MNQ", "5m")["close"].to_list() == (df["close"] + 1).to_list()
```

- [ ] **Step 2:** Run `.venv/bin/pytest tests/data -v`. Expected: FAIL, import errors.
- [ ] **Step 3:** Implement `normalise_yahoo` and `fetch_bars` in `yahoo.py`.
  - A tz-naive index (daily) is localised to UTC **as-is**; a tz-aware index
    is converted to UTC.
  - `fetch_bars`: when `start` is None, use `now − MAX_LOOKBACK[interval]`
    (or `period="max"` for `1d`).
- [ ] **Step 4:** Implement `append_bars` / `read_bars` in `store.py`.
  - Path: `root/bars/<symbol>/<interval>/<YYYY-MM>.parquet`, month taken from
    the UTC `ts`.
  - Merge with the existing file, `unique(subset="ts", keep="last")` with new
    rows last, sort, write zstd Parquet.
  - `read_bars` scans all months (`pl.scan_parquet`) and filters start/end.
- [ ] **Step 5:** Run `.venv/bin/pytest tests/data -v`. Expected: PASS.
- [ ] **Step 6:** Add `tests/data/test_yahoo_live.py`, marked
  `@pytest.mark.network`: `fetch_bars(MNQ,"1d")` returns more than 1,500 rows
  in `BAR_SCHEMA`. Run it once: `.venv/bin/pytest -m network -v`.
  Expected: PASS (needs internet).
- [ ] **Step 7: Commit** `feat: yahoo normalisation and monthly parquet store`.

---

### Task 4: Session tagging

**Files:**
- Create: `src/apollo/data/sessions.py`
- Test: `tests/data/test_sessions.py`

**Interfaces:**
- Produces: `add_session_columns(df: pl.DataFrame) -> pl.DataFrame`, which
  adds:
  - `ts_et` (Datetime, America/New_York);
  - `globex_date` (Date): an ET time at or after 18:00 belongs to the next
    calendar day;
  - `is_rth` (Bool): 09:30 ≤ ET time < 16:00, Monday–Friday;
  - `ny_date` (Date): the ET calendar date for RTH rows, null otherwise.

- [ ] **Step 1: Write the failing tests**

```python
import polars as pl
from datetime import datetime, timezone
from apollo.data.sessions import add_session_columns

def _one(ts_utc):
    return add_session_columns(pl.DataFrame({"ts": [ts_utc]}).with_columns(pl.col("ts").dt.replace_time_zone("UTC")))

def test_evening_belongs_to_next_globex_day():
    r = _one(datetime(2026, 11, 4, 23, 30))          # 18:30 ET (EST) Wed
    assert str(r["globex_date"][0]) == "2026-11-05" and r["is_rth"][0] is False

def test_rth_bounds_edt_and_est():
    assert _one(datetime(2026, 10, 30, 13, 30))["is_rth"][0] is True   # 09:30 EDT
    assert _one(datetime(2026, 11, 2, 14, 29))["is_rth"][0] is False   # 09:29 EST
    assert _one(datetime(2026, 11, 2, 21, 0))["is_rth"][0] is False    # 16:00 EST

def test_dst_change_day():
    r = _one(datetime(2026, 11, 1, 23, 0))            # Sun 18:00 EST, first bar after fall-back
    assert str(r["globex_date"][0]) == "2026-11-02"
```

- [ ] **Step 2:** Run the tests. Expected: FAIL, import error.
- [ ] **Step 3:** Implement with Polars expressions only (`dt.convert_time_zone`, `dt.hour`, `dt.minute`, `dt.weekday`, `dt.offset_by`).
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5: Commit** `feat: globex and NY session tagging`.

---

### Task 5: Resampling to 4H and to the NY session

**Files:**
- Create: `src/apollo/data/resample.py`
- Test: `tests/data/test_resample.py`

**Interfaces:**
- Consumes: `add_session_columns` (Task 4), the `bars` fixture.
- Produces:
  - `to_4h(df_1h: pl.DataFrame) -> pl.DataFrame`: buckets start at ET hours
    18, 22, 02, 06, 10, 14, so a bucket never crosses the 17:00–18:00 break.
    Output columns are `BAR_SCHEMA` + `bars_in` (Int32, how many 1H bars were
    combined).
  - `to_rth_daily(df_intraday: pl.DataFrame) -> pl.DataFrame`: one row per
    `ny_date` with the RTH open/high/low/close/volume, column `ny_date`
    instead of `ts`.

- [ ] **Step 1: Write the failing tests**

```python
import polars as pl
from apollo.data.resample import to_4h, to_rth_daily

def test_4h_aggregates_and_anchors(bars):
    h = bars("2026-11-03 18:00", 8, "1h")           # Tue 18:00 ET .. Wed 01:00 ET
    out = to_4h(h)
    assert out.height == 2 and out["bars_in"].to_list() == [4, 4]
    assert out["open"][0] == h["open"][0] and out["close"][0] == h["close"][3]
    assert out["high"][0] == h["high"][:4].max()

def test_4h_across_dst(bars):
    h = bars("2026-10-31 18:00", 30, "1h")          # crosses Sun 2026-11-01 fall-back
    starts = to_4h(h).with_columns(pl.col("ts").dt.convert_time_zone("America/New_York").dt.hour().alias("h"))["h"]
    assert set(starts.to_list()) <= {18, 22, 2, 6, 10, 14}

def test_rth_daily_uses_only_session(bars):
    m = bars("2026-11-02 08:00", 12 * 10, "5m")     # 08:00–17:55 ET
    d = to_rth_daily(m)
    assert d.height == 1 and d["open"][0] == m.filter(pl.col("ts").dt.convert_time_zone("America/New_York").dt.strftime("%H:%M") == "09:30")["open"][0]
```

- [ ] **Step 2:** Run the tests. Expected: FAIL, import error.
- [ ] **Step 3:** Implement `to_4h`:
  - bucket key = (`globex_date`, `floor((ET hour − 18) mod 24 / 4)`);
  - aggregate first/max/min/last/sum;
  - `ts` = the first bar's `ts`.

  Implement `to_rth_daily` by filtering `is_rth` and grouping on `ny_date`.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5: Commit** `feat: 4H and NY-session resampling`.

---

### Task 6: Roll days

**Files:**
- Create: `src/apollo/data/rolls.py`
- Test: `tests/data/test_rolls.py`

**Interfaces:**
- Produces:
  - `roll_windows(start: date, end: date) -> list[tuple[date, date]]`: for
    each March/June/September/December, (third Friday − 8 calendar days,
    third Friday), inclusive.
  - `mark_roll_days(df: pl.DataFrame, sym: Symbol) -> pl.DataFrame`: adds
    `near_roll` (Bool), true when `globex_date` falls in a window. Always
    false when `sym.roll_rule == "none"`. Needs `globex_date`, so call
    `add_session_columns` first.

- [ ] **Step 1: Write the failing tests**

```python
from datetime import date
from apollo.data.rolls import roll_windows

def test_2026_windows():
    w = roll_windows(date(2026, 1, 1), date(2026, 12, 31))
    assert w[0] == (date(2026, 3, 12), date(2026, 3, 20))
    assert w[3] == (date(2026, 12, 10), date(2026, 12, 18))
    assert len(w) == 4
```

  Add `test_none_rule_never_flags`: an MGC frame inside a window gives all
  `near_roll == False`. Add `test_index_flags`: an MNQ frame on 2026-03-15
  gives `True`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement. Third Friday = first day of the month + offset to the first Friday + 14 days. Add a `# shortcut:` note that MGC/MCL monthly rolls aren't modelled in v1.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5: Commit** `feat: quarterly roll windows`.

---

### Task 7: Data-quality report

**Files:**
- Create: `src/apollo/data/quality.py`
- Test: `tests/data/test_quality.py`

**Interfaces:**
- Consumes: `add_session_columns` (Task 4).
- Produces:
  - `@dataclass class QualityReport`: `symbol: str`, `interval: str`,
    `rows: int`, `duplicates: int`, `gaps: list[tuple[str, str]]` (UTC ISO
    start/end of each hole), `bad_ticks: list[str]` (UTC ISO ts),
    `bad_days: list[str]` (globex dates with more than 20% of expected bars
    missing); `to_json() -> str`.
  - `check_quality(df: pl.DataFrame, interval: Interval) -> QualityReport`.
- **Definitions:**
  - Gap: two consecutive bars more than 2× the interval apart, unless the hole
    lies entirely inside the expected closures: the daily break 17:00–18:00
    ET Monday–Thursday, and Friday 17:00 to Sunday 18:00 ET.
  - Bad tick: |close − previous close| > 8 × ATR(14).
  - Skipped for `1d`: gaps and bad days.

- [ ] **Step 1: Write the failing tests**

```python
import polars as pl
from apollo.data.quality import check_quality

def test_weekend_and_daily_break_not_gaps(bars):
    df = bars("2026-11-06 15:00", 2, "1h").vstack(bars("2026-11-08 18:00", 2, "1h"))  # Fri → Sun
    assert check_quality(df, "1h").gaps == []

def test_real_hole_reported(bars):
    df = bars("2026-11-03 09:30", 3, "5m").vstack(bars("2026-11-03 10:30", 3, "5m"))
    assert len(check_quality(df, "5m").gaps) == 1

def test_bad_tick(bars):
    df = bars("2026-11-03 09:30", 40, "5m")
    df = df.with_columns(pl.when(pl.int_range(pl.len()) == 30).then(pl.col("close") * 1.5).otherwise(pl.col("close")).alias("close"))
    assert len(check_quality(df, "5m").bad_ticks) >= 1
```

- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement. ATR = rolling 14-mean of the true range.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5: Commit** `feat: data quality report`.

---

### Task 8: Collector CLI

**Files:**
- Create: `src/apollo/data/collect.py`
- Test: `tests/data/test_collect.py`

**Interfaces:**
- Consumes: `load_symbols`, `fetch_bars`, `append_bars`, `check_quality`.
- Produces:
  - `collect(root: Path, symbols: dict[str, Symbol], intervals:
    list[Interval], fetch: Callable[[Symbol, Interval], pl.DataFrame] =
    fetch_bars, today: date | None = None) -> dict[str, int]`, returning a
    map of `"CODE/interval"` to rows written. It writes
    `root/quality/<today>/<CODE>_<interval>.json`.
  - `main(argv: list[str] | None = None) -> int`: flags `--root`
    (default `data_store`), `--symbols` (comma list or `all`),
    `--intervals` (default `1m,5m,15m,1h,1d`). Returns 1 only if every pair
    raised or returned empty.
  - Run as `python -m apollo.data.collect`.

- [ ] **Step 1: Write the failing tests**

```python
import polars as pl
from apollo.config import load_symbols
from apollo.data.collect import collect, main

def test_collect_writes_and_reports(tmp_path, bars):
    syms = {k: v for k, v in load_symbols().items() if k in ("MNQ", "NVDA")}
    res = collect(tmp_path, syms, ["5m"], fetch=lambda s, i: bars("2026-11-03 09:30", 5, "5m").with_columns(symbol=pl.lit(s.code)))
    assert res == {"MNQ/5m": 5, "NVDA/5m": 5}
    assert any((tmp_path / "quality").rglob("MNQ_5m.json"))

def test_one_failure_does_not_stop_others(tmp_path, bars):
    syms = {k: v for k, v in load_symbols().items() if k in ("MNQ", "NVDA")}
    def fetch(s, i):
        if s.code == "NVDA":
            raise RuntimeError("rate limited")
        return bars("2026-11-03 09:30", 5, "5m")
    assert collect(tmp_path, syms, ["5m"], fetch=fetch) == {"MNQ/5m": 5, "NVDA/5m": 0}

def test_main_exit_code_when_all_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("apollo.data.collect.fetch_bars", lambda s, i: pl.DataFrame())
    assert main(["--root", str(tmp_path), "--symbols", "MNQ", "--intervals", "1d"]) == 1
```

- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement. Catch exceptions per pair with `logging.warning`; skip empty frames.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5: Real run.** Run `.venv/bin/python -m apollo.data.collect --symbols MNQ --intervals 1h,1d`. Expected: logs rows written; `data_store/bars/MNQ/1d/` holds monthly files back to 2019; the quality JSON exists.
- [ ] **Step 6: Commit** `feat: collector CLI`.

---

### Task 9: Scheduled collection Action

**Files:**
- Create: `.github/workflows/collect.yml`

**Interfaces:**
- Consumes: `python -m apollo.data.collect`.
- Produces: commits to branch `data` with `data_store/bars/**` and
  `data_store/quality/**`.

- [ ] **Step 1:** Write the workflow:
  - `on: schedule: cron "30 22 * * 1-5"` (after the 17:00 ET close in both
    EST and EDT) plus `workflow_dispatch`;
  - `permissions: contents: write`;
  - check out `main`, then check out branch `data` into `data_store/` (if the
    branch doesn't exist, create an orphan `data` branch there);
  - install, run the collector with `--root data_store`;
  - in `data_store/`: `git add -A`, commit `data: <date>` as
    `github-actions[bot]` only if there are changes, push `data`.
- [ ] **Step 2:** Validate the YAML locally with `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/collect.yml'))"`. If PyYAML is missing, skip this step; CI's first run validates it. Expected: no error.
- [ ] **Step 3: Commit** `ci: weekday data collection to data branch`.
- [ ] **Step 4: Hand-off check.** Pushing needs a GitHub remote. **Ask Vaughn** before creating the repo (`gh repo create VaughnAntonio/Apollo --public --source . --push`). After the push, trigger `gh workflow run collect.yml`. Expected: a green run and a `data` branch containing `data_store/bars/MNQ/...`.

---

## Self-review notes

- **Spec coverage for this plan's scope:**
  - 5.3 collector, Parquet, `data` branch, 4H from 1H, sessions, roll
    handling: Tasks 3–6, 8, 9.
  - 5.13 data quality: Task 7.
  - Section 7 CI: Task 1. The frontend CI steps come in plan 6.
  - Everything else is deferred to plans 2–7, as listed in the Roadmap.
- **Roll exclusion from features and P&L** is *consumed* in plans 3 and 4,
  through `near_roll`.
- **Local sync** (pulling the `data` branch) is a one-line
  `git worktree add data_store data`. It is documented in the README task
  (plan 7), not a separate task here.
