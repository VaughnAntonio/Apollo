# Apollo Predictor, Plan 3 of 7: Regime Detector and Range Forecaster Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Forecast, before each New York session, what kind of session it will
be (trend up, trend down, chop, normal) and a range its high and low stay
inside about 90% of the time. Both are scored walk-forward against baselines,
and every live forecast goes into a ledger before the session it predicts.

**Architecture:**
- A new `apollo.models` package:
  - `sessions` builds one row per New York session (label, excursions, roll
    flag);
  - `returns` cleans 1H returns of contract-roll jumps;
  - `health` computes predictive-maintenance features from data known at the
    09:00 ET forecast time;
  - `walkforward` is a generic expanding-window, monthly-refit loop;
  - `regime` and `range` hold the two models and their baselines;
  - `ledger` writes and scores daily forecasts;
  - `report` is the CLI that writes the metrics the Models page (Plan 7) will
    read.

**Tech Stack:** Python 3.13, Polars, NumPy, SciPy (STFT, Hilbert),
scikit-learn (logistic regression, gradient boosting), MAPIE 1.x (reference
check for the conformal bound).

**Spec:** `docs/superpowers/specs/2026-11-08-apollo-predictor-design.md`
(5.4 regime detector, 5.5 range forecaster, 5.13 forecast ledger, section 3
honesty rules).

## Global Constraints

- **New dependencies** (all listed in spec 5.1, which Vaughn approved):
  `numpy`, `scipy`, `scikit-learn`, `mapie`. Nothing else.
- **v1 session = 09:00–16:00 ET**, built from the seven 1H bars that open
  09:00 to 15:00.
  - Reason: Yahoo's 1H bars sit on the hour, so 09:30 isn't available over
    the 2-year history.
  - The forecast is made at **09:00 ET** on the session's date, from bars
    that **closed by 09:00 ET**.
  - Write this in the model card (Plan 7). Revisit when the collector has a
    year of 5m bars.
- **Label (spec 5.4, same thresholds as the case study):** body ratio =
  |close − open| / (high − low).
  - `trend_up`: ratio > 0.6 and close > open.
  - `trend_down`: ratio > 0.6 and close < open.
  - `chop`: ratio < 0.3.
  - `normal`: everything else.
- **Excursions (spec 5.5):** `up_exc = high − open`, `down_exc = open − low`,
  in points.
- **No lookahead.** Every feature row for session D uses only bars with close
  ≤ 09:00 ET on D, and daily bars dated before D. A guard test perturbs
  future bars and checks the features don't move.
- **Walk-forward:**
  - expanding training window;
  - first fit after **250 sessions**;
  - refit on the first session of each calendar month;
  - every reported number is out-of-sample.
- **Range:**
  - each excursion gets a one-sided upper bound at **95%**, so by Bonferroni
    the zone covers both sides about 90% of the time;
  - the conformal calibration window is the **last 120 out-of-sample
    residuals**.
- **Coverage reported** = the share of sessions where the high **and** the
  low both stayed inside `[open − down_bound, open + up_bound]`.
- **Sessions are dropped from training and scoring** when their feature
  window or session touches a roll jump that couldn't be cleaned (see Task 2),
  or when the session has fewer than 7 bars. They're counted and reported.
- **Prose** (docstrings, comments, report text, commits): humanizer skill,
  embedded mode. Commit messages end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Run `set -o pipefail` in any piped check command, so a failing check can't
  hide behind `tail`.

## Review Focus

1. **A short session** (holiday, half-day, missing bars): fewer than 7 bars,
   so it isn't labelled and isn't scored. It's counted in `dropped`.
   *(Pinned in Task 1.)*
2. **A class never seen in a training fold** (e.g. no `trend_down` in the
   first 250 sessions). The model still outputs all four probabilities, with
   0 for the unseen class, and log-loss stays finite (clipped).
   *(Pinned in Task 4.)*
3. **The first 120 sessions after the first fit have fewer than 120
   residuals.** The conformal bound uses whatever residuals exist once there
   are at least 30, and no bound before that. *(Pinned in Task 5.)*
4. **A roll jump inside the feature window** (Yahoo's continuous `=F` series
   switches contracts). Features must not show a fake volatility spike;
   that return is zeroed. *(Pinned in Task 2.)*
5. **Running the ledger writer twice on one day.** The second run overwrites
   the same file with the same forecast, and never writes a forecast for a
   session that has already started (after 09:00 ET).
   *(Pinned in Task 6.)*

---

## File structure

