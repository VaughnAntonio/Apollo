# Apollo Predictor, Plan 5 of 7: Journal and Local API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Apollo a real trade journal (DuckDB, with the case study
imported), a "Take trade" flow that records what the model said at entry, a
live top-down signal for today, and a local FastAPI server that the web app
(Plan 6) reads everything from.

**Architecture:**
- **`apollo.journal`** holds the journal:
  - `store`: the DuckDB table and CRUD, with derived R, P&L and win;
  - `importer`: imports the case study;
  - `trades`: Take trade, close and auto-exit, and the model snapshot;
  - `stats`: followed vs manual vs skipped, by tag and grade, a P&L
    calendar, and an export for the `journal-review` skill.
- **`apollo.live.signal`** builds today's checklist (daily bias → 4H → 1H →
  15m → 5m trigger) from the existing pipelines.
- **`apollo.api`** is a FastAPI app over all of it. It binds to `127.0.0.1`
  only.

**Tech Stack:**
- FastAPI and Uvicorn (already installed through OpenBB) and DuckDB (Vaughn's
  pick).
- New, for tests only: `httpx` (BSD), which FastAPI's `TestClient` needs.
  *Approval requested with this plan.*

**Spec:** `docs/superpowers/specs/2026-11-08-apollo-predictor-design.md`
(5.6 checklist, 5.8 journal, 5.9 API, 5.15 journal review).

## Global Constraints

- **Local and private.**
  - The journal lives in `data_store/journal.duckdb`, with screenshots in
    `journal_media/`. Both are git-ignored. `*.duckdb` already is; add
    `journal_media/`.
  - The API binds to `127.0.0.1` only.
  - CORS allows `http://localhost:5173` (Plan 6's Vite dev server) and
    nothing else.
- **Journal fields** (spec 5.8):
  - `id`, `opened_at`, `closed_at`, `symbol`, `side`, `entry`, `stop`,
    `target`, `exit`, `size`, `fees`;
  - `account`, `stage` (`backtest|forward_test|eval|funded|live`);
  - `strategy`, `grade` (`A|B|C|E` or null), `tags` (list), `notes`
    (Markdown), `screenshot` (path);
  - `source` (`signal|manual|imported`), `model_snapshot` (JSON), `scaled`
    (bool, true for case-study rows).
- **Derived on read:**
  - `risk_$ = |entry − stop| × point_value × size`;
  - `pnl_$ = sign × (exit − entry) × point_value × size − fees`;
  - `r = pnl_$ / risk_$`;
  - `win = r > 0`.
  - All null while the trade is open.
- **Case-study rows have no prices**, so they store the case study's `r` and
  scaled P&L directly in two columns, `imported_r` and `imported_pnl`. The
  derived values then use those.
- **Model snapshot** (written when an entry is created, never edited later):
  - the latest forecast (regime probabilities, zone);
  - the checklist rows with their status;
  - the signal (entry, stop, target, contracts, risk of drawdown limit);
  - `snapshot_at`.
- **Signal-skipped trades:** a signal day with no journal entry counts as
  "skipped". The stats compare **signal / manual / skipped**.
- **Live signal: decision rules come from spec 5.6, with the variant set in
  config.**
  - `[live] variant = "plain"` until Vaughn picks one. Plan 4 found no filter
    with enough trades to prefer it.
  - Overnight Daily → 1H CISDs use Plan 4's deferred-entry rule.
- **Every API response that carries a signal or forecast says**
  `"research_only": true`, and the docs page says "Research tool. Not
  financial advice."
- **Prose:** humanizer skill (embedded mode). Commits end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Use
  `set -o pipefail`, and keep the ledger and commit in one `&&` chain (Plan 4
  lesson).

## Review Focus

1. **Editing a trade's stop after it's saved.** `model_snapshot` and the
   original stop (`initial_stop`) are kept. R is always measured against the
   **initial** stop, so moving a stop can't flatter the result. *(Pinned in
   Task 1.)*
2. **A trade left open past 16:00 ET.** Auto-close fills it at the 15:00 bar's
   close and marks `exit_reason = "flat_auto"`, waiting for the user to
   confirm. It never silently picks a better price. *(Pinned in Task 2.)*
3. **Importing the case study twice** creates no duplicates: the import key
   is (`source='imported'`, date, account, trade_no). *(Pinned in Task 2.)*
4. **The API is called for a symbol with no models** (`model_enabled=false`,
   e.g. NVDA). `/bars` works. `/signal` returns
   `{"status": "no_model", ...}` with HTTP 200, not a 500. *(Pinned in
   Task 5.)*
5. **Malformed or hostile journal input** (a negative size, `side="sideways"`,
   a screenshot path with `../`) is rejected with 422. Uploads are saved only
   under `journal_media/` with a generated name. *(Pinned in Task 5.)*

