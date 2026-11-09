# Apollo Predictor, Plan 3b: Market Context (OpenBB) and Investor Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give both models free market context they can't see in price
(volatility indices and scheduled high-impact releases, via OpenBB), measure
whether it helps with a public run log and an ablation, and install seven
Investor Skills where judgment is needed: risk-rule review and journal
review.

**Architecture:**
- **`apollo.context`:** fetches and caches context through OpenBB's keyless
  providers into `data_store/context/`.
- **`apollo.models.context`:** turns that cache into point-in-time features
  per session.
- **The models report:** gains feature sets (`health`, `context`, `both`),
  an ablation, and `runs/log.csv`.
- **Skills:** copied into `.claude/skills/` with their licence. A new
  `journal-review` skill and a risk-rules review document put them to work.

**Tech Stack:** OpenBB 2.x: `openbb-core`, `openbb-index`, `openbb-economy`,
`openbb-cboe`, `openbb-nasdaq`, `openbb-federal-reserve` (all Apache-2.0),
plus `certifi`. Everything from Plan 3.

**Spec:** `docs/superpowers/specs/2026-11-08-apollo-predictor-design.md`,
new sections 5.14 and 5.15, plus 5.13 (run log).

**Builds on:** Plan 3 (branch `plan-3-models`). Merge it into `main` first.

## Global Constraints

- **Keyless providers only:** `cboe`, `nasdaq`, `federal_reserve`. No API
  keys, no paid tiers, no TradingAgents.
- **Certificates:** the python.org build of Python on macOS ships without
  root certificates. Before the first OpenBB call, set
  `os.environ.setdefault("SSL_CERT_FILE", certifi.where())`.
- **Calendar quirk** (verified 2026-11-09): Nasdaq lists US events **one day
  late** and its times mix ET and CT.
  - Apollo uses `listed_date − 1 day` and ignores the listed time.
  - Known truth for tests:
    - CPI on 2024-12-11 and on 2025-06-11;
    - nonfarm payrolls on 2025-07-03;
    - FOMC decisions on 2024-11-07, 2024-12-18 and 2025-01-29.
- **High-impact kinds** (exact Nasdaq event names, case-insensitive):
  - `fomc` = "Fed Interest Rate Decision";
  - `cpi` = "CPI" or "Core CPI";
  - `nfp` = "Nonfarm Payrolls" (not "Private Nonfarm Payrolls");
  - `other` = "PCE Price Index", "Core PCE Price Index", "GDP Growth Rate",
    "Retail Sales", "ISM Manufacturing PMI".

  If a name doesn't match the live feed, the Task 1 network test shows which
  names exist. Fix the name list, not the test dates.
- **Point in time:**
  - vol features for session D use the **last close dated before D**;
  - event flags use events **dated D**, since releases are scheduled in
    advance;
  - the 08:00 ET cutoff from Plan 3 still applies.
- **Context features**, in this order (`CONTEXT_FEATURES`):
  1. `vix`, `vix_chg5`, `vix_term`, `vxn`, `vxn_vix`;
  2. `ev_fomc`, `ev_cpi`, `ev_nfp`, `ev_other`, `ev_any`.
- **Investor Skills:** keep the MIT `LICENSE` and add a `SOURCE.md` (repo
  URL, commit, date). Copy files unchanged.
- **Prose:** humanizer skill (embedded mode). Commits end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Use
  `set -o pipefail` in piped checks.
- **Dependency approval:** Vaughn approved OpenBB on 2026-11-09. Add nothing
  beyond the packages listed here.

## Review Focus

1. **OpenBB is unreachable** (no network, Cboe or Nasdaq down). The collector
   logs it, keeps the existing cache, and the nightly and pre-open jobs still
   finish. Features for days without context are null, and both models cope
   with nulls. *(Pinned in Task 1 and Task 2.)*
2. **A Monday session:** the vol features come from Friday's close, not
   Saturday or Sunday (no rows exist), and not Monday's own close.
   *(Pinned in Task 2.)*
3. **A release scheduled for D but listed on D+1 by Nasdaq:** flagged on D.
   **A release on D+1:** not flagged on D. *(Pinned in Tasks 1 and 2.)*
4. **The same event appears several times** (CPI, Core CPI and Core CPI
   Index rows at once): it counts once per kind; `ev_any` stays 0/1.
   *(Pinned in Task 1.)*
5. **A run that changes nothing** (same feature set and config) still appends
   a new row to `runs/log.csv` with a new attempt number. The log is a record
   of runs, not of distinct configs. *(Pinned in Task 3.)*

---

## File structure

