# Apollo Predictor: design

Date: 2026-11-08
Owner: Vaughn Antonio
Status: draft, awaiting Vaughn's approval

## 1. Intent

A free, TradingView-style web app that turns two forecasting models into a
top-down trading signal, with a built-in trade journal.

1. **Regime detector.** Predicts what kind of session is coming (trend up,
   trend down, chop, normal) using signal-processing methods from industrial
   predictive maintenance (spectral kurtosis, envelope analysis, crest factor,
   RMS trend) applied to price returns.
2. **Range forecaster.** Predicts a calibrated 90% range for the session and
   the next hour using conformal prediction (MAPIE), and reports how often
   past ranges actually held.
3. **Strategy layer.** A mechanical version of the TTrades Fractal Model that
   Vaughn already trades: daily bias → 4H → 1H → 15m → 5m entry.
   - The regime and range forecasts filter setups and cap targets.
   - Size = 1–2% of account risk per trade.

### Why

- **Portfolio project** for summer 2027 applications (Industry 4.0, data,
  quant/fintech roles). The pitch: "I applied predictive-maintenance
  techniques to Nasdaq futures, and I can show how well the forecasts are
  calibrated." Generic GitHub stock predictors forecast a single price and
  never show their misses; this one does the opposite.
- **Personal tool.** Vaughn trades MNQ intraday and wants to use it during the
  New York session.
- **Follow-up to his case study**
  ([mnq-trading-case-study](https://github.com/VaughnAntonio/mnq-trading-case-study),
  R + Quarto). That study found:
  - no proven edge;
  - position size is the main risk (worst funded day = 2.8x the drawdown
    limit);
  - trend days were his weakest;
  - passive holding matched his results.

  Its regime tags were labels applied after the day closed. This project asks
  the next question: *could I have known before or during the day, and sized
  accordingly?*

## 2. Goals, non-goals, anti-goals

**Goals**
- An interactive chart that works like TradingView: candles, timeframe
  switching, crosshair, zoom.
- Futures and US stocks via a ticker picker.
- A regime forecast and a range forecast, each with probabilities or
  coverage and an honest accuracy record.
- A top-down checklist and signal: direction, entry, stop, size, and share of
  the prop-firm limit at risk.
- A journal: add, edit and view trades. Each entry automatically saves what
  the model said at entry time. The 51 case-study trades are imported.
- A walk-forward backtest including fees and slippage, compared against buy &
  hold, an MA 20/50 rule, and the journal.
- Free to run and free to host.
- Light, dark and auto themes. Minimal look taken from Portfoliov2.

**Non-goals (v1)**
- Real-time tick data, order execution, broker connections.
- Crypto, forex, options, and stocks outside the US.
- Multi-user accounts or login.
- Mobile-first design. It must work on a phone, but desktop is the target.

**Anti-goals** (failure even if it technically works)
- Claiming an edge the data doesn't support, or hiding misses.
- Any lookahead bias. Every feature uses only data available at decision
  time.
- Looking like a generic AI dashboard: neon colours, gradients, card grids,
  emojis.
- Leaking Vaughn's private journal (real dollar amounts, account numbers,
  notes) to the public site.
- Paid services or API keys required to run it.

## 3. Constraints

- **Cost: zero.** Data from Yahoo Finance via `yfinance`. Hosting on GitHub
  Pages. Scheduled jobs on GitHub Actions free tier.
- **Free data limits.** Yahoo keeps:

  | Bars | History |
  |---|---|
  | 1m | 7 days |
  | 5m and 15m | 60 days |
  | 1h | ~730 days |
  | Daily | MNQ since 2019 |

  Futures prices are delayed about 10 minutes. 4H bars are built from 1H.
  Continuous `=F` series jump at each quarterly roll; the case study already
  notes this, and the data layer must flag roll dates.
- **Licences.** Only MIT, BSD or Apache dependencies. No GPL or AGPL code is
  copied (TradeNote and backtesting.py were rejected for this reason).