---

## File structure

```
pyproject.toml                    + duckdb; dev: httpx
config/strategy.toml              + [live] variant = "plain" (modify)
src/apollo/journal/__init__.py
src/apollo/journal/store.py       JournalStore (DuckDB): add, get, list, update, delete; derived fields
src/apollo/journal/importer.py    import_case_study()
src/apollo/journal/trades.py      take_trade(), close_trade(), auto_close(), build_snapshot()
src/apollo/journal/stats.py       journal_stats(), calendar(), export_for_review()
src/apollo/live/__init__.py
src/apollo/live/signal.py         current_signal(), CheckRow
src/apollo/api/__init__.py
src/apollo/api/main.py            create_app(root) -> FastAPI; main()  (python -m apollo.api)
.claude/skills/journal-review/SKILL.md   point "Apollo's journal export" at the new export (modify)
tests/journal/*, tests/live/*, tests/api/*
```

---

### Task 1: Journal store

**Files:** `pyproject.toml`, `.gitignore`,
`src/apollo/journal/{__init__,store}.py`,
`tests/journal/{__init__,test_store}.py`.

**Interfaces:**
- `JournalStore(path: Path)`. It creates the `journal` table on first use.
  Methods:
  - `add(entry: dict) -> int` returns the new id; it validates the fields
    (Global Constraints) and raises `ValueError` on bad input;
  - `get(id) -> dict | None`;
  - `list(symbol: str | None = None, start: date | None = None, end: date |
    None = None, source: str | None = None) -> list[dict]`, newest first;
  - `update(id, changes: dict) -> dict`: `model_snapshot`, `initial_stop`,
    `source` and `opened_at` can't be changed (raises `ValueError`);
  - `delete(id) -> bool`.

  Every returned dict includes the derived `risk_$`, `pnl_$`, `r` and `win`.
- `initial_stop` is set from `stop` on `add` and never changes; R uses it.

- [ ] **Step 1:** Add `duckdb` to dependencies and `httpx` to dev dependencies; install. Add `journal_media/` to `.gitignore`. Expected: `python -c "import duckdb, httpx"` exits 0.
- [ ] **Step 2: Write the failing tests**

```python
def test_add_get_derived(tmp_path):
    s = JournalStore(tmp_path / "j.duckdb")
    i = s.add(dict(BULL, entry=102.0, stop=99.75, target=110.0, size=2, fees=4.48))
    e = s.get(i)
    assert e["risk_$"] == 9.0 and e["r"] is None          # open: no P&L yet
    s.update(i, {"exit": 106.5, "closed_at": CLOSE})
    e = s.get(i)
    assert e["pnl_$"] == pytest.approx(4.5 * 2 * 2 - 4.48) and e["r"] == pytest.approx((18 - 4.48) / 9)

def test_moving_the_stop_does_not_change_r(tmp_path): ...  # update stop=101 after entry; r still uses 99.75
def test_snapshot_and_source_are_frozen(tmp_path): ...     # update({"model_snapshot": {}}) -> ValueError
def test_rejects_bad_input(tmp_path): ...                  # size -1, side "sideways", screenshot "../x.png" -> ValueError
def test_list_filters_and_order(tmp_path): ...             # 3 entries, two symbols; filter + newest first
```

  `BULL` is a minimal valid entry for MNQ on account "APEX 50k", stage
  "eval", source "manual". Write each test with concrete values, as in the
  first one.
