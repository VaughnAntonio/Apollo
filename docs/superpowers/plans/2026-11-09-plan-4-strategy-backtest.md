# Apollo Predictor, Plan 4 of 7: Strategy and Backtester Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Fractal Model setups into trades with entry, stop, target and
size, simulate them honestly on real MNQ bars, and answer the headline
question: does adding the forecasts (and the proposed risk rules) improve
the Fractal Model out of sample? The answer is reported with confidence
intervals, a prop-firm Monte Carlo and a locked holdout.

**Architecture:**
- A new `apollo.strategy` package:
  - `config` loads the trade, cost, account and risk settings;
  - `candidates` turns setups plus forecasts into candidate trades, each
    with a skip reason;
  - `simulate` walks the bars and fills trades under the risk rules;
  - `metrics` computes expectancy, confidence intervals, benchmarks and the
    Monte Carlo;
  - `backtest` is the CLI. It runs the variants, keeps the holdout locked,
    and writes a report plus a quantstats tearsheet.

**Tech Stack:** Python 3.13, Polars, NumPy, quantstats (picked by Vaughn,
Apache-2.0). Everything else is from Plans 1–3b.

**Spec:** `docs/superpowers/specs/2026-11-08-apollo-predictor-design.md`
(5.6 strategy and sizing, 5.7 backtester, 5.13 holdout, run log, Monte Carlo
and ablation). **Risk proposals:** `docs/reviews/risk-rules-review.md`, rules
1–9.

## Global Constraints

- **Entries use the CISD that confirms after C2 closes** (`after_c2_cisd_*`
  from Plan 2). The earlier "early" CISD fires before the setup is knowable.
- **Fill price:** the open of the bar after the CISD bar (spec 5.7, more
  conservative than 5.6's "CISD close"). From then on, check stop and target
  on each later bar. **If a bar hits both, take the stop.**
- **Headline layer, Daily → 1H:**
  - signals are 1H CISD bars;
  - an entry fill must open between 09:00 and 15:00 ET (the session, spec
    3);
  - everything is flat at **16:00 ET**, at the close of the 15:00 bar.
- **Second layer, 1H → 5m:** 5m CISD bars, entry window **09:30–12:00 ET**
  (spec 5.6), flat at 16:00. Report it with its sample size; it is never the
  headline.
- **Stop:** 1 tick beyond `after_c2_protected`.
- **Target:** C1's opposite extreme. When the variant uses the range filter,
  cap the target at the zone edge (open ± bound).
- **Skip the trade** if reward:risk < **1.5** (spec 5.6).
- **Sizing:** `floor(risk_$ / (stop_points × point_value))`, where risk_$ =
  1% of account size. Skip the trade if that comes to 0. The account is
  **APEX 50k** (size 50,000, trailing drawdown 2,500, locks at +100, eval
  profit target 3,000).
- **Costs per contract per side** (spec 5.7): commission **$0.62** (micros)
  or **$2.25** (E-minis), plus **1 tick** of slippage.
- **Limits:** one open position at a time, at most **2 trades per session**.
- **Forecast inputs** for a session must be out-of-sample. Use only the rows
  Plan 3's walk-forward produced, with the feature set fixed at `both`, the
  best range model from attempts 4–6.
- **The holdout is locked.** Sessions in the last `holdout_months` (default
  **3**, see *Open for Vaughn*) are excluded from every run except one
  explicit `--final` run.
  - The `--final` run writes `runs/holdout.lock` (date + config hash) and
    refuses a second run with a different config.
- **Every backtest run is appended to `runs/backtests.csv`:** attempt,
  run_at, git_commit (`--dirty` aware), layer, variant, config_hash,
  n_trades, expectancy_R, CI low and high, win rate, max drawdown in R, and
  the P(pass eval) at 1%.
- **Prose:** humanizer skill (embedded mode). Commits end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Use
  `set -o pipefail`.

## Variants (the ablation)

Each one is a set of switches in `config/strategy.toml`; the report shows
them side by side.

| Name | Regime filter | Range filter | Risk rules 1–6 | Rules 7–9 |
|---|---|---|---|---|
| `plain` | off | off | off | off |
| `regime` | on | off | off | off |
| `range` | off | on | off | off |
| `both` | on | on | off | off |
| `plain+risk` | off | off | on | off |
| `both+risk` | on | on | on | off |
| `both+risk+be` | on | on | on | 7 (breakeven at +1R) |
| `both+risk+fomc` | on | on | on | 8 (no new trades after 13:30 ET on FOMC days) |
| `both+risk+event` | on | on | on | 9 (half size on any high-impact day) |

- **Regime filter** (spec 5.6): bull setups need P(chop) < 0.5 and P(trend
  down) < P(trend up); bear setups mirror that.
- **Range filter:** the target is capped at the zone edge, and the trade is
  skipped if the uncapped target lies more than 10% of the zone width beyond
  the edge.
- **Risk rules 1–6** (from the risk review):
  1. no new trades after −2R realised in the session;
  2. skip a trade whose planned loss is more than 25% of the cushion left
     above the trailing threshold;
  3. size at 0.5% while the cushion is below half the drawdown limit, until
     a new equity high;
  4. not applicable to a backtest (manual trades), so ignored here;
  5. skip if the stop is wider than half the zone (needs the range
     forecast; off when there is none);
  6. minimum stop of 4 ticks.

## Review Focus

1. **A setup whose CISD bar is the last bar of the session** (15:00 bar).
   The fill would be the next morning, so the trade is skipped with the
   reason `outside_window`, never carried overnight. *(Pinned in Task 2.)*
2. **The stop and target are hit in the same bar.** The trade loses at the
   stop, and slippage is still applied. *(Pinned in Task 3.)*
3. **The account breaches its trailing drawdown in the middle of the run.**
   The simulation stops trading that account and records `breached_at`.
   Later setups get the skip reason `account_breached`. *(Pinned in Task 3.)*
4. **A variant needs a forecast that doesn't exist** (before the models'
   first out-of-sample session). The candidate gets the skip reason
   `no_forecast` and is counted. The plain variant still trades those
   sessions, so the report states each variant's sample size. *(Pinned in
   Task 2.)*