```
pyproject.toml                          + openbb-core, openbb-index, openbb-economy,
                                          openbb-cboe, openbb-nasdaq, openbb-federal-reserve, certifi
src/apollo/context/__init__.py
src/apollo/context/fetch.py             fetch_vol(), fetch_events(), normalise_events(), EVENT_KINDS
src/apollo/context/collect.py           collect_context(), main()   (python -m apollo.context.collect)
src/apollo/models/context.py            context_features(), CONTEXT_FEATURES
src/apollo/models/report.py             + feature sets, ablation, run log, coverage by event (modify)
src/apollo/models/runlog.py             append_run()
.github/workflows/collect.yml           + context step (modify)
.github/workflows/forecast.yml          + context step (modify)
.claude/skills/{ptj-macro-trend,seykota-systematic-trend,turtle-trading,livermore,
                marks-cycles,simons-quant,druckenmiller}/   copied, + LICENSE, SOURCE.md
.claude/skills/journal-review/SKILL.md  new
docs/reviews/risk-rules-review.md       new
tests/context/test_*.py, tests/models/test_context.py, tests/models/test_runlog.py
```

---

### Task 1: Install OpenBB and the context collector

**Files:** `pyproject.toml`, `src/apollo/context/{__init__,fetch,collect}.py`,
`tests/context/{__init__,test_fetch,test_collect}.py`, both workflows.

**Interfaces:**
- `EVENT_KINDS: dict[str, tuple[str, ...]]`: kind → exact event names (from
  Global Constraints).
- `normalise_events(raw: pl.DataFrame) -> pl.DataFrame`.
  - Input columns: `date` (datetime as listed), `country`, `event`.
  - Output: one row per (`date`, `kind`), where `date` is the true release
    date (listed − 1 day), US only, known kinds only. Sorted.
- `fetch_vol(start: date) -> pl.DataFrame` with columns `date`, `vix`,
  `vix3m`, `vxn` (one OpenBB call per index, joined on date).
- `fetch_events(start: date, end: date) -> pl.DataFrame`: the calendar
  fetched in 28-day chunks, then normalised.
- `collect_context(root: Path, today: date, fetch_vol=..., fetch_events=...)
  -> dict[str, int]`, which writes `root/context/vol.parquet` (full refresh
  from 2019-01-01) and `root/context/events.parquet`.
  - Events: merge the cache with a fresh fetch from (today − 60 days) to
    (today + 60 days). The first run fetches from 2024-01-01.
  - A fetch error leaves that file as it was and is logged.
  - Returns row counts.
- `main(argv) -> int`: flags `--root` and `--start-events`. Always exits 0
  and prints what was updated, so a provider outage can't fail the job.

- [ ] **Step 1:** Add the packages to `pyproject.toml`; run `.venv/bin/pip install -e ".[dev]"`, then `.venv/bin/python -c "from openbb import obb; print(obb.index, obb.economy)"`. Expected: no AttributeError (the first import prints "Building...").
- [ ] **Step 2: Write the failing tests**

```python
RAW = pl.DataFrame({
    "date": [datetime(2024, 12, 12, 8, 30), datetime(2024, 12, 12, 8, 30), datetime(2024, 12, 12, 8, 30),
             datetime(2024, 12, 19, 14, 0), datetime(2025, 7, 4, 7, 30), datetime(2025, 7, 4, 7, 30),
             datetime(2024, 12, 12, 9, 0)],
    "country": ["United States"] * 6 + ["Germany"],
    "event": ["CPI", "Core CPI", "Core CPI Index", "Fed Interest Rate Decision",
              "Nonfarm Payrolls", "Private Nonfarm Payrolls", "CPI"],
})

def test_normalise_shifts_and_dedupes():
    out = normalise_events(RAW)
    assert out.select("date", "kind").rows() == [
        (date(2024, 12, 11), "cpi"), (date(2024, 12, 18), "fomc"), (date(2025, 7, 3), "nfp")]

def test_collect_keeps_cache_when_provider_fails(tmp_path):
    collect_context(tmp_path, date(2026, 11, 9), fetch_vol=lambda s: VOL3, fetch_events=lambda s, e: normalise_events(RAW))
    def boom(*a): raise ConnectionError("cboe down")
    counts = collect_context(tmp_path, date(2026, 11, 10), fetch_vol=boom, fetch_events=boom)
    assert counts == {"vol": 3, "events": 3}
    assert pl.read_parquet(tmp_path / "context/vol.parquet").height == 3

@pytest.mark.network
def test_live_calendar_matches_known_release_dates():
    ev = fetch_events(date(2024, 11, 1), date(2025, 7, 10))
    got = set(ev.select("date", "kind").rows())
    for known in [(date(2024, 12, 11), "cpi"), (date(2025, 6, 11), "cpi"), (date(2025, 7, 3), "nfp"),
                  (date(2024, 11, 7), "fomc"), (date(2024, 12, 18), "fomc"), (date(2025, 1, 29), "fomc")]:
        assert known in got, known
```

  `VOL3` is a 3-row frame with columns `date`, `vix`, `vix3m`, `vxn`. Add
  `test_live_vol_has_history` (network): `fetch_vol(date(2019, 1, 1)).height
  > 1800`, with no null `vix`.