- [ ] **Step 3:** Run `.venv/bin/pytest tests/journal -q`. Expected: FAIL.
- [ ] **Step 4:** Implement. Use one table, store `tags` and `model_snapshot` as JSON text, and compute the derived fields in Python on read.
- [ ] **Step 5:** Run `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 6: Commit** `feat(journal): DuckDB journal store with derived R and frozen fields`.

---

### Task 2: Case-study import, Take trade, close and auto-close

**Files:** `src/apollo/journal/{importer,trades}.py`,
`tests/journal/{test_importer,test_trades}.py`.

**Interfaces:**
- `import_case_study(store, csv_dir: Path) -> int`: reads
  `trades_public.csv`, writes one row per trade (`source="imported"`,
  `scaled=True`, `imported_r`, `imported_pnl`, plus strategy, grade, stage
  and account). Returns the number of new rows. The import key is
  `(date, account, trade_no)`.
- `build_snapshot(signal: dict, forecast: dict | None) -> dict`.
- `take_trade(store, signal: dict, forecast: dict | None, fill: float | None
  = None, size: int | None = None) -> int`:
  - creates `source="signal"` from the signal's entry, stop, target and
    contracts;
  - `fill` and `size` override the defaults;
  - refuses when `signal["status"] != "trigger"`.
- `close_trade(store, id, exit: float, at: datetime, reason: str) -> dict`.
- `auto_close(store, bars_by_symbol: dict[str, pl.DataFrame], now: datetime)
  -> list[int]`: for each open entry, walk its bars after `opened_at` with
  Plan 4's rules (stop first on a same-bar hit; flat at 16:00 ET using the
  15:00 bar's close). It sets `exit`, `closed_at`, and `exit_reason` =
  `stop_auto|target_auto|flat_auto`, plus `needs_confirm=True`. Returns the
  ids it closed.

- [ ] **Step 1: Write the failing tests:**
  - `test_import_counts_and_r`: 51 rows; one known row's `r` matches the CSV.
  - `test_import_twice_adds_nothing`.
  - `test_take_trade_records_snapshot`: the snapshot holds the checklist and
    forecast, and source is `signal`.
  - `test_take_trade_refuses_without_trigger`.
  - `test_auto_close_stop_first_and_flat`: two open trades, one hits stop
    and target in the same bar (→ `stop_auto` at the stop); the other runs
    past 16:00 (→ `flat_auto` at the 15:00 bar's close).
  - `test_auto_close_needs_confirm`.

  The CSV comes from the case-study clone in the scratchpad or a fixture
  copy. Copy `trades_public.csv` into `tests/fixtures/` (it's public, MIT
  data).
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement. `auto_close` reuses the per-bar logic from `apollo.strategy.simulate`, extracted into a shared `walk_trade(...)` helper. Don't duplicate it.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`. Expected: all pass, including Plan 4's simulator tests after the extraction.
- [ ] **Step 5: Commit** `feat(journal): case-study import, take trade, close and auto-close`.

---

### Task 3: Journal stats and the review export

**Files:** `src/apollo/journal/stats.py`, `tests/journal/test_stats.py`,
`.claude/skills/journal-review/SKILL.md`.