5. **The holdout leaks.** Any non-`--final` run over a date range that
   reaches into the holdout must cut the range there. A test runs with
   synthetic dates across the boundary. *(Pinned in Task 5.)*

---

## File structure

```
pyproject.toml                       + quantstats
config/strategy.toml                 + [trade] [costs] [risk] [variants.*] [backtest] (modify)
config/accounts.toml                 APEX 50k, TOPSTEP 50k presets
src/apollo/strategy/__init__.py
src/apollo/strategy/config.py        TradeConfig, Account, Variant, load_trade_config()
src/apollo/strategy/candidates.py    build_candidates(), SKIP_REASONS
src/apollo/strategy/simulate.py      simulate(), AccountState
src/apollo/strategy/metrics.py       expectancy_ci(), equity_stats(), benchmarks(), prop_monte_carlo()
src/apollo/strategy/backtest.py      run_backtest(), main()   (python -m apollo.strategy.backtest)
src/apollo/models/report.py          + forecast_frame() (modify)
tests/strategy/test_*.py
```

---

### Task 1: Trading config and forecast frame

**Files:** `pyproject.toml`, `config/strategy.toml`, `config/accounts.toml`,
`src/apollo/strategy/{__init__,config}.py`, `src/apollo/models/report.py`,
`tests/strategy/{__init__,test_config}.py`, `tests/models/test_runlog.py`
(real-data test).

**Interfaces:**
- `@dataclass(frozen=True) Account` with `name`, `size`, `drawdown`, `lock`
  (profit above the start where the trailing threshold stops), and
  `profit_target`. Presets:
  - **APEX 50k:** 50,000 / 2,500 / 100 / 3,000;
  - **TOPSTEP 50k:** 50,000 / 2,000 / 0 / 3,000.
- `@dataclass(frozen=True) Variant` with `regime: bool`, `range: bool`,
  `risk_rules: bool`, `breakeven: bool`, `fomc_cutoff: bool`,
  `event_half: bool`.
- `@dataclass(frozen=True) TradeConfig` with:
  - `risk_pct`, `min_rr`, `max_trades`, `stop_ticks_beyond`;
  - `windows: dict[str, tuple[time, time]]` (entry windows per layer);
  - `flat_at: time`;
  - `commission: dict[str, float]` (by `"micro"`/`"emini"`), `slip_ticks`;
  - `daily_cap_r`, `cushion_frac`, `step_down_pct`, `min_stop_ticks`,
    `max_stop_zone_frac`, `range_room`;
  - `holdout_months`, `account`, `variants: dict[str, Variant]`.
- `load_trade_config(path=CONFIG_DIR/"strategy.toml") -> TradeConfig`.
- `forecast_frame(root, code, feature_set="both") -> pl.DataFrame`: one row
  per out-of-sample session, with columns:
  - `date`, `open` (09:00 bar), `p_trend_up`, `p_trend_down`, `p_chop`,
    `p_normal`;
  - `up_bound`, `down_bound` (null before calibration);
  - `ev_fomc`, `ev_any`.

  It is built from `build_report`'s scored rows; don't recompute the models.