```
pyproject.toml                       + numpy, scipy, scikit-learn, mapie
src/apollo/models/__init__.py
src/apollo/models/sessions.py        build_sessions(), LABELS
src/apollo/models/returns.py         clean_returns()
src/apollo/models/health.py          health_features(), FEATURES
src/apollo/models/walkforward.py     refit_points(), walk_forward()
src/apollo/models/regime.py          fit_regime(), regime_baselines(), regime_metrics()
src/apollo/models/range.py           conformal_upper(), range_forecasts(), coverage()
src/apollo/models/ledger.py          write_forecast(), score_ledger()
src/apollo/models/report.py          build_report(), main()  (python -m apollo.models.report)
.github/workflows/collect.yml        + ledger write/score after collection (modify)
tests/models/test_*.py
```

---

### Task 1: Dependencies and the session table

**Files:**
- Modify: `pyproject.toml`
- Create: `src/apollo/models/__init__.py`, `src/apollo/models/sessions.py`
- Test: `tests/models/__init__.py`, `tests/models/test_sessions.py`

**Interfaces:**
- Consumes: `add_session_columns`, `mark_roll_days`, `load_symbols` (Plan 1).
- Produces:
  - `LABELS = ("trend_up", "trend_down", "chop", "normal")`.
  - `build_sessions(h1: pl.DataFrame, sym: Symbol) -> pl.DataFrame`: one row
    per weekday ET date that has 1H bars opening 09:00–15:00, with columns:
    - `date` (Date), `forecast_at` (Datetime UTC, 09:00 ET);
    - `open` (the 09:00 bar's open), `high`, `low`, `close` (the 15:00 bar's
      close);
    - `bars` (Int), `body_ratio`, `label` (null when bars < 7);
    - `up_exc`, `down_exc`, `near_roll`.

- [ ] **Step 1:** Add `numpy`, `scipy`, `scikit-learn`, `mapie` to `dependencies`. Run `.venv/bin/pip install -e ".[dev]"`. Expected: installs cleanly; `python -c "import mapie, sklearn, scipy"` exits 0.
- [ ] **Step 2: Write the failing tests** (the 1H rows use the `ohlc` fixture, starting 09:00 ET)

```python
def test_trend_up_session(ohlc):
    rows = [(100, 101, 99.5, 100.8), (100.8, 102, 100.5, 101.9), (101.9, 103, 101.8, 102.9),
            (102.9, 104, 102.5, 103.8), (103.8, 105, 103.6, 104.9), (104.9, 106, 104.5, 105.8),
            (105.8, 107, 105.6, 106.9)]
    s = build_sessions(ohlc(rows, "2026-11-03 09:00", "1h"), load_symbols()["MNQ"]).row(0, named=True)
    assert (s["open"], s["high"], s["low"], s["close"]) == (100.0, 107.0, 99.5, 106.9)
    assert s["label"] == "trend_up" and s["up_exc"] == 7.0 and s["down_exc"] == 0.5
    assert str(s["forecast_at"]) == "2026-11-03 14:00:00+00:00"

@pytest.mark.parametrize("o, c, h, lo, label", [
    (100, 100.4, 101, 99, "chop"),          # body 0.4 / range 2 = 0.2
    (100, 98.4, 100.2, 98.2, "trend_down"),  # body 1.6 / range 2 = 0.8
    (100, 100.9, 101, 99, "normal"),         # body 0.9 / range 2 = 0.45
])
def test_label_thresholds(ohlc, o, c, h, lo, label):
    # seven bars: first opens at o, one bar touches h, one touches lo, last closes at c
    rows = [(o, o, o, o), (o, h, o, o), (o, o, lo, o), (o, o, o, o), (o, o, o, o), (o, o, o, o), (o, o, o, c)]
    rows = [(a, max(a, b2, d), min(a, b3, d), d) for a, b2, b3, d in rows]
    assert build_sessions(ohlc(rows, "2026-11-04 09:00", "1h"), load_symbols()["MNQ"])["label"][0] == label

def test_short_session_unlabelled(ohlc):
    s = build_sessions(ohlc([(100, 101, 99, 100.5)] * 4, "2026-11-27 09:00", "1h"), load_symbols()["MNQ"])
    assert s["bars"][0] == 4 and s["label"][0] is None
```

- [ ] **Step 3:** Run `.venv/bin/pytest tests/models -q`. Expected: FAIL, import error.
- [ ] **Step 4:** Implement with Polars:
  - filter weekday bars whose ET open hour is 9–15;
  - group by ET date;
  - aggregate first/max/min/last and count;
  - compute the label with `pl.when`;
  - `near_roll` via `mark_roll_days` on the session's date.