**Interfaces:**
- `journal_stats(entries: list[dict], signal_days: list[date]) -> dict`
  with:
  - `by_source` (`signal`, `manual`, `imported`, each: n, win rate, mean R,
    sum R);
  - `skipped` (signal days with no `signal` entry);
  - `by_tag`, `by_grade`, `by_stage`;
  - `worst_days` (top 3 by day R);
  - `daily_cap_breaks` (days below −2R or with more than 2 trades: the
    journal review's suggested rule).
- `calendar(entries) -> list[dict]` with `date`, `n`, `r` and `pnl_$` per
  day, for the P&L calendar.
- `export_for_review(store, path: Path) -> Path` writes the CSV the
  `journal-review` skill reads (one row per trade, with the derived fields).
  Update the skill's Inputs section: *"1. `python -m apollo.journal.export`
  output"*.

- [ ] **Step 1: Write the failing tests:**
  - `test_by_source_and_skipped`;
  - `test_daily_cap_breaks`: a day with 3 trades and a day at −2.5R are both
    listed;
  - `test_calendar_sums`;
  - `test_export_columns`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement, plus `python -m apollo.journal.export --out docs/reviews/journal-export.csv`. The export is git-ignored because it holds real trades. Add `docs/reviews/journal-export*.csv` to `.gitignore`.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(journal): stats, P&L calendar and review export`.

---

### Task 4: Today's live signal (the checklist)

**Files:** `config/strategy.toml`, `src/apollo/live/{__init__,signal}.py`,
`tests/live/{__init__,test_signal}.py`.

**Interfaces:**
- `@dataclass CheckRow` with `step` (`daily_bias|4h|1h|15m|5m_trigger`),
  `status` (`pass|wait|fail|no_data`) and `detail: str`.
- `current_signal(root: Path, code: str, now: datetime, *, frames=None) ->
  dict`. `frames` is injectable for tests. Returns:
  - `status` (`flat|waiting|trigger|no_model`), `direction`;
  - `checklist: list[CheckRow]`;
  - `entry`, `stop`, `target`, `contracts`, `risk_of_limit`, `variant`,
    `as_of`;
  - `research_only: true`.
- **Rules** (spec 5.6, using setups that are already detected; no new
  detection logic):
  - **daily_bias:** the latest D-1H setup whose C2 is the last *completed*
    daily bar, or whose C3 closed through. Its direction is the bias. If the
    live variant uses the regime filter, also check it. With no setup:
    `status=flat`.
  - **4h:** a 4H-15m setup in the bias direction whose C2 falls in today's
    Globex day.
  - **1h:** the bias setup's after-C2 CISD has confirmed, or is deferred to
    today's open under Plan 4's rule. Range room, if the variant uses range.
  - **15m:** a 4H-15m setup in the bias direction has an after-C2 CISD.
  - **5m_trigger:** a 1H-5m setup in the bias direction has an after-C2
    CISD whose fill falls in 09:30–12:00 ET today. Build the candidate with
    `build_candidates(..., layer="1H-5m")`. A non-skipped candidate gives
    `status=trigger` with its levels and size.
  - **Sizing** uses the configured account and `risk_pct`. `risk_of_limit` =
    planned loss ÷ the account's drawdown.

- [ ] **Step 1: Write the failing tests** with injected frames built from Plan 2's fixtures:
  - `test_no_setup_is_flat`;
  - `test_bias_then_waiting`: a daily setup only, so `waiting` with
    daily_bias `pass` and the others `wait`;
  - `test_full_trigger_levels`: all rows pass, `trigger`, with the
    candidate's entry, stop, target and contracts;
  - `test_symbol_without_model`: NVDA gives `no_model`;
  - `test_research_only_flag`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement. Add `[live] variant = "plain"` to `strategy.toml`.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`. Expected: all pass. Then run `.venv/bin/python -c "from apollo.live.signal import current_signal; ..."` on real MNQ data and print the checklist. Expected: a valid dict (any status).
- [ ] **Step 5: Commit** `feat(live): today's top-down checklist and signal`.

---

### Task 5: The local API

**Files:** `src/apollo/api/{__init__,main}.py`, `tests/api/{__init__,test_api}.py`.

**Interfaces:**
- `create_app(root: Path = Path("data_store"), journal_path: Path | None =
  None) -> FastAPI` with these endpoints (spec 5.9, plus three for the
  journal flow):

| Endpoint | Method | Returns |
|---|---|---|
| `/symbols` | GET | configured symbols with `model_enabled` |
| `/bars?symbol=&tf=&start=&end=` | GET | `[{time, open, high, low, close, volume}]`, UNIX seconds; `tf` ∈ `1m,5m,15m,1h,4h,1d` (4h built from 1h) |
| `/forecast?symbol=` | GET | latest `report.latest` plus coverage stats (cached per day) |
| `/signal?symbol=` | GET | `current_signal(...)` |
| `/journal?symbol=&start=&end=&source=` | GET | entries |
| `/journal` | POST | create (manual); 422 on bad input |
| `/journal/{id}` | GET, PATCH, DELETE | one entry |
| `/journal/take` | POST | `take_trade` from the current signal (body: optional fill, size) |
| `/journal/{id}/close` | POST | `close_trade` |
| `/journal/{id}/screenshot` | POST | multipart image; saved as `journal_media/<id>-<uuid>.<png/jpg>`; max 5 MB |
| `/journal/stats` | GET | `journal_stats` + `calendar` |
| `/backtest/summary?symbol=&layer=` | GET | the latest `reports/backtest_<code>_<layer>.json` (no new run) |
| `/healthz` | GET | `{"ok": true}` |

- `main(argv)`: `python -m apollo.api --port 8000` runs Uvicorn on
  `127.0.0.1`.

- [ ] **Step 1: Write the failing tests** with `fastapi.testclient.TestClient(create_app(tmp_root))` and injected small data:
  - `test_bars_and_symbols`;
  - `test_signal_no_model_for_stock`;
  - `test_journal_crud_roundtrip`;
  - `test_bad_input_422` (negative size, a bad side, a traversal path);
  - `test_screenshot_upload_saved_safely`: an uploaded name `../../evil.png`
    is stored under `journal_media/` with a generated name;
  - `test_cors_only_vite_origin`;
  - `test_backtest_summary_reads_report_without_running`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement with Pydantic models for every request body.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`, `ruff` and `pyright`. Expected: all clean.
- [ ] **Step 5: Real smoke.** Start `.venv/bin/python -m apollo.api` in the background, then `curl` `/healthz`, `/symbols`, `/bars?symbol=MNQ&tf=1h`, `/signal?symbol=MNQ` and `/journal/stats` after running `python -m apollo.journal.import` once. Expected: JSON on all five. Stop the server.
- [ ] **Step 6: Commit** `feat(api): local FastAPI server for the web app`.

---

## Self-review notes

- **Spec coverage:**
  - 5.8 storage, fields, derived values, import, Take trade, close,
    auto-close, signal/manual/skipped split: Tasks 1–3.
  - 5.6 checklist mapping: Task 4.
  - 5.9 endpoints: Task 5.
  - 5.15 journal-review input: Task 3.
- **Deferred to Plan 6:**
  - drawing trades on the chart;
  - the Take trade button and journal sheet UI;
  - the collapsible menu.
- **Deferred to Plan 7:** static snapshot mode (the API is local only).
- **Risk:** the live signal re-runs detection for four pairings on every
  call. Cache per symbol per minute in the API (the frontend polls every 60
  s).