- [ ] **Step 1:** Add `quantstats` to the dependencies and install. Expected: `python -c "import quantstats"` exits 0.
- [ ] **Step 2: Write the failing tests**

```python
def test_config_defaults():
    c = load_trade_config()
    assert (c.risk_pct, c.min_rr, c.max_trades, c.flat_at) == (0.01, 1.5, 2, time(16, 0))
    assert c.account.name == "APEX 50k" and c.account.drawdown == 2500 and c.holdout_months == 3
    assert set(c.variants) == {"plain", "regime", "range", "both", "plain+risk", "both+risk",
                               "both+risk+be", "both+risk+fomc", "both+risk+event"}
    assert c.variants["both+risk+be"].breakeven and not c.variants["both+risk"].breakeven
```

  Real-data test (skipped without `data_store`): `forecast_frame` has no row
  dated before the first out-of-sample session, and `up_bound` is null for
  exactly the first 30 rows.
- [ ] **Step 3:** Run `.venv/bin/pytest tests/strategy -q`. Expected: FAIL.
- [ ] **Step 4:** Implement the TOML sections and loaders, and extract `forecast_frame` from `build_report`.
- [ ] **Step 5:** Run `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 6: Commit** `feat(strategy): trading config, account presets and forecast frame`.

---

### Task 2: Candidate trades

**Files:** `src/apollo/strategy/candidates.py`, `tests/strategy/test_candidates.py`.

**Interfaces:**
- `SKIP_REASONS = ("no_cisd", "outside_window", "no_forecast", "regime",
  "range_room", "rr", "stop_too_tight", "stop_too_wide", "fomc_cutoff")`.
- `build_candidates(setups: pl.DataFrame, ltf: pl.DataFrame, forecasts:
  pl.DataFrame, sym: Symbol, cfg: TradeConfig, variant: Variant, layer:
  Literal["D-1H","1H-5m"]) -> pl.DataFrame`, one row per setup, with columns:
  - `setup_ts`, `direction`, `signal_ts`, `entry_ts` (next LTF bar open),
    `session`;
  - `stop`, `target`, `target_capped` (bool), `rr`, `planned_stop_pts`;
  - `half_size` (event rule);
  - `skip` (null or one of `SKIP_REASONS`).

  The checks run in the order the list shows. The first failure sets
  `skip`.
- **Prices:**
  - `rr` uses the **entry bar's open** (known at fill) as the entry price;
  - stop = protected ∓ `stop_ticks_beyond` × tick;
  - the target and its cap come from the Global Constraints.

- [ ] **Step 1: Write the failing tests** (hand-built 1H bars and setup rows; `ohlc` fixture)

```python
def test_bull_trade_levels(ohlc):
    # setup: bull, after_c2_protected 100.0, C1 high 110.0, CISD bar opens 2026-11-03 10:00 ET;
    # the next 1H bar (11:00 ET) opens at 102.0
    c = build_candidates(SETUP, ohlc(BARS, "2026-11-03 09:00", "1h"), NO_FORECASTS, MNQ, CFG, PLAIN, "D-1H").row(0, named=True)
    assert (c["stop"], c["target"], c["rr"]) == (99.75, 110.0, pytest.approx(8 / 2.25))
    assert c["skip"] is None and str(c["entry_ts"]) == "2026-11-03 16:00:00+00:00"

def test_last_bar_of_session_is_outside_window(...):   # CISD on the 15:00 bar
    assert build_candidates(...)["skip"][0] == "outside_window"

def test_range_cap_and_room(...):       # zone up_bound puts the edge at 106: capped; at 99% beyond → range_room
def test_no_forecast_only_blocks_filtered_variants(...):  # plain trades, both → "no_forecast"
def test_rr_and_stop_bounds(...):       # rr 1.4 → "rr"; 3-tick stop with risk rules → "stop_too_tight"
def test_fomc_cutoff(...):              # FOMC day, entry 13:30 with fomc_cutoff → "fomc_cutoff"; 13:00 ok
```

  Write each test with concrete numbers in the same style as the first. The
  comments give the exact case each one pins.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement. Map a setup to its session through the ET date of `entry_ts`.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(strategy): candidate trades with skip reasons`.

---

### Task 3: The simulator

**Files:** `src/apollo/strategy/simulate.py`, `tests/strategy/test_simulate.py`.