- [ ] **Step 3:** Run `.venv/bin/pytest tests/context -q`. Expected: FAIL (import error).
- [ ] **Step 4:** Implement. Import OpenBB lazily inside the fetch functions, after the SSL default, so the rest of the package and the tests never pay for it.
- [ ] **Step 5:** Run `.venv/bin/pytest -q` and `.venv/bin/pytest -m network -q tests/context`. Expected: all pass. If the live test fails on a name, print the US event names for that week and fix `EVENT_KINDS`.
- [ ] **Step 6: Wire the jobs.** Add `.venv/bin/python -m apollo.context.collect --root data_store` before the models step in both `collect.yml` and `forecast.yml`. Run `.venv/bin/python -m apollo.context.collect` locally. Expected: `data_store/context/vol.parquet` and `events.parquet` exist; it prints the row counts.
- [ ] **Step 7: Commit** `feat(context): OpenBB volatility and economic-calendar collector`.

---

### Task 2: Context features

**Files:** `src/apollo/models/context.py`, `tests/models/test_context.py`.

**Interfaces:**
- `CONTEXT_FEATURES` (in the order from Global Constraints).
- `context_features(sessions: pl.DataFrame, vol: pl.DataFrame, events:
  pl.DataFrame) -> pl.DataFrame`, with columns `date` + `CONTEXT_FEATURES`
  and one row per session.
  - **Vol features** use the last `vol` row with `date < session date`:
    - `vix_chg5` = log(vix / vix five rows earlier);
    - `vix_term` = vix / vix3m;
    - `vxn_vix` = vxn / vix.
  - **Event flags** use `events.date == session date`.
  - Empty `vol` or `events` gives null vol features and 0 flags.

- [ ] **Step 1: Write the failing tests**

```python
def test_monday_uses_friday_close():
    vol = pl.DataFrame({"date": [date(2026, 11, 5), date(2026, 11, 6), date(2026, 11, 9)],
                        "vix": [20.0, 25.0, 99.0], "vix3m": [22.0, 20.0, 1.0], "vxn": [24.0, 30.0, 1.0]})
    f = context_features(SESSIONS(date(2026, 11, 9)), vol, EMPTY_EVENTS).row(0, named=True)
    assert f["vix"] == 25.0 and f["vix_term"] == pytest.approx(1.25) and f["vxn_vix"] == pytest.approx(1.2)

def test_event_flags_on_the_day_only():
    ev = pl.DataFrame({"date": [date(2026, 11, 10)], "kind": ["cpi"]})
    f = context_features(SESSIONS(date(2026, 11, 9), date(2026, 11, 10)), EMPTY_VOL, ev)
    assert f["ev_cpi"].to_list() == [0.0, 1.0] and f["ev_any"].to_list() == [0.0, 1.0]
    assert f["vix"].is_null().all()
```

  `SESSIONS(*dates)` builds a frame with `date` and `forecast_at` (08:00 ET).
  `EMPTY_VOL` and `EMPTY_EVENTS` are empty frames with the right schemas.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement with `join_asof(strategy="backward")` on a `date − 1 day` key for vol, and a left join on `date` for events.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(models): point-in-time market context features`.

---

### Task 3: Feature sets, ablation and the run log

**Files:** `src/apollo/models/runlog.py`, `src/apollo/models/report.py`,
`tests/models/test_runlog.py`, `tests/models/test_ledger.py` (real-data test).

**Interfaces:**
- `append_run(path: Path, row: dict) -> int`: appends to `runs/log.csv`,
  writing the header on the first write, and returns the new attempt number
  (rows + 1). Columns:
  - `attempt`, `run_at`, `git_commit`, `code`, `feature_set`,
    `config_hash`;
  - `n_scored`, `logit_acc`, `logit_ll`, `gbm_ll`, `freq_ll`;
  - `range_both`, `range_width`.
- `build_report(root, code, now=None, feature_set: Literal["health",
  "context", "both"] = "both")`.
  - The features are `FEATURES`, `CONTEXT_FEATURES`, or both concatenated.
  - The report adds `feature_set`, `range.by_event` (both-sides coverage for
    `ev_any` = 0 vs 1), and `range.width_by_event`.
- `main` flags: `--features {health,context,both}` (default `both`) and
  `--ablation` (runs all three sets and prints one table). Every
  `build_report` call made by `main` appends one row to the run log.
- `config_hash` = the first 12 hex characters of sha256 over the feature
  names, `FIRST`, `ALPHA`, `CALIB` and both model specs.
- **The log is committed.** `runs/log.csv` is not git-ignored. Spec 5.13
  wants the number of attempts to be public.

- [ ] **Step 1: Write the failing tests**

```python
def test_attempts_count_every_run(tmp_path):
    p = tmp_path / "runs/log.csv"
    assert append_run(p, ROW) == 1 and append_run(p, ROW) == 2
    assert pl.read_csv(p)["attempt"].to_list() == [1, 2]