- **Tooling.** Vaughn uses PyCharm Community (free) on macOS. Plain `venv` +
  `pyproject.toml`; no Pro-only features.
- **Honesty line** on every page: "Research tool. Not financial advice."

## 4. Approaches considered

| | Approach | Trade-off | Verdict |
|---|---|---|---|
| A | Local app (FastAPI + DuckDB backend, React frontend), plus a nightly static snapshot published for recruiters | Usable live during the session and shareable, but the frontend runs in two modes | **Chosen by Vaughn** |
| B | All-Python dashboard (Streamlit/Dash) | Fastest to build, but can't match the TradingView look or the Portfoliov2 menu and popups | Rejected |
| C | Static only (Python writes JSON, site reads it) | Cheapest, but not live, and the journal has nowhere reliable to save | Rejected |

## 5. Decided design

### 5.1 Stack (dependencies picked by Vaughn)

| Layer | Choice |
|---|---|
| Data | `yfinance` |
| Storage | `DuckDB` (local file), Parquet for collected bars |
| Dataframes | `Polars` (pandas only where a library requires it) |
| API | `FastAPI` (+ `uvicorn`) |
| Range model | `MAPIE` (brings `scikit-learn`) |
| Reports | `quantstats` |
| Chart | `lightweight-charts` (TradingView, Apache-2.0), used directly; no React wrapper |
| Frontend | Vite + React + TypeScript + Tailwind v4 + shadcn/ui (customised), same as Portfoliov2 |
| Signal processing | `numpy` + `scipy` (needed for spectral kurtosis and the Hilbert envelope; no maintained library exists) |
| Tests | `pytest` (Python), `node --test` or Vitest (frontend) |

Rejected by Vaughn: ruptures, PyWavelets, hmmlearn, vectorbt, `ta`, the
lightweight-charts React wrapper, the LuxAlgo and TradeNote journals. The
**backtester is written in-house** (small and tested).

### 5.2 Look

Reference mockup:
`.superpowers/brainstorm/90195-1794176385/content/layout-a-v5-menu.html`.

- **Layout A:**
  - a top bar: menu button, the APOLLO wordmark (uppercase with a small raised ©, like
    the Portfoliov2 name logo), ticker picker, timeframe tabs
    D · 4H · 1H · 15m · 5m · 1m, Trades toggle, "Delayed 10m";
  - one large chart;
  - a 260px right rail split by hairlines (no cards) into **Top-down
    checklist**, **Signal** and **Model check**;
  - a footer with the disclaimer and data source.
- **Tokens from Portfoliov2 `src/index.css`.**
  - Light: background `#e8eaec`, ink `#262933`, muted text `#565a64`, hairline
    `#c4c7cd`, soft fill `#dfe1e4`, panel `#f4f4f4`, brand `#3d5a4a`, down
    `#a32d2d`, radius 4px.
  - Dark (derived): background `#17191e`, ink `#e3e5e8`, muted text `#8b9099`,
    hairline `#2e323a`, soft fill `#22252c`, panel `#1d2026`, brand `#7fa68f`,
    down `#d26a66`.
  - Up candles = brand, down candles = down. Theme is Light / Dark / Auto,
    stored in `localStorage`.
- **Type:** Geist for text, Geist Mono for every number. Portfolio's
  Newsreader serif is **not** used (taste rule: no serif in dashboards).
- **Menu:** Portfoliov2's `MobileNav.tsx` behaviour at every screen width.
  - A hamburger whose outer bars shrink on hover opens a full-screen panel
    that wipes down from the top (clip-path).
  - Numbered tiles 01 Chart, 02 Journal, 03 Backtest, 04 Models, 05 Case study
    rise in, staggered; hovering one dims the others.
  - Below the tiles: a theme tile and a brand-coloured "New journal entry"
    tile. "Close" uses the ⊣ mark. Closing plays the animation in reverse.
  - Built on Radix Dialog with Portfoliov2's keyframes; respects
    `prefers-reduced-motion`.