- [ ] **Step 5:** Run `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 6: Commit** `feat(models): dependencies and New York session table`.

---

### Task 2: Roll-clean 1H returns

**Files:**
- Create: `src/apollo/models/returns.py`
- Test: `tests/models/test_returns.py`

**Interfaces:**
- Consumes: `roll_windows` (Plan 1), `Symbol`.
- Produces: `clean_returns(h1: pl.DataFrame, sym: Symbol) -> pl.DataFrame`,
  which adds:
  - `ret`: log return close-to-close;
  - `roll_jump` (Bool): true on the one bar per roll window whose |ret| is
    the largest **and** more than 5× the median |ret| of that window; `ret`
    is set to 0 there.
  - Symbols with `roll_rule == "none"` never flag.

- [ ] **Step 1: Write the failing test**

```python
def test_roll_jump_zeroed(bars):
    h = bars("2026-03-12 09:00", 200, "1h")            # inside the March 2026 window (Mar 12-20)
    h = h.with_columns(pl.when(pl.int_range(pl.len()) >= 100).then(pl.col("close") + 300)
                       .otherwise(pl.col("close")).alias("close"))
    out = clean_returns(h, load_symbols()["MNQ"])
    assert out["roll_jump"].sum() == 1 and out.filter("roll_jump")["ret"][0] == 0.0
    assert out["ret"].abs().max() < 0.02                # no fake spike left
```

  Add `test_no_flag_outside_window_or_for_none_rule`: the same jump in May
  for MNQ, and in March for MGC, gives `roll_jump.sum() == 0`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement. The window membership uses the ET date of each bar.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(models): roll-clean hourly returns`.

---

### Task 3: Health features (the predictive-maintenance part)

**Files:**
- Create: `src/apollo/models/health.py`
- Test: `tests/models/test_health.py`

**Interfaces:**
- Consumes: `build_sessions` (Task 1), `clean_returns` (Task 2), daily bars
  (`read_bars(..., "1d")`).
- Produces:
  - `FEATURES: tuple[str, ...]`, in this order:
    1. `rms`, `rms_slope`, `kurt`, `skew`, `crest`;
    2. `env_mean`, `env_kurt`;
    3. `sk_low`, `sk_mid`, `sk_high`;
    4. `rng_24h`, `gap`;
    5. `d_ma50`, `d_atr`, `prev_label_*` (one-hot, four columns).
  - `health_features(sessions: pl.DataFrame, h1: pl.DataFrame, d1:
    pl.DataFrame, sym: Symbol, window: int = 120) -> pl.DataFrame`: one row
    per session, with `date` plus `FEATURES` (null when fewer than `window`
    clean returns exist before `forecast_at`).
- **Definitions.** `r` = the last `window` cleaned 1H returns whose bar
  closed ≤ `forecast_at`.
  - `rms` = sqrt(mean r²).
  - `rms_slope` = rms(last 24) / rms(previous 96) − 1.
  - `kurt`, `skew` = `scipy.stats` (Fisher).
  - `crest` = max|r| / rms.
  - `env` = |`scipy.signal.hilbert`(r)|; `env_mean`, `env_kurt`.
  - **Spectral kurtosis:** `scipy.signal.stft(r, nperseg=24, noverlap=12)`;
    SK(f) = mean_t |X|⁴ / (mean_t |X|²)² − 2. Average SK over three equal
    frequency bands (excluding DC) to give `sk_low`, `sk_mid`, `sk_high`.
  - `rng_24h` = mean (high − low)/close over the last 24 bars.
  - `gap` = 09:00 open / close of the last bar before 09:00 − 1.
  - `d_ma50` = last daily close before D / its 50-day SMA − 1.
  - `d_atr` = ATR14 / close on daily bars before D.
  - `prev_label_*` = one-hot of the previous session's label (all 0 when it
    is null).

- [ ] **Step 1: Write the failing tests**