```

  Extend the real-data test (skipped without `data_store/context/`):
  `build_report(..., feature_set="health")` gives the same regime numbers as
  Plan 3's final run (logit log-loss 1.344, n 239, to 3 decimals). This
  proves the refactor didn't change attempt 1. And `"both"` returns a
  `range.by_event` with keys `"0"` and `"1"`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`, `ruff` and `pyright`. Expected: all clean.
- [ ] **Step 5: Real run.** Run `.venv/bin/python -m apollo.models.report --symbol MNQ --ablation`. Expected: three rows (health, context, both) with accuracy and log-loss for logit, gbm and frequency, plus range hit rate and width, and coverage by event day. **Report the numbers exactly as they come out**, including when context doesn't help. `runs/log.csv` gains 3 rows.
- [ ] **Step 6: Commit** `feat(models): feature-set ablation and public run log`, including `runs/log.csv`.

---

### Task 4: Investor Skills, journal review and the risk-rules review

**Files:**
- `.claude/skills/<7 skills>/` (copied, plus `LICENSE`, `SOURCE.md`)
- `.claude/skills/journal-review/SKILL.md`
- `docs/reviews/risk-rules-review.md`
- `CLAUDE.md` (modify)

**Interfaces:**
- **The `journal-review` skill:**
  - `name: journal-review`.
  - Description: use when Vaughn asks to review his trading journal or a
    week of trades.
  - Process:
    1. Load the journal: Apollo's DuckDB export once Plan 5 exists, until
       then the case study's `data/public/trades_public.csv` and
       `days_public.csv`.
    2. Apply `ptj-macro-trend`, `seykota-systematic-trend`, `turtle-trading`
       and `livermore` as lenses: cutting losses, size versus the drawdown
       limit, following rules versus "Gamba" tags, pressing winners.
    3. Write `docs/reviews/journal-<YYYY-MM-DD>.md` with a verdict per lens,
       the three biggest rule breaks with dates and R-multiples, and one
       change for next week.
  - Rules: report numbers from the data only, no invented trades; humanizer
    for prose.
- **`risk-rules-review.md`:** apply the same four skills to spec 5.6:
  - stop placement;
  - 1–2% risk sizing;
  - "Risk of drawdown limit";
  - at most 2 trades a session;
  - flat by 16:00;
  - no daily loss cap yet;
  - no pyramiding.

  For each lens: what it would keep, change or add, as concrete rule text.
  Then a consolidated table of proposed changes, each marked *proposed: for
  Vaughn to accept or reject before Plan 4*. Use the case-study facts (2.8×
  limit day, Gamba days, 9% journal coverage) as evidence.

- [ ] **Step 1:** Copy the 7 skill folders unchanged from questflowai/investorskills at a pinned commit (record it), with `LICENSE` and `SOURCE.md` in each. Check: `ls .claude/skills` lists the 7 plus `humanizer` and `journal-review`.
- [ ] **Step 2:** Write `journal-review/SKILL.md` as specified.
- [ ] **Step 3:** Run the journal review once on the case-study data, following the new skill. Expected: `docs/reviews/journal-2026-11-09.md` exists, and every number in it traces back to the CSVs.
- [ ] **Step 4:** Write `docs/reviews/risk-rules-review.md` by applying the four skills to spec 5.6.
- [ ] **Step 5:** Update `CLAUDE.md`'s skills list: investor skills for risk and journal review only, never in the signal.
- [ ] **Step 6: Commit** `feat(skills): investor skills, journal review and risk-rules review`.

---

## Self-review notes

- **Spec 5.14 coverage:**
  - sources: Task 1;
  - point-in-time features: Task 2;
  - run log and ablation: Task 3;
  - calendar quirk test: Task 1;
  - TradingAgents excluded: Global Constraints.
- **Spec 5.15 coverage:** install, journal review and risk-rule review:
  Task 4.
- **Deliberately left for Plan 4:**
  - the event-day trading rule (skip or cut size), decided with the
    backtest;
  - adopting any risk-rule changes Vaughn accepts from the review.
- **Honest outcome:** context may not rescue the regime model. The range
  model is the likelier winner, since event days have bigger ranges.
  Whatever happens is logged.