**Interfaces:**
- `simulate(cands: pl.DataFrame, bars: pl.DataFrame, sym: Symbol, cfg:
  TradeConfig, variant: Variant) -> tuple[pl.DataFrame, dict]`.
  - **The trades frame** holds every candidate without a `skip`, with these
    columns:
    - `entry_ts`, `exit_ts`, `entry`, `exit`, `contracts`;
    - `exit_reason` (`stop`, `target`, `flat`, `breakeven`);
    - `gross_$`, `costs_$`, `net_$`, `r` (net $ ÷ planned risk $);
    - `skip` (late skips: `max_trades`, `daily_cap`, `cushion`, `size_zero`,
      `in_position`, `account_breached`).
  - **The state dict** holds `equity_curve` (per session), `peak`,
    `threshold`, `breached_at`.
- **Walk order:** trades in `entry_ts` order. Each trade walks the bars from
  `entry_ts`:
  - stop first if a bar hits both;
  - exit at the close of the last bar before `flat_at`.
- **Breakeven variant:** once a bar's favourable extreme reaches +1R, the
  stop moves to entry. Check it from the *next* bar, never the same one.
- **Account trailing threshold:** `min(peak − drawdown, start + lock)`,
  updated at each trade's exit. A breach stops all trading.
- **Costs:** 2 sides × contracts × (commission + slip_ticks × tick ×
  point_value).

- [ ] **Step 1: Write the failing tests** with exact $ and R:
  - `test_target_hit`;
  - `test_same_bar_stop_wins`;
  - `test_flat_at_four`;
  - `test_breakeven_moves_stop_next_bar_only`;
  - `test_daily_cap_after_minus_two_r`;
  - `test_cushion_rule_skips_big_risk`;
  - `test_step_down_size_after_drawdown`;
  - `test_breach_stops_trading`;
  - `test_one_position_and_max_trades`.

  Each states its bars, its candidate rows and the expected exit, P&L and
  skip reason. Example:

```python
def test_same_bar_stop_wins(ohlc):
    # bull entry 102 (open), stop 99.75, target 110; the next bar trades 99 to 111
    t, _ = simulate(cands_one(stop=99.75, target=110.0), ohlc([(102, 103, 101, 102.5), (102.5, 111, 99, 105)], ...), MNQ, CFG, PLAIN)
    row = t.row(0, named=True)
    assert row["exit_reason"] == "stop" and row["exit"] == pytest.approx(99.75 - 0.25)   # slippage
```

- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement as one ordered loop. The bar data is small: 2 years of 1H bars.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(strategy): trade simulator with costs, account and risk rules`.

---

### Task 4: Metrics, benchmarks and the prop-firm Monte Carlo

**Files:** `src/apollo/strategy/metrics.py`, `tests/strategy/test_metrics.py`.

**Interfaces:**
- `expectancy_ci(r: np.ndarray, n_boot=10_000, seed=7) -> dict` with `n`,
  `mean`, `low`, `high` (95% bootstrap percentile) and `win_rate`.
- `equity_stats(trades) -> dict` with `net_$`, `max_dd_$`, `max_dd_r`,
  `profit_factor`, `trades_per_month`.
- `benchmarks(d1: pl.DataFrame, start: date, end: date, sym) -> dict` over
  the same window:
  - `buy_hold_$`: 1 contract, close to close;
  - `ma_20_50_$`: long 1 contract the next day when SMA20 > SMA50, using
    only signals from earlier days, the case study's rule.
- `prop_monte_carlo(r: np.ndarray, account: Account, risk_pct: float,
  n_paths=10_000, max_trades=200, seed=7) -> dict`:
  - resample R-multiples with replacement;
  - $ per R = `risk_pct × size`;
  - apply the trailing threshold and lock;
  - return `p_pass` (profit target before a breach), `p_breach` (breach
    within `max_trades`) and `median_trades_to_pass`.

- [ ] **Step 1: Write the failing tests**

```python
def test_ci_contains_mean_and_shrinks_with_n(): ...      # n=20 vs n=2000 of the same distribution
def test_monte_carlo_extremes():
    acc = Account("x", 50_000, 2_500, 100, 3_000)
    assert prop_monte_carlo(np.full(50, 1.0), acc, 0.01)["p_pass"] == 1.0   # always +1R → passes
    assert prop_monte_carlo(np.full(50, -1.0), acc, 0.01)["p_breach"] == 1.0