```python
def test_features_known_values():
    r = np.array([0.01, -0.01] * 60)                 # alternating: rms 0.01, crest 1, kurt -2
    f = _stats(r)                                     # pure helper exposed for testing
    assert f["rms"] == pytest.approx(0.01) and f["crest"] == pytest.approx(1.0)
    assert f["kurt"] == pytest.approx(-2.0)

def test_spike_raises_crest_and_sk():
    rng = np.random.default_rng(0); r = rng.normal(0, 0.001, 120); s = r.copy(); s[110] = 0.02
    assert _stats(s)["crest"] > 3 * _stats(r)["crest"] and _stats(s)["sk_high"] > _stats(r)["sk_high"]

def test_no_lookahead(synthetic_frames):
    sess, h1, d1, sym = synthetic_frames
    base = health_features(sess, h1, d1, sym)
    D = sess["forecast_at"][-30]
    later = pl.col("ts") >= D                                       # 1H bars opening at or after 09:00 on D
    day_d_or_later = (pl.col("ts") + timedelta(hours=6)).dt.date() >= D.date()  # daily bar dated D or later
    bump = lambda cond: pl.when(cond).then(pl.col("close") * 1.1).otherwise(pl.col("close")).alias("close")
    h1_mod, d1_mod = h1.with_columns(bump(later)), d1.with_columns(bump(day_d_or_later))
    mod = health_features(sess, h1_mod, d1_mod, sym)
    keep = pl.col("date") <= D.date()
    assert base.filter(keep).equals(mod.filter(keep))
```

  Fixture `synthetic_frames` in `tests/models/conftest.py`: 1H bars from
  2026-01-05 18:00 ET for 60 days of weekday Globex hours with a seeded
  random-walk close (`np.random.default_rng(7)`, steps of 0.1%), daily bars
  aggregated from them by `globex_date` and stamped 18:00 ET the day before,
  `build_sessions(h1, MNQ)`, and the MNQ `Symbol`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement:
  - `_stats(r: np.ndarray) -> dict[str, float]` for the window statistics;
  - `health_features` loops over sessions with a binary search (`np.searchsorted`) into the bar closes.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(models): predictive-maintenance health features`.

---

### Task 4: Walk-forward loop and the regime detector

**Files:**
- Create: `src/apollo/models/walkforward.py`, `src/apollo/models/regime.py`
- Test: `tests/models/test_walkforward.py`, `tests/models/test_regime.py`

**Interfaces:**
- Produces:
  - `refit_points(dates: list[date], first: int = 250) -> list[int]`: the
    row indices where a refit happens (index `first`, then the first row of
    each later month).
  - `walk_forward(X: np.ndarray, y: np.ndarray, dates: list[date], fit:
    Callable[[np.ndarray, np.ndarray], Any], predict: Callable[[Any,
    np.ndarray], np.ndarray], first: int = 250) -> np.ndarray`: predictions
    for rows ≥ `first` (NaN rows before). Training data at each refit = all
    rows strictly before the refit index.
  - `fit_regime(kind: Literal["logit","gbm"])` returns `(fit, predict)` for
    `walk_forward`. `predict` returns probabilities with 4 columns in
    `LABELS` order, filling unseen classes with 0.
    - logit = `StandardScaler` + `LogisticRegression(max_iter=1000)`;
    - gbm = `HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05,
      max_iter=200)`.
  - `regime_baselines(labels: list[str], dates, first=250) -> dict[str,
    np.ndarray]`: `majority` (the most common label in training) and
    `yesterday` (the previous session's label), as one-hot probabilities.
  - `regime_metrics(proba: np.ndarray, labels: list[str]) -> dict` with
    `accuracy`, `log_loss` (probabilities clipped to [1e-6, 1]), `n`,
    `confusion` (4×4 list).

- [ ] **Step 1: Write the failing tests**

```python
def test_refit_points_monthly():
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(400)]
    pts = refit_points(dates, first=250)
    assert pts[0] == 250 and all(dates[p].day == 1 for p in pts[1:])

def test_walk_forward_never_trains_on_future():
    seen = []
    def fit(X, y): seen.append(len(X)); return None
    walk_forward(np.zeros((300, 1)), np.zeros(300), DATES_300, fit, lambda m, X: np.zeros(len(X)))
    assert seen[0] == 250 and seen == sorted(seen)

def test_unseen_class_gets_zero_and_finite_loss():
    X = np.random.default_rng(0).normal(size=(300, 3)); y = np.array(["chop", "normal"] * 150)
    fit, predict = fit_regime("logit")
    p = walk_forward(X, y, DATES_300, fit, predict)[250:]
    assert p.shape == (50, 4) and (p[:, LABELS.index("trend_down")] == 0).all()
    assert np.isfinite(regime_metrics(p, list(y[250:]))["log_loss"])