- **Ticker picker:** a searchable popover grouped into Futures (MNQ, MES,
  M2K, MYM, NQ, ES, MGC, MCL) and US stocks (NVDA, AAPL, MSFT, TSLA, AMZN,
  META). Any valid US stock symbol can be typed in. The last choice is
  remembered.
- **Journal sheet:** a full-screen sheet with the same wipe animation.
  - Left: the trade list (date, symbol, strategy, account, R, coloured by
    sign). Right: the trade detail.
  - The detail shows a header row, a 4-column hairline grid of fields, the
    screenshot, and notes.
  - Clicking a trade dot on the chart opens that trade.
- **Taste rules applied** (design-taste-frontend-v1, tuned down for
  minimalism): no emojis, no shadows or gradients, one accent colour, grid
  rather than flex maths, `min-h-[100dvh]`, skeleton loaders, and empty and
  error states for every panel.

### 5.3 Data pipeline

- **Collector** (`collector/collect.py`), run by a GitHub Action every weekday
  after the 17:00 New York close:
  - fetches 1m, 5m, 15m, 1h and 1d bars for every symbol in
    `config/symbols.toml`;
  - removes duplicates and appends to monthly Parquet files at
    `bars/<symbol>/<interval>/<YYYY-MM>.parquet`;
  - commits them to a separate `data` branch, so `main` stays small.
- This builds up the 1m/5m history Yahoo won't keep. From day one the system
  has about 2 years of 1H bars and daily bars back to 2019. The 5m/1m entry
  layer starts with 60 or 7 days and grows.
- **Locally:** `make sync` (or a script) pulls the `data` branch. DuckDB
  queries the Parquet files directly. While the app is running, the API also
  fetches the latest bars from Yahoo every 60 s and caches them in DuckDB.
- **4H bars** are resampled from 1H, aligned to the CME session (18:00 New
  York open).
- **Sessions:** "session" means the New York cash session (09:30–16:00 ET) for
  the strategy, and the full Globex day for daily bars, matching the case
  study's definitions.
- **Roll handling:** the collector records the quarterly roll dates for `=F`
  symbols. Returns that cross a roll are excluded from features and from
  backtest P&L.

### 5.4 Regime detector

- **Label** (copied from the case study, `R/05_market_regimes.R`): body ratio
  = |close − open| / (high − low).
  - Trend: body ratio > 0.6. Direction from close vs open.
  - Chop: body ratio < 0.3.
  - Normal: everything else.
  - Daily labels use the full Globex day; session labels use the New York
    session.