def test_risk_two_pct_passes_faster_but_breaches_more(): ...  # mixed R, p_breach(2%) > p_breach(1%)
def test_ma_rule_uses_yesterdays_signal(): ...            # flip on day k trades from day k+1
```

- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(strategy): expectancy CIs, benchmarks and prop-firm Monte Carlo`.

---

### Task 5: Backtest CLI, holdout lock, run log and tearsheet

**Files:** `src/apollo/strategy/backtest.py`, `tests/strategy/test_backtest.py`, `.gitignore`.

**Interfaces:**
- `run_backtest(root, code, layer, variant_name, cfg, final=False) -> dict`:
  loads the bars, runs `run_model` for the layer, `forecast_frame`,
  candidates and the simulator, applies the holdout cut, then returns the
  metrics, the skip-reason counts, the benchmarks, the Monte Carlo at 1% and
  2%, and the trade list.
- `holdout_start(session_dates: list[date], months: int) -> date`: the first
  session in the last `months` calendar months.
- `main(argv)`:
  - flags `--symbol`, `--layer {D-1H,1H-5m}`, `--variants all|<names>`,
    `--final`, `--tearsheet`;
  - prints one table (variant, n trades, expectancy R with CI, win rate, max
    DD R, P(pass) at 1% and 2%, top skip reasons) and the benchmarks;
  - writes `reports/backtest_<code>_<layer>.json`;
  - with `--tearsheet`, writes `reports/tearsheet_<code>_<layer>_<variant>.html`
    from the daily net-$ series via quantstats;
  - appends every variant run to `runs/backtests.csv`.
- **`--final`:** writes `runs/holdout.lock` with the date, config hash and
  variants. A second `--final` with a different config hash exits 1 with a
  message. The same hash is allowed: re-printing is fine, but it's logged as
  a new attempt.

- [ ] **Step 1: Write the failing tests**:
  - `test_holdout_start`: 3 months back from the last session date.
  - `test_non_final_run_never_sees_holdout`: synthetic setups on both sides
    of the boundary; only the earlier ones become trades.
  - `test_final_lock_refuses_changed_config`.
  - `test_backtests_log_appends_per_variant`.
  - A real-data smoke test (skipped without `data_store`):
    `run_backtest(..., "D-1H", "plain")` returns n_trades > 0, and
    `skip_counts` sums to the setup count.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement. Add `reports/` (already ignored) and nothing else to `.gitignore`. `runs/backtests.csv` is committed.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`, `ruff`, `pyright`. Expected: all clean.
- [ ] **Step 5: Real run.** Run `.venv/bin/python -m apollo.strategy.backtest --symbol MNQ --layer D-1H --variants all --tearsheet`, then the same with `--layer 1H-5m`. Expected: two tables. **Report every number as it comes out**, including variants that are worse than `plain`, wide CIs, and how few trades each has. Don't run `--final`: that's Vaughn's call after he has seen the in-sample results.
- [ ] **Step 6: Commit** `feat(strategy): backtest CLI with locked holdout, run log and tearsheets`, including `runs/backtests.csv`.

---

## Open for Vaughn (asked with plan approval)

1. **Holdout length.** The forecast filters only exist from about Jan 2026,
   because Plan 3 needs 250 sessions before its first out-of-sample
   forecast. Spec 5.13 says to lock the last 6 months, which would leave
   only ~4 months to develop the filters on.
   - **The plan defaults to 3 months.** That leaves about 7 months to
     develop on and keeps about 60 sessions untouched.
2. **Risk rules 1–9.** The plan doesn't ask you to accept them yet. It tests
   them as variants. You choose after seeing the numbers, and that choice
   also decides what the `--final` run uses.

## Self-review notes

- **Spec coverage:**
  - 5.6 entry, stop, target, R:R, sizing, limits, flat time: Tasks 2–3.
  - 5.7 fill rule, same-bar rule, costs, two layers, filters on/off,
    benchmarks, bootstrap CIs, tearsheet: Tasks 2–5.
  - 5.13 holdout, run log, Monte Carlo, ablation: Tasks 4–5.
  - Risk review rules 1–3 and 5–9: the variants.
- **Not in this plan:**
  - the journal benchmark (needs Plan 5's journal store); the report quotes
    the case study's numbers as text for now;
  - SMT confirmation (spec v2);
  - the positional entry variant, which spec 5.6 lists. It's left out to
    keep the variant count down, and noted in the report as not tested.
- **Expected sample sizes:**
  - Daily → 1H: about 75 setups in 2 years, so filtered variants trade on
    the last ~10 months only.
  - 1H → 5m: about 130 setups on about 60 days.

  Wide confidence intervals are expected, and the report states them.