def test_logit_learns_separable_signal():
    X = np.random.default_rng(3).normal(size=(300, 2))
    y = np.where(X[:, 0] > 0.5, "trend_up", np.where(X[:, 0] < -0.5, "chop", "normal"))
    fit, predict = fit_regime("logit")
    p = walk_forward(X, y, DATES_300, fit, predict)[250:]
    assert regime_metrics(p, list(y[250:]))["accuracy"] > 0.9
```

  `DATES_300` = the first 300 weekdays from 2025-01-01, defined in
  `tests/models/conftest.py`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement both modules.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(models): walk-forward loop and regime detector with baselines`.

---

### Task 5: Conformal range forecaster

**Files:**
- Create: `src/apollo/models/range.py`
- Test: `tests/models/test_range.py`

**Interfaces:**
- Consumes: `walk_forward`, `FEATURES`, the regime probabilities from Task 4.
- Produces:
  - `conformal_upper(residuals: np.ndarray, alpha: float) -> float`: the
    split-conformal quantile, i.e. the `ceil((n+1)(1−alpha))`-th smallest
    residual (∞ when that rank is > n).
  - `range_forecasts(X: np.ndarray, up: np.ndarray, down: np.ndarray, dates,
    alpha: float = 0.05, calib: int = 120, min_calib: int = 30) ->
    pl.DataFrame`, with columns `up_pred`, `down_pred`, `up_bound`,
    `down_bound` (null until ≥ `min_calib` residuals exist).
    - Base model per side: `HistGradientBoostingRegressor(loss="quantile",
      quantile=0.5, max_depth=3, max_iter=200)` via `walk_forward`.
    - The bound = pred + `conformal_upper` of the last `calib` signed
      residuals (y − pred) **from earlier sessions only**.
  - `coverage(sessions_with_bounds: pl.DataFrame) -> dict`: `both`, `up`,
    `down` (hit rates), `mean_width`, `n`, plus `by_regime` (dict label →
    `both`).

- [ ] **Step 1: Write the failing tests**

```python
def test_conformal_rank():
    assert conformal_upper(np.arange(1, 20, dtype=float), 0.05) == 19.0      # ceil(20*0.95)=19
    assert conformal_upper(np.arange(1, 10, dtype=float), 0.05) == np.inf    # rank 10 > 9

def test_matches_mapie_split_conformal():
    # Two-sided absolute residuals: our quantile equals MAPIE's half-width.
    from mapie.regression import SplitConformalRegressor
    from sklearn.linear_model import LinearRegression
    rng = np.random.default_rng(1); X = rng.normal(size=(400, 1)); y = 2 * X[:, 0] + rng.normal(size=400)
    model = LinearRegression().fit(X[:200], y[:200])
    m = SplitConformalRegressor(model, confidence_level=0.9, prefit=True)
    m.conformalize(X[200:], y[200:])
    _, iv = m.predict_interval(X[:1])
    ours = conformal_upper(np.abs(y[200:] - model.predict(X[200:])), 0.10)
    assert (iv[0, 1, 0] - model.predict(X[:1])[0]) == pytest.approx(ours)

def test_coverage_near_nominal_on_iid_data():
    rng = np.random.default_rng(5); X = rng.normal(size=(1000, 2)); scale = 1 + np.abs(X[:, 0])
    up, down = rng.exponential(scale), rng.exponential(scale)
    f = range_forecasts(X, up, down, DATES_1000)
    cov = coverage(_with_actuals(f, up, down))       # helper in the test: adds open=0, high=up, low=-down
    assert 0.86 <= cov["both"] <= 0.94

def test_no_bound_before_min_calib():
    f = range_forecasts(X300, UP300, DOWN300, DATES_300)
    first = f["up_bound"].is_not_null().arg_max()
    assert first == 250 + 30
```

  If MAPIE's 1.x signature differs from the call above, adapt the test to
  the installed version's documented split-conformal API. Keep the
  assertion: our quantile equals MAPIE's half-width.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(models): conformal range forecaster with coverage`.

---

### Task 6: Forecast ledger, report CLI and the nightly Action

**Files:**
- Create: `src/apollo/models/ledger.py`, `src/apollo/models/report.py`
- Modify: `.github/workflows/collect.yml`
- Test: `tests/models/test_ledger.py`, `tests/models/test_report.py`