- **Target:** the **New York session** label (that's where the trades
  happen).
  - The forecast is made **before the open**, using data up to 09:00 ET.
  - v1 has no intraday re-forecast. If one is added later, it gets its own
    cut-off and is scored separately. *(Builder's call.)*
- **Training history** *(builder's call)*:
  - daily-bar features back to 2019 (~1,900 sessions);
  - 1H features over the ~2 years Yahoo keeps;
  - 15m features are left out until the collector has gathered at least 250
    sessions of them.
- **Features** ("machine health indicators" on 1H and 15m log returns, in
  rolling windows):
  - spectral kurtosis per frequency band (STFT via `scipy.signal`);
  - envelope (Hilbert) mean and kurtosis;
  - crest factor;
  - RMS and its slope;
  - plain kurtosis and skew;
  - realised range;
  - overnight gap;
  - close vs 50-day MA (the case study's bull/bear context).
- **Model:** multinomial logistic regression first, gradient boosting second.
  Keep whichever does better on walk-forward log-loss. Output: class
  probabilities.
- **Baselines it must beat**, shown in the Models page:
  - always predict the most common class;
  - predict yesterday's label.
- **Reported:** accuracy, log-loss and a confusion matrix, on walk-forward
  out-of-sample data only.

### 5.5 Range forecaster

- **Targets:**
  - session range: high − low of the New York session, in points;
  - next-hour range on 1H bars.
- **Base model:** a gradient-boosting or quantile regressor on realised
  volatility features, plus the regime probabilities.
- **Interval:** MAPIE conformal prediction for time series (EnbPI, or split
  conformal recalibrated on a rolling window; builder picks after testing)
  at 90% coverage.
- **The zone is asymmetric** *(builder's call, so the number shown matches
  the lines drawn)*:
  - Two targets: **up-excursion** = session high − open, and
    **down-excursion** = open − session low.
  - Each gets its own one-sided 95% conformal upper bound.
  - Zone = [open − down bound, open + up bound]. By Bonferroni, the high and
    low both stay inside the zone in at least ~90% of sessions.
- **The checklist uses the session zone.** The next-hour zone only appears in
  the chart tooltip.
- **Reported coverage** = the share of sessions where the high and the low
  *both* stayed inside the drawn zone. This is exactly what the user sees,
  never just width coverage. Also reported: average zone width, and coverage
  split by regime. The rail's "Model check" shows the last 60 sessions.

### 5.6 Strategy layer: TTrades Fractal Model + forecast filters

Vaughn trades a version of the **TTrades Fractal Model** (YouTube: TTrades).
The strategy layer codifies it mechanically. The regime and range models act
as **filters and target setters on top of it**. The headline research
question becomes: **does adding the forecasts improve the Fractal Model's
out-of-sample expectancy over the plain model?**

This is an independent interpretation of public TTrades material. The
official indicator is closed-source. The README must credit TTrades and say
this. Every rule below is a default in `config/strategy.toml` and **must be
reviewed by Vaughn before the backtest is trusted** (see section 9).

**Terms, per higher-timeframe (HTF) candle:**
- **C1:** the previous HTF candle.
- **C2 (reversal closure):**
  - Bullish: trades below C1's low by at least 1 tick (the sweep), then
    closes back above C1's low.
  - Bearish: the mirror image.
  - **Valid only if the sweep touches an HTF point of interest** on the same
    timeframe:
    - a swing low/high, defined as a 3-bar fractal;
    - or an unfilled fair value gap, defined as a 3-candle gap.
- **C3:** the next candle, expected to continue in C2's direction.
  - "C3 closure" = it closes beyond C2's high (bullish) or low (bearish).
- **EQ:** the midpoint of C2's sweep wick. If price trades back through EQ
  against the bias before entry, the setup is invalid.
- **CISD (change in state of delivery), on the lower timeframe (LTF) after
  the sweep:**
  - Bullish: an LTF candle closes above the open of the first candle in the
    most recent run of consecutive down-close candles that made the low. That
    low becomes the **protected low**.
  - Bearish: the mirror image.
  - *(Common definition used in this trading style; Vaughn to confirm.)*

**Timeframe pairings (HTF → LTF):** Daily → 1H, 4H → 15m, 1H → 5m (15m → 1m
optional).

**The rail's top-down checklist, mapped to Vaughn's process:**

| Step | Rule |
|---|---|
| Daily bias | The last daily candle is a valid C2 or C3 closure in a direction, **and** the regime model doesn't contradict it: P(chop) < 0.5 and P(trend against the direction) < P(trend with it). Otherwise flat. |
| 4H | A 4H C2 is forming or closed in the bias direction at a 4H POI. |
| 1H | 1H CISD in the bias direction (Daily → 1H pairing). The forecast zone still leaves room to the target (target inside the zone, or at most 10% beyond it). |
| 15m | 15m CISD in the bias direction (4H → 15m pairing). |
| 5m trigger | 5m CISD (1H → 5m pairing), inside the New York window 09:30–12:00 ET. This is the entry signal. |

**Entry, stop and target:**
- **Entry:** the close of the CISD candle. A "positional" variant enters at
  the next HTF open instead; both are backtested.
- **Stop:** 1 tick beyond the protected low/high.
- **Target:** the opposite extreme of C1 (range expansion), capped at the
  forecast zone edge.
  - Skip the trade if reward:risk < 1.5.
  - Flat by 16:00 ET.
- **Limits:** one position per symbol, at most 2 trades per session.

**Sizing (Vaughn's rule):**
- Risk per trade = **1% of account size** by default (setting goes up to 2%),
  e.g. 50k account → $500 at 1%.
- `contracts = floor(risk_$ / (stop_distance_pts × point_value))`. If that is
  0, skip the trade.
- Point values come from `config/symbols.toml`: MNQ $2, MES $5, M2K $5,
  MYM $0.5, NQ $20, ES $50, MGC $10, MCL $100. Stocks: shares at $1/point.
- **Accounts** are set in `config/accounts.toml`: name, size, max drawdown,
  risk %. Presets: APEX 50k (size 50,000, drawdown 2,500); TOPSTEP 50k (size
  50,000, drawdown 2,000).
- The rail shows **"Risk of drawdown limit"** = planned loss ÷ the account's
  max drawdown. It's a warning only (e.g. 1% of 50k = 20% of a 2,500 limit).
  The backtest simulates its own account balance with the same rules.

**Optional (v2):** SMT/PSP confirmation using MNQ vs MES divergence; the
collector already stores both.

### 5.7 Backtester (in-house)

- **Event loop over bars:** decisions use only closed bars. Order: fill at
  the next bar's open, then apply stop and target.
- **If a stop and a target are both hit in the same bar,** assume the stop
  (the conservative choice).
- **Costs** (configurable): commission $0.62/side per micro and $2.25/side
  per E-mini; slippage 1 tick per side; stocks $0 commission + $0.01/share
  slippage.
- **Walk-forward:**
  - expanding training window;
  - models refit monthly;
  - every reported number is out-of-sample.
- **Two test layers:**
  - **Daily → 1H Fractal Model** over the full ~2 years: entry on the 1H
    CISD. This is the headline result.
  - **Full top-down model** with the 5m CISD trigger, over whatever 5m history
    exists, labelled with its sample size.
- **Output:** trade list, equity curve, R-multiples, and a quantstats HTML
  tearsheet. Each layer runs **with and without the forecast filters**.
  Compared against:
  - buy & hold, 1 contract;
  - MA 20/50, 1 contract (rule copied from `R/06_benchmark_ma.R`);
  - the journal's live stages.
- **Bootstrap 95% confidence intervals** on expectancy, as in the case study.

### 5.8 Journal

- **Storage:** a `journal` table in the local DuckDB. Screenshots go to
  `journal_media/`. Both are git-ignored.
- **Fields:**
  - id, opened_at, closed_at, symbol, side, entry, stop, target, exit, size,
    fees;
  - account (with presets), stage (backtest / forward / eval / funded);
  - strategy, setup grade (A/B/C/E), tags (free-form, e.g. "Gamba"), notes
    (Markdown), screenshot path;
  - **model_snapshot**: JSON of the regime probabilities, zone, checklist
    state and signal at `opened_at`, recorded automatically when the entry is
    saved.
- **Derived:** R-multiple, P&L in $, win.
- **Import:** a one-off importer loads the case-study files
  `data/public/trades_public.csv` and `days_public.csv` (scaled dollars, kept
  scaled and labelled). Missing fields stay empty and display as "Not
  recorded".
- **On the chart:** with Trades on, each journal day is a dot (brand colour if
  the day's R is ≥ 0, down colour if negative). Intraday views show markers at
  the actual entry and exit times.
- **"Take trade" (following the signal):** when the 5m trigger fires, the
  Signal panel shows a **Take trade** button.
  - Clicking it creates a journal entry prefilled with symbol, side, entry,
    stop, target, size, account and the model snapshot, with
    `source = signal`. The user can adjust the fill price and size before
    saving.
  - The chart then draws the open trade TradingView-style: an entry marker,
    an entry line, a dashed stop line (down colour) and a dashed target line
    (brand colour), plus live open R in the rail.
  - **Close trade** records the exit (price/time, or auto-filled when the
    stop or target is hit on later bars, which the user confirms).
  - Manual trades (`source = manual`) are drawn the same way.
  - The Journal stats split **followed-signal vs manual vs signal-skipped**
    trades. This is a discipline metric: did taking the model's signals beat
    your own calls? It answers the case study's "Gamba days" finding.

### 5.9 API (FastAPI, local)

| Endpoint | Method | Returns |
|---|---|---|
| `/bars?symbol=&tf=&from=&to=` | GET | OHLCV |
| `/forecast?symbol=&at=` | GET | Regime probabilities, zone, coverage stats |
| `/signal?symbol=&at=` | GET | Checklist state, entry, stop, target, size, risk of limit |
| `/journal` | GET / POST | List / create entries |
| `/journal/{id}` | GET / PATCH / DELETE | One entry |
| `/backtest/summary?symbol=` | GET | Latest walk-forward result + tearsheet link |
| `/symbols` | GET | The configured symbol list |

The frontend polls `/bars` and `/signal` every 60 s while a session is open.

### 5.10 Public snapshot

- **Built by a nightly GitHub Action:** after the collector runs, it
  1. refits or refreshes the forecasts;
  2. runs the backtest;
  3. exports `snapshot/*.json` (recent bars per symbol and timeframe,
     forecasts, signals, backtest summary, anonymised case-study journal);
  4. builds the frontend in `VITE_MODE=static`;
  5. deploys to GitHub Pages.
- **Static mode:** reads JSON instead of the API, makes the journal
  read-only, hides "New journal entry", and shows a "Snapshot of <date>"
  label.
- **Privacy:** the private DuckDB journal never leaves the laptop. Only the
  case study's already-anonymised data is published.

### 5.11 Pages

1. **Chart:** the main screen described above.
2. **Journal:** the sheet, plus a stats strip (win rate, expectancy in R,
   count by tag and grade) and a P&L-by-day calendar.
3. **Backtest:** equity curves vs the benchmarks, R distribution, a monthly
   table, and a link to the quantstats tearsheet.
4. **Models:** regime accuracy and confusion matrix vs the baselines, range
   coverage over time and by regime, and a feature-importance view. The
   "predictive maintenance" story is told here with one diagram (machine
   signal → health indicators → failure warning; returns → features → regime
   warning).
5. **Case study:** a short summary of the R report's findings, a link to the
   report, and how this project answers its open questions.
6. **Guide (how it works):** explains the whole app on real MNQ data, for
   Vaughn and for recruiters. Two parts:
   - **Guided tour:** opened from the menu and offered on first visit (can be
     skipped, never shown again once dismissed). Step-by-step spotlights over
     the live Chart screen, each with one short paragraph:
     ticker picker → timeframe tabs → regime forecast → range zone →
     Fractal Model checklist rows → signal and sizing → Take trade → journal
     → Model check.
   - **Explainers:** three short interactive sections, each using one past MNQ
     day as a worked example with a step slider:
     - **Fractal Model:** C1 → C2 sweep at a POI → C3, then the LTF CISD and
       the protected low, entry, stop and target drawn as the slider moves.
     - **Regime detector:** the predictive-maintenance analogy diagram, then
       that day's health indicators, the probabilities, and what actually
       happened.
     - **Range forecaster:** the excursion targets, the conformal bound, and
       coverage over the last 60 sessions, including the misses.
   - The tour is a small in-house component (spotlight + popover); no new
     dependency.

Backtest, Models and Guide charts follow the `dataviz` skill.

### 5.12 Model scope per ticker

- **v1:** full models, signal and backtest for the four equity-index micros:
  MNQ (primary), MES, M2K, MYM.
- **Other tickers** (NQ, ES, MGC, MCL, stocks) get the chart, journal and
  range forecaster. The checklist rail shows "Model not trained for this
  symbol" until it's enabled in config.
- *(Builder's call, flagged for Vaughn.)*

### 5.13 Research rigour (what makes it credible)

Added after comparing with similar public projects (2026-11-08). None of
these was found in comparable repos.

- **Forecast ledger.**
  - Every pre-open forecast (regime probabilities, zone, checklist,
    signal) is written to `ledger/<symbol>/<date>.json` by the nightly Action
    **before** the session it predicts, and committed.
  - The next run scores it.
  - Git timestamps make it a forward record that can't be backfilled. The
    Models page shows "live since <date>" next to the backtest numbers.
- **Locked holdout.**
  - The last 6 months of 1H data before the first full backtest run are
    reserved and touched once, at the end.
  - Every backtest run (config hash, date, metrics) is appended to
    `runs/log.csv`, so the number of variants tried is public.
- **Prop-firm Monte Carlo.** Resample the backtest's trade R-multiples
  (bootstrap, 10,000 paths) to estimate:
  - the probability of passing an evaluation (profit target before drawdown
    breach);
  - the probability of breaching a funded account within N trades.

  Results are shown per account preset and per risk % (1% vs 2%). This
  directly answers the case study's sizing finding.
- **Ablation.** Every result table includes:
  - plain Fractal Model;
  - plus the regime filter;
  - plus the range filter;
  - plus both.

  This shows what each model actually contributes.
- **Data quality report.** Each collector run checks for missing bars, bad
  ticks (moves larger than 8× ATR), DST shifts, holidays and roll days. It
  writes `quality/<date>.json`. Bad days are excluded and shown.
- **Model card.** A `docs/model-card.md` for each model covering data,
  target, features, validation method, metrics, known failure modes and
  limitations.

## 6. Repository layout (proposed)

```
apollo-predictor/
  pyproject.toml
  config/            symbols.toml, strategy.toml, accounts.toml
  src/apollo/
    data/            yahoo.py, collect.py, sessions.py, resample.py, rolls.py
    features/        health.py (spectral kurtosis, envelope, crest, RMS), basic.py
    models/          regime.py, range.py
    strategy/        checklist.py, sizing.py
    backtest/        engine.py, costs.py, report.py
    journal/         store.py, importer.py, snapshot.py
    api/             main.py
    export/          snapshot.py
  tests/             mirrors src/apollo
  web/               Vite + React app
  .github/workflows/ collect.yml, publish.yml
  docs/superpowers/  specs/, plans/
```

## 7. Ways of working

- Skills: superpowers (plans, test-driven development, verification),
  ponytail (smallest change that works) and karpathy-guidelines while coding;
  design-taste-frontend-v1 and dataviz for the UI.
- **Test first** for every rule that touches money or time:
  - session boundaries;
  - resampling;
  - roll exclusion;
  - no-lookahead checks;
  - sizing;
  - the same-bar stop-and-target rule;
  - cost maths;
  - conformal coverage on synthetic data.
- **Lookahead guard test:** shift the future of the input series and check
  that the features at time *t* do not change.
- Mark shortcuts with `shortcut:` comments.
- **CI:** a GitHub Action on every push runs
  - `ruff` (lint and format);
  - `pyright` (types);
  - `pytest`;
  - the frontend type-check, tests and build.
- **README:** a demo GIF, an architecture diagram, how to run it in PyCharm
  (Windows/Linux and macOS shortcuts), a limitations section, a TTrades
  credit, and a link to the live snapshot.
- **Frontend smoke test:** one Playwright test that opens the Chart, switches
  ticker and timeframe, opens the menu and the journal, and takes a trade
  against a fixture API. *(Dev dependency; Vaughn to approve during the
  plan.)*

## 8. Left to the builder

- EnbPI vs rolling split-conformal, and the base regressor, chosen by
  walk-forward results.
- Exact feature window lengths and STFT band edges, within reason, tuned only
  on training folds.
- Component split, state management and the API response shapes beyond the
  endpoint list above.
- Whether `make` or a small Python CLI wraps sync / run / test.
- Visual details not covered by the mockup and tokens, following the same
  rules.

## 9. Open for Vaughn

- **Before the backtest is trusted,** review the Fractal Model codification
  in section 5.6, especially:
  - the CISD definition;
  - the POI types;
  - the New York entry window;
  - the 1.5 R:R minimum;
  - the target rule.

  The plan's first strategy task produces a chart page that marks every
  detected C2 and CISD on real MNQ data, so Vaughn can check the detection
  against how he reads the chart before any results are computed.