**Interfaces:**
- Produces:
  - `build_report(root: Path, code: str) -> dict`, which runs the whole
    pipeline and returns:
    - `regime`: metrics for logit, gbm, majority, yesterday;
    - `range`: coverage;
    - `dropped`: counts by reason;
    - `sessions`: the out-of-sample per-session rows;
    - `latest`: the forecast for the next session.
  - `main(argv)` writes `reports/models_<code>.json` (git-ignored) and prints
    a short table.
  - `write_forecast(root: Path, code: str, forecast: dict, now: datetime) ->
    Path | None`: writes `root/ledger/<code>/<date>.json` (the
    regime probabilities, chosen model, open-relative bounds and
    `written_at`). It writes nothing, returning None, when `now` ≥ that
    session's 09:00 ET.
  - `score_ledger(root: Path, code: str, sessions: pl.DataFrame) -> dict`:
    for each ledger file whose session has finished, adds `actual_label`,
    `hit_both`, `scored_at` (it leaves already-scored files alone) and
    returns the running totals.
- **The chosen regime model** is the one with the lower walk-forward log-loss
  (logit or gbm), recorded in the report and in each ledger entry.

- [ ] **Step 1: Write the failing tests**

```python
def test_no_forecast_after_session_start(tmp_path):
    late = datetime(2026, 11, 10, 9, 1, tzinfo=NY)
    assert write_forecast(tmp_path, "MNQ", FORECAST_FOR_NOV_10, late) is None

def test_rewrite_same_day_is_identical(tmp_path):
    early = datetime(2026, 11, 9, 18, 0, tzinfo=NY)
    a = write_forecast(tmp_path, "MNQ", FORECAST_FOR_NOV_10, early).read_text()
    b = write_forecast(tmp_path, "MNQ", FORECAST_FOR_NOV_10, early).read_text()
    assert a == b

def test_score_marks_hits(tmp_path):
    # ledger: 2026-11-03 and 2026-11-04, both open 100 with bounds up 5 / down 5
    # sessions: Nov 3 high 104 low 97 (inside), Nov 4 high 106 low 99 (outside)
    totals = score_ledger(tmp_path, "MNQ", SESSIONS_NOV_3_4)
    assert totals == {"n": 2, "hit_both": 1}
    assert json.loads((tmp_path / "ledger/MNQ/2026-11-03.json").read_text())["hit_both"] is True

@pytest.mark.skipif(not Path("data_store/bars/MNQ/1h").exists(), reason="no local data")
def test_report_on_real_data_has_baselines():
    r = build_report(Path("data_store"), "MNQ")
    assert set(r["regime"]) == {"logit", "gbm", "majority", "yesterday"} and r["range"]["n"] > 100
```

  `FORECAST_FOR_NOV_10` = `{"date": "2026-11-10", "model": "logit", "proba":
  {"trend_up": 0.4, "trend_down": 0.1, "chop": 0.2, "normal": 0.3},
  "up_bound": 120.0, "down_bound": 110.0}`, with `NY = ZoneInfo("America/New_York")`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement. In `collect.yml`, after the collect step, run
  `python -m apollo.models.report --root data_store --symbol MNQ
  --write-ledger --score-ledger` for MNQ, MES, M2K and MYM. The ledger files
  sit in `data_store/ledger/` and are committed with the bars. Add
  `reports/` to `.gitignore`.
- [ ] **Step 4:** Run `.venv/bin/pytest -q`, `ruff`, `pyright`. Expected: all clean.
- [ ] **Step 5: Real run.** Run `.venv/bin/python -m apollo.models.report --symbol MNQ`. Expected: a table with regime accuracy and log-loss for the 4 models, range coverage `both` and mean width, and the dropped counts. **Report the numbers as they are**, including when a model doesn't beat its baselines.
- [ ] **Step 6: Commit** `feat(models): forecast ledger, report CLI and nightly scoring`.

---

## Self-review notes

- **Spec coverage:**
  - 5.4 label, target, pre-open forecast, training history, features,
    logistic regression vs gradient boosting, baselines, metrics: Tasks 1–4.
  - 5.5 asymmetric excursion targets, 95% one-sided bounds, coverage of
    both sides, by-regime coverage: Task 5.
  - 5.13 forecast ledger: Task 6.
  - 5.3 roll exclusion for features: Task 2.
- **Deferred, as the spec allows:**
  - the next-hour zone (chart tooltip only) and the intraday re-forecast:
    Plan 6 / later;
  - 15m features: after about a year of collection;
  - EnbPI: v1 uses rolling split conformal, which spec 8 leaves to the
    builder. MAPIE serves as the reference check.
- **Data note:** about 500 labelled sessions, so 250 go to the first training
  fold and about 250 are scored out-of-sample. Results will carry wide
  uncertainty; the report states `n` next to every number.
