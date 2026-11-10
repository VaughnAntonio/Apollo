# Apollo Predictor, Plan 6 of 7: Web App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the local web app that Vaughn trades from. It has:
- the Layout A chart screen, with the top-down checklist, the signal and the model check in the rail;
- the APOLLO menu, which behaves like Portfoliov2's `MobileNav` at every width;
- Light, Dark and Auto themes;
- the ticker picker;
- Take trade, with the open trade drawn on the chart;
- the journal sheet, with stats and a P&L calendar.

All of it reads from the Plan 5 API.

**Architecture:**
- **`web/`** is a Vite + React + TypeScript app.
  - `src/api/` is a typed client for the Plan 5 endpoints, plus one polling hook.
  - `src/lib/` holds pure functions (time formatting, chart data, open R, storage). Vitest tests them in jsdom.
  - `src/components/` holds the UI.
- **The chart** uses `lightweight-charts` directly, with no React wrapper (spec 5.1). One component owns the chart instance. Everything it draws comes from pure functions in `src/lib/chart.ts`, so the drawing rules can be tested without a canvas.
- **Navigation** is a hash route (`#/chart`, `#/backtest`, `#/models`, `#/case-study`). The journal is a sheet over any page. Backtest, Models and Case study are Plan 7, so here they show an empty state.
- **The Python side** gets three small additions:
  - `model_check` on `/forecast`;
  - `POST /journal/auto-close`;
  - `GET /media/{name}`, to show screenshots.

**Tech Stack:** All npm packages are MIT unless marked. Versions are exact, checked on 2026-11-10 against npm and Portfoliov2's `package.json`. *Approval requested with this plan.*

| Package | Version | Why |
|---|---|---|
| `react`, `react-dom` | 19.3.1 | Spec 5.1, same as Portfoliov2 |
| `radix-ui` | 1.8.1 | Dialog (menu, journal sheet) and Popover (ticker picker); the package Portfoliov2's MobileNav already imports |
| `lightweight-charts` | 5.2.1 (Apache-2.0) | The chart, picked by Vaughn |
| `@fontsource-variable/geist`, `@fontsource-variable/geist-mono` | 5.3.x (font licence OFL-1.1) | Geist and Geist Mono served locally, as Portfoliov2 does; no Google Fonts request |
| dev: `vite` 8.3.7, `@vitejs/plugin-react` 6.3.0, `typescript` ~7.0.2, `tailwindcss` + `@tailwindcss/vite` 4.3.5, `@types/react` + `@types/react-dom` 19.3.x | | Same toolchain as Portfoliov2 |
| dev: `vitest` 5.1.0, `@testing-library/react` 16.3.3, `jsdom` 31.0.0 | | Unit and component tests (spec 5.1 allows Vitest) |
| dev: `@playwright/test` 1.65.0 (Apache-2.0) | | The one smoke test in spec 7; it downloads Chromium (about 150 MB) once |

**Not added:**
- the `shadcn` CLI, `class-variance-authority`, `tailwind-merge` and `lucide-react`. We need only Dialog and Popover, which shadcn wraps around Radix anyway, and two inline SVG marks.
- a data-fetching library such as React Query. One 40-line hook covers polling.

**Spec:** `docs/superpowers/specs/2026-11-08-apollo-predictor-design.md`. Plan 6 covers:
- 5.2, the look;
- 5.8, the journal on the chart, Take trade and close;
- 5.9, polling;
- 5.11, page 1 (Chart) and page 2 (Journal);
- section 7, frontend CI and the smoke test.

Plan 5's deferred list (trades on the chart, the Take trade UI, the journal sheet and the menu) is all here.

## Global Constraints

- **Tokens, copied from spec 5.2** and defined once in `web/src/index.css` as CSS variables on `:root`:
  - Light: `--bg #e8eaec`, `--ink #262933`, `--muted #565a64`, `--line #c4c7cd`, `--soft #dfe1e4`, `--panel #f4f4f4`, `--brand #3d5a4a`, `--brand-fg #f4f4f4`, `--down #a32d2d`, radius 4px.
  - Dark: `--bg #17191e`, `--ink #e3e5e8`, `--muted #8b9099`, `--line #2e323a`, `--soft #22252c`, `--panel #1d2026`, `--brand #7fa68f`, `--brand-fg #17191e`, `--down #d26a66`.
  - Dark applies under `:root[data-theme=dark]`. It also applies under `@media (prefers-color-scheme: dark) { :root:not([data-theme=light]) }`, which is Auto. Tailwind v4 `@theme` maps these to utilities (`bg-bg`, `text-ink`, `border-line`, …).
- **Type:** Geist for text and Geist Mono for every number (`font-mono tabular-nums`). No serif.
- **Taste rules (spec 5.2):**
  - no emojis, shadows or gradients;
  - one accent colour (`--brand`), with `--down` used only for losses and stops;
  - hairlines, not cards;
  - CSS grid for layout;
  - `min-h-[100dvh]`;
  - a skeleton, an empty state and an error state for every panel.
- **Up candles are brand and down candles are down.** Candle colours are read from the CSS variables, and they change when the theme changes.
- **Every time is shown in ET** (`America/New_York`), whatever the browser's zone. Vaughn is in Madrid. Times typed into forms are sent without a zone, and the API reads them as New York time (Plan 5 fix).
- **Every page footer says:** "Research tool. Not financial advice." It also says "Data: Yahoo Finance". The top bar says "Delayed 10m".
- **The API base** is `import.meta.env.VITE_API ?? "http://127.0.0.1:8000"`. The dev server runs on `http://localhost:5173`, the only origin the API allows.
- **Polling:** `/bars` and `/signal` are polled every 60 s while the tab is visible (spec 5.9). Polling pauses while the tab is hidden and refreshes once when it's shown again.
- **`localStorage` keys:** `apollo.theme` (`light|dark|auto`), `apollo.symbol`, `apollo.tf` and `apollo.trades` (`on|off`). Every read and write sits in try/catch and falls back to `auto`, `MNQ`, `5m` and `on`.
- **Motion:** every animation sits inside `@media (prefers-reduced-motion: no-preference)`.
- **Prose** (UI copy, comments, the web README) follows the humanizer skill. Mark shortcuts with `// shortcut:`.
- **Ask Vaughn** before adding any package not in the table above.

## Review Focus

1. **The API isn't running.** Every panel shows an error state with the line "Start the API: `python -m apollo.api.main`". The chart area isn't blank, and the app recovers on the next poll without a reload. *Test: Task 2 (`usePoll` error then recovery) and Task 9 (smoke test with the API routes failing).*
2. **A symbol or timeframe has no bars**, such as NVDA on 1m or anything not collected yet. The chart shows "No 1m bars for NVDA yet" instead of crashing on an empty series. *Test: Task 3.*
3. **The tab sleeps or polls overlap.** After the laptop wakes, the first poll returns bars that overlap ones already drawn. Merging them must not duplicate or reorder candles, because lightweight-charts throws on out-of-order `update` calls. *Test: Task 3 (`mergeBars`).*
4. **The browser is in Madrid during the DST gap.** Europe changes clocks a week before the US. Between those changes, a chart label for the 09:30 ET bar must still read 09:30. A time typed into the journal form as "10:00" must be saved as 10:00 ET. *Tests: Task 3 (`nyTime` on 2026-03-10 and 2026-10-28) and Task 8 (the form sends a naive ISO string).*
5. **The signal expires between showing and clicking.** The API answers Take trade with 422, for example because there's no trade signal any more or a trade is already open. The rail shows the API's message under the button. Nothing is drawn as if the trade had opened. *Test: Task 5.*

---

## File Structure

```
web/
  package.json, package-lock.json, vite.config.ts, tsconfig.json, index.html
  playwright.config.ts, README.md
  src/
    main.tsx, App.tsx              hash route, providers, layout grid
    index.css                      tokens, @theme, menu/sheet keyframes, fonts
    api/types.ts                   response types for the Plan 5 API
    api/client.ts                  typed fetch wrappers, ApiError
    api/usePoll.ts                 polling hook (visibility-aware)
    lib/storage.ts                 safe localStorage get/set
    lib/theme.ts                   theme apply + useTheme
    lib/time.ts                    nyTime, nyDate, toNaiveIso
    lib/chart.ts                   mergeBars, candleColours, tradeLines, tradeMarkers, dayDots
    lib/trade.ts                   openR, fmtR, fmtPrice
    components/TopBar.tsx          burger, wordmark, ticker, timeframes, Trades toggle
    components/Wordmark.tsx, EndMark.tsx
    components/TickerPicker.tsx
    components/Chart.tsx           the only lightweight-charts owner
    components/Rail.tsx            Checklist, Signal (Take trade / open trade), ModelCheck
    components/Menu.tsx
    components/journal/Sheet.tsx, TradeList.tsx, TradeDetail.tsx, EntryForm.tsx, Stats.tsx
    components/Placeholder.tsx     empty-state page for Plan 7 pages
    components/State.tsx           Skeleton, Empty, ErrorLine
  tests/                           Vitest files mirror src/ (lib/*.test.ts, components/*.test.tsx)
  e2e/smoke.spec.ts                Playwright, API mocked with page.route
src/apollo/api/main.py             + model_check, auto-close, media
tests/api/test_api.py              + tests for the three additions
.github/workflows/ci.yml           + web job
.claude/launch.json                web dev server for the preview pane
```

---

### Task 1: API additions for the web app

**Files:**
- Modify: `src/apollo/api/main.py`
- Test: `tests/api/test_api.py`

**Interfaces:**
- Produces, for the web types in Task 2:
  - `GET /forecast` returns its Plan 5 fields plus `model_check: {n: int, range_hit: float | null, regime_accuracy: float | null}`, computed over the last 60 entries of the report's `sessions`.
  - `POST /journal/auto-close?symbol=MNQ` returns `{closed: list[int]}`.
  - `GET /media/{name}` returns the image bytes.
- Consumes: `apollo.journal.trades.auto_close(store, bars_by_symbol, now)` and `read_bars`.

- [ ] **Step 1: Write the failing tests**

```python
def test_model_check_last_60(tmp_path):
    from apollo.api.main import model_check
    sessions = [{"label": "chop", "proba": {"chop": .6, "normal": .4}, "hit_both": i % 4 != 0}
                for i in range(80)]
    sessions[-1]["proba"] = {"chop": .1, "normal": .9}
    mc = model_check(sessions)
    assert mc["n"] == 60
    assert mc["range_hit"] == pytest.approx(45 / 60)
    assert mc["regime_accuracy"] == pytest.approx(59 / 60)
    assert model_check([]) == {"n": 0, "range_hit": None, "regime_accuracy": None}

def test_auto_close_endpoint(client):
    i = client.post("/journal", json=MANUAL | {"opened_at": "2026-11-03T09:00:00",
                                               "target": 200.0, "stop": 0.5}).json()["id"]
    r = client.post("/journal/auto-close", params={"symbol": "MNQ"})
    assert r.status_code == 200 and r.json() == {"closed": [i]}  # the 15:00 bar flats it
    assert client.get(f"/journal/{i}").json()["needs_confirm"] is True

def test_media_serves_only_uploaded_names(client):
    i = client.post("/journal", json=MANUAL).json()["id"]
    path = client.post(f"/journal/{i}/screenshot",
                       files={"file": ("a.png", b"\x89PNG", "image/png")}).json()["screenshot"]
    got = client.get("/media/" + path.removeprefix("journal_media/"))
    assert got.status_code == 200 and got.headers["content-type"] == "image/png"
    for bad in ["../j.duckdb", "x.png", "1-abc.png", "..%2Fj.duckdb"]:
        assert client.get(f"/media/{bad}").status_code == 404
```

- [ ] **Step 2: Run the tests to check they fail**

Run: `.venv/bin/pytest tests/api/test_api.py -k "model_check or auto_close_endpoint or media" -v`
Expected: FAIL (`model_check` not defined; 404 or 405 on the new routes).

- [ ] **Step 3: Implement the three additions in `main.py`**
  - `model_check(sessions: list[dict]) -> dict` is a module-level function.
    - It takes the last 60 sessions.
    - `range_hit` is the mean of `hit_both`.
    - `regime_accuracy` is the share where the `proba` argmax equals `label`.
    - `_default_forecast` adds `model_check(r["sessions"])`.
  - The auto-close route finds the earliest open trade for `symbol` and returns `{closed: []}` if there isn't one. It reads 5m bars from that trade's `opened_at`. If there are none, it falls back to 1h bars. It calls `auto_close(store, {symbol: bars}, datetime.now(UTC))`.
  - The media route accepts only `name` matching `^\d+-[0-9a-f]{32}\.(png|jpg)$`. Anything else is a 404. It serves `media_dir / name` with `FileResponse`.

- [ ] **Step 4: Run the API tests**

Run: `.venv/bin/pytest tests/api -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/apollo/api/main.py tests/api/test_api.py
git commit -m "feat(api): model check, auto-close and media routes for the web app"
```

---

### Task 2: Scaffold, tokens, themes, API client and polling

**Files:**
- Create: `web/` (Vite React-TS layout), `web/src/index.css`, `web/src/lib/storage.ts`, `web/src/lib/theme.ts`, `web/src/api/types.ts`, `web/src/api/client.ts`, `web/src/api/usePoll.ts`, `web/src/components/State.tsx`, `web/src/App.tsx`
- Create: `.claude/launch.json` (config `web`: `npm --prefix web run dev`, port 5173)
- Modify: `.github/workflows/ci.yml` (add a `web` job), `.gitignore` (`web/node_modules`, `web/dist`, `web/test-results`, `web/playwright-report`)
- Test: `web/tests/lib/storage.test.ts`, `web/tests/lib/theme.test.ts`, `web/tests/api/client.test.ts`, `web/tests/api/usePoll.test.tsx`

**Interfaces:**
- Produces:
  - `get(key: string, fallback: string): string` and `set(key: string, value: string): void`, in `lib/storage.ts`.
  - `type Theme = "light" | "dark" | "auto"`, `applyTheme(t: Theme): void` (sets or removes `data-theme` on `<html>`) and `useTheme(): [Theme, (t: Theme) => void]`.
  - `types.ts`, matching the API's JSON exactly:
    - `Sym {code, name, kind: "future" | "stock", model_enabled}`;
    - `Bar {time, open, high, low, close, volume}` (time in UTC seconds);
    - `CheckRow {step, status: "pass" | "wait" | "fail" | "no_data", detail}`;
    - `Signal {symbol, status: "trigger" | "waiting" | "flat" | "no_model", direction: "bull" | "bear" | null, entry, entry_ts, stop, target, contracts, risk_of_limit, account, variant, as_of, checklist: CheckRow[]}`;
    - `Forecast {latest?, range?, regime_model?, model_check?, status?: "no_model"}`;
    - `Entry`, with the journal columns plus `"risk_$"`, `"pnl_$"`, `r` and `win`;
    - `JournalStats {stats, calendar: {date, n, r, "pnl_$"}[]}`.
  - `client.ts`:
    - `class ApiError extends Error {status: number}`, whose message is the API's `detail`, or `"Start the API: python -m apollo.api.main"` on a network error;
    - `api.symbols()`, `api.bars(symbol, tf, start?)`, `api.signal(symbol)`, `api.forecast(symbol)`;
    - `api.journal.list()`, `api.journal.get(id)`, `api.journal.create(body)`, `api.journal.patch(id, body)`, `api.journal.remove(id)`, `api.journal.close(id, {exit, at?, reason?})`, `api.journal.take(symbol, {fill?, size?})`, `api.journal.autoClose(symbol)`, `api.journal.screenshot(id, file)` and `api.journal.stats()`;
    - `mediaUrl(path)`.
  - `usePoll<T>(fn: () => Promise<T>, deps: unknown[], everyMs = 60_000): {data?: T, error?: ApiError, loading: boolean, refresh(): void}`.
  - `State.tsx`: `<Skeleton rows={n}/>`, `<Empty>{text}</Empty>` and `<ErrorLine error={e}/>`.

- [ ] **Step 1: Scaffold and install**

Run, in `web/`:
- `npm create vite@8.3.7 . -- --template react-ts`, keeping only what this plan lists;
- `npm i -E` with the runtime packages;
- `npm i -DE` with the dev packages from the Tech Stack table.

Add the scripts `dev`, `build` (`tsc -b && vite build`), `typecheck` (`tsc -b --noEmit`), `test` (`vitest run`) and `e2e` (`playwright test`). Vitest uses `environment: "jsdom"`.

- [ ] **Step 2: Write the failing tests**

```ts
// storage.test.ts
it("falls back when localStorage throws", () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked") })
  expect(get("apollo.symbol", "MNQ")).toBe("MNQ")
  expect(() => set("apollo.symbol", "MES")).not.toThrow()
})
// theme.test.ts
it("auto removes data-theme, light/dark set it, and the choice is stored", () => {
  applyTheme("dark"); expect(document.documentElement.dataset.theme).toBe("dark")
  applyTheme("auto"); expect(document.documentElement.dataset.theme).toBeUndefined()
  const { result } = renderHook(() => useTheme()); act(() => result.current[1]("light"))
  expect(localStorage.getItem("apollo.theme")).toBe("light")
})
// client.test.ts
it("turns a 422 into ApiError with the API's detail", async () => {
  fetchMock(422, { detail: "there is no trade signal right now" })
  await expect(api.journal.take("MNQ", {})).rejects.toMatchObject(
    { status: 422, message: "there is no trade signal right now" })
})
it("says how to start the API when it's unreachable", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")))
  await expect(api.symbols()).rejects.toMatchObject(
    { status: 0, message: "Start the API: python -m apollo.api.main" })
})
// usePoll.test.tsx
it("polls, keeps the last data on error, recovers, and pauses while hidden", async () => {
  vi.useFakeTimers()
  const fn = vi.fn().mockResolvedValueOnce(1).mockRejectedValueOnce(new ApiError("down", 0))
    .mockResolvedValue(2)
  const { result } = renderHook(() => usePoll(fn, [], 60_000))
  await vi.waitFor(() => expect(result.current.data).toBe(1))
  await act(() => vi.advanceTimersByTimeAsync(60_000))
  expect(result.current.error?.status).toBe(0); expect(result.current.data).toBe(1)
  hideTab(); await act(() => vi.advanceTimersByTimeAsync(180_000)); expect(fn).toHaveBeenCalledTimes(2)
  showTab(); await vi.waitFor(() => expect(result.current.data).toBe(2))
})
```

- [ ] **Step 3: Run them to check they fail**

Run: `npm --prefix web test`
Expected: FAIL (modules not found).

- [ ] **Step 4: Implement**
  - Write `index.css` with the tokens and `@theme` from Global Constraints, and import the two fontsource packages.
  - `App.tsx` renders `<main class="grid min-h-[100dvh] grid-rows-[auto_1fr_auto] bg-bg text-ink">`, with a placeholder top bar and the footer copy.
  - `usePoll` listens to `visibilitychange`. When the tab is shown again it refreshes once and restarts the interval.
  - The client builds query strings with `URLSearchParams`. It sends JSON with `content-type: application/json`, and sends screenshots as `FormData` field `file`.

- [ ] **Step 5: Run the tests, the type-check and the build**

Run: `npm --prefix web test && npm --prefix web run typecheck && npm --prefix web run build`
Expected: all pass; `web/dist/index.html` exists.

- [ ] **Step 6: Add the CI job**

The `web` job uses `actions/setup-node@v4` with `node-version: 26`, `cache: npm`, `cache-dependency-path: web/package-lock.json`. Then it runs `npm ci`, `typecheck`, `test` and `build`, all with `--prefix web`.

- [ ] **Step 7: Commit**

```bash
git add web .github/workflows/ci.yml .gitignore .claude/launch.json
git commit -m "feat(web): Vite app with Portfoliov2 tokens, themes, API client and polling"
```

---

### Task 3: Chart, timeframes and ET time

**Files:**
- Create: `web/src/lib/time.ts`, `web/src/lib/chart.ts`, `web/src/components/Chart.tsx`, `web/src/components/TopBar.tsx` (timeframe tabs, Trades toggle and "Delayed 10m" for now)
- Test: `web/tests/lib/time.test.ts`, `web/tests/lib/chart.test.ts`, `web/tests/components/Chart.test.tsx`

**Interfaces:**
- Consumes: `api.bars` and `usePoll` (Task 2).
- Produces:
  - `type Tf = "1d" | "4h" | "1h" | "15m" | "5m" | "1m"`. The tab labels are `D 4H 1H 15m 5m 1m`, and the default is `5m`.
  - `nyTime(sec: number): string` returns `HH:mm` in ET. `nyDate(sec: number): string` returns `YYYY-MM-DD` in ET. `toNaiveIso(local: string): string` turns a `datetime-local` value into `YYYY-MM-DDTHH:mm:00` with no zone.
  - `mergeBars(old: Bar[], fresh: Bar[]): Bar[]` returns bars sorted by `time` and unique by `time`, with the fresh bar winning.
  - `candleColours(css: CSSStyleDeclaration): {upColor, downColor, wickUpColor, wickDownColor, borderVisible: false}`.
  - `<Chart symbol tf trades overlays>`. `overlays` is filled in Task 6, and the chart exposes `onMarkerClick(entryId)`.

- [ ] **Step 1: Write the failing tests**

```ts
it("shows ET in the US/EU DST gap", () => {
  expect(nyTime(Date.UTC(2026, 2, 10, 13, 30) / 1000)).toBe("09:30")  // US on EDT, Madrid on CET
  expect(nyTime(Date.UTC(2026, 9, 28, 13, 30) / 1000)).toBe("09:30")  // Madrid on CET, US still EDT
  expect(nyDate(Date.UTC(2026, 10, 3, 3, 0) / 1000)).toBe("2026-11-02")
})
it("toNaiveIso keeps the wall-clock time and adds no zone", () => {
  expect(toNaiveIso("2026-11-10T10:00")).toBe("2026-11-10T10:00:00")
})
it("mergeBars de-duplicates overlap, keeps order and lets the fresh bar win", () => {
  const a = [bar(1, 10), bar(2, 11), bar(3, 12)], b = [bar(3, 13), bar(4, 14)]
  expect(mergeBars(a, b).map(x => [x.time, x.close])).toEqual([[1, 10], [2, 11], [3, 13], [4, 14]])
  expect(mergeBars([], [])).toEqual([])
})
it("candle colours come from the tokens", () => {
  document.documentElement.style.setProperty("--brand", "#3d5a4a")
  document.documentElement.style.setProperty("--down", "#a32d2d")
  expect(candleColours(getComputedStyle(document.documentElement)))
    .toMatchObject({ upColor: "#3d5a4a", downColor: "#a32d2d" })
})
// Chart.test.tsx: lightweight-charts mocked with vi.mock
it("shows an empty state when there are no bars", async () => {
  mockApi({ bars: [] })
  render(<Chart symbol="NVDA" tf="1m" trades overlays={none} onMarkerClick={() => {}} />)
  expect(await screen.findByText("No 1m bars for NVDA yet")).toBeInTheDocument()
})
```

- [ ] **Step 2: Run them to check they fail**

Run: `npm --prefix web test -- time chart Chart`
Expected: FAIL.

- [ ] **Step 3: Implement**
  - `nyTime` and `nyDate` use `Intl.DateTimeFormat("en-GB", {timeZone: "America/New_York", ...})`.
  - The chart uses the `lightweight-charts` v5 API: `createChart`, `chart.addSeries(CandlestickSeries, ...)` and `localization.timeFormatter` plus `timeScale.tickMarkFormatter`, using `nyTime` and `nyDate`.
  - Its layout uses `--bg` and `--ink`, and its grid lines and borders use `--line`.
  - A `MutationObserver` on `<html data-theme>` and a `matchMedia("(prefers-color-scheme: dark)")` listener re-apply the colours.
  - On the first load the chart calls `setData`. Each poll fetches `start = last bar time`, merges with `mergeBars`, and calls `series.update` for each bar at or after the last drawn time.
  - The chart resizes with `autoSize: true`.
  - The timeframe tabs persist to `apollo.tf`. The active tab gets `aria-current="true"` and an ink underline, as in the mockup.

- [ ] **Step 4: Run the tests and check in the browser**

Run: `npm --prefix web test && npm --prefix web run typecheck`, then `python -m apollo.api.main` and preview `web`.
Expected:
- MNQ 5m candles appear with ET labels;
- switching to D, 4H and 1m redraws;
- toggling the theme recolours the candles.

- [ ] **Step 5: Commit**

```bash
git add web/src web/tests
git commit -m "feat(web): candle chart with ET times, timeframes and incremental polling"
```

---

### Task 4: Wordmark, ticker picker

**Files:**
- Create: `web/src/components/Wordmark.tsx`, `web/src/components/EndMark.tsx`, `web/src/components/TickerPicker.tsx`
- Modify: `web/src/components/TopBar.tsx`
- Test: `web/tests/components/TickerPicker.test.tsx`

**Interfaces:**
- Consumes: `api.symbols()` and `storage`.
- Produces:
  - `<Wordmark/>` renders `APOLLO` with a raised `©`. The `©` uses the Portfoliov2 markup: `relative -top-[0.7em] ml-px text-[0.4em] font-medium`, with `aria-hidden`.
  - `<EndMark className/>` is the ⊣ SVG (`M2 12h18M20 4v16`, stroke 1.25).
  - `<TickerPicker value onChange/>`.

- [ ] **Step 1: Write the failing test**

```tsx
it("groups futures and stocks, filters by code or name, and remembers the pick", async () => {
  mockApi({ symbols: [sym("MNQ", "Micro E-mini Nasdaq-100", "future"),
                      sym("MES", "Micro E-mini S&P 500", "future"), sym("NVDA", "NVIDIA", "stock")] })
  const onChange = vi.fn()
  render(<TickerPicker value="MNQ" onChange={onChange} />)
  await user.click(screen.getByRole("button", { name: /MNQ/ }))
  expect(screen.getByText("Futures")).toBeInTheDocument(); expect(screen.getByText("US stocks")).toBeInTheDocument()
  await user.type(screen.getByPlaceholderText("Search futures or US stocks"), "nvi")
  expect(screen.queryByText("MES")).toBeNull()
  await user.keyboard("{Enter}")
  expect(onChange).toHaveBeenCalledWith("NVDA"); expect(localStorage.getItem("apollo.symbol")).toBe("NVDA")
})
it("says so when nothing matches", async () => { /* type "zzz" → "No symbol matches zzz" */ })
```

- [ ] **Step 2: Run it to check it fails**

Run: `npm --prefix web test -- TickerPicker`
Expected: FAIL.

- [ ] **Step 3: Implement with Radix `Popover`**
  - The popover opens with the menu's wipe keyframe, over 0.45 s.
  - The search input filters case-insensitively on code and name. Enter picks the first match, and ↑/↓ move through the matches.
  - Each row is a two-column grid (code `w-16`, name in muted text).
  - If the stored symbol isn't in `/symbols` any more, the picker falls back to `MNQ`.

- [ ] **Step 4: Run the tests**

Run: `npm --prefix web test && npm --prefix web run typecheck`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src web/tests
git commit -m "feat(web): APOLLO wordmark and searchable ticker picker"
```

---

### Task 5: The rail: checklist, signal with Take trade, model check

**Files:**
- Create: `web/src/components/Rail.tsx`, `web/src/lib/trade.ts`
- Test: `web/tests/lib/trade.test.ts`, `web/tests/components/Rail.test.tsx`

**Interfaces:**
- Consumes: `api.signal`, `api.forecast`, `api.journal.take`, `api.journal.list` and `usePoll`.
- Produces:
  - `openR(e: Pick<Entry, "side" | "entry" | "initial_stop">, last: number): number | null`;
  - `fmtPrice(x: number | null, tick = 0.25): string` (Geist Mono, thousands separators, "Not recorded" for null);
  - `fmtR(r: number | null): string` (`+1.25R` or `−0.50R`, using a real minus sign);
  - `<Rail symbol openTrade lastClose onTaken(id)/>`.

- [ ] **Step 1: Write the failing tests**

```ts
it("openR is measured against the opening stop and signed by side", () => {
  expect(openR({ side: "long", entry: 100, initial_stop: 98 }, 103)).toBe(1.5)
  expect(openR({ side: "short", entry: 100, initial_stop: 102 }, 103)).toBe(-1.5)
  expect(openR({ side: "long", entry: null, initial_stop: 98 }, 103)).toBeNull()
  expect(fmtR(-0.5)).toBe("−0.50R"); expect(fmtPrice(29987)).toBe("29,987.00")
})
```
```tsx
it("lists the checklist rows with their state", async () => {
  mockApi({ signal: waiting([row("daily_bias", "pass", "Bear C2 at a swing high"), row("5m_trigger", "wait", "No 5m trigger")]) })
  render(<Rail symbol="MNQ" openTrade={null} lastClose={null} onTaken={() => {}} />)
  expect(await screen.findByText("Bear C2 at a swing high")).toBeInTheDocument()
  expect(screen.queryByRole("button", { name: "Take trade" })).toBeNull()
})
it("Take trade sends the edited fill and size", async () => {
  mockApi({ signal: trigger({ entry: 102, contracts: 2 }), take: { id: 7 } })
  const onTaken = vi.fn(); render(<Rail symbol="MNQ" openTrade={null} lastClose={null} onTaken={onTaken} />)
  await user.click(await screen.findByRole("button", { name: "Take trade" }))
  await user.clear(screen.getByLabelText("Fill")); await user.type(screen.getByLabelText("Fill"), "102.25")
  await user.clear(screen.getByLabelText("Contracts")); await user.type(screen.getByLabelText("Contracts"), "1")
  await user.click(screen.getByRole("button", { name: "Save trade" }))
  expect(takeSpy).toHaveBeenCalledWith("MNQ", { fill: 102.25, size: 1 }); expect(onTaken).toHaveBeenCalledWith(7)
})
it("shows the API's reason when the signal expired", async () => {
  mockApi({ signal: trigger({}), take: apiError(422, "there is no trade signal right now") })
  /* click Take trade, Save trade */
  expect(await screen.findByText("there is no trade signal right now")).toBeInTheDocument()
})
it("says the model isn't trained for stocks", async () => {
  mockApi({ signal: { status: "no_model", checklist: [] }, forecast: { status: "no_model" } })
  render(<Rail symbol="NVDA" openTrade={null} lastClose={null} onTaken={() => {}} />)
  expect(await screen.findByText("Model not trained for this symbol")).toBeInTheDocument()
})
```

- [ ] **Step 2: Run them to check they fail**

Run: `npm --prefix web test -- trade Rail`
Expected: FAIL.

- [ ] **Step 3: Implement the rail**

The rail is 260px wide, with three `<section>`s split by hairlines and no cards. Each has a small mono uppercase label: **Top-down**, **Signal** and **Model check, last 60 sessions**.

- **Checklist:**
  - Labels: Daily bias, 4H, 1H, 15m, 5m trigger.
  - A filled dot means `pass`, a hollow dot `wait`, a `--down` dot `fail` and a muted dash `no_data`.
  - The `detail` text sits on the right in mono.
- **Signal:**
  - The direction ("Long" or "Short", in brand), then contracts, entry, stop, target and risk of limit, with a 3px bar.
  - `waiting` or `flat` shows "No trade signal".
  - **Take trade** shows only on `trigger`. It opens an inline form with Fill and Contracts prefilled. **Save trade** posts it.
  - While a trade is open, this section shows the open trade instead: side, entry, stop, target, live open R from `lastClose`, a **Close trade** button and a **Confirm exit** button.
    - Close trade takes an exit price and calls `close` with reason `manual`.
    - Confirm exit appears when `needs_confirm` is true. It calls `close` with the same exit and the stored `exit_reason`, so the auto reason is kept.
- **Model check:** range hit rate and regime accuracy as percentages, from `forecast.model_check`.
- Every section has a skeleton, an empty state and an `ErrorLine`.

- [ ] **Step 4: Run the tests**

Run: `npm --prefix web test && npm --prefix web run typecheck`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src web/tests
git commit -m "feat(web): top-down checklist, signal with Take trade, model check rail"
```

---

### Task 6: Trades on the chart

**Files:**
- Modify: `web/src/lib/chart.ts`, `web/src/components/Chart.tsx`, `web/src/App.tsx`
- Test: `web/tests/lib/chart.test.ts`

**Interfaces:**
- Consumes: `api.journal.list`, `api.journal.stats` and `api.journal.autoClose` (polled with `/bars` while a trade for the symbol is open).
- Produces:
  - `tradeLines(e: Entry, css): PriceLineSpec[]`:
    - an entry line (solid, `--ink`);
    - a stop line (dashed, `--down`);
    - a target line (dashed, `--brand`);
    - no lines for missing prices or closed trades.
  - `tradeMarkers(entries: Entry[], symbol: string, tf: Tf): MarkerSpec[]`:
    - intraday only;
    - entry: an arrow at `opened_at` (up for long, down for short);
    - exit: a circle at `closed_at`;
    - each marker carries its `id`;
    - none for imported rows (they have no time of day).
  - `dayDots(calendar, tf: Tf): MarkerSpec[]`, on `1d` only: one dot per day, brand when `r >= 0` and down otherwise.
  - `type PriceLineSpec = {price, color, lineStyle: 0 | 2, title}`, where 2 is dashed.
  - `type MarkerSpec = {time, position, shape, color, id}`.

- [ ] **Step 1: Write the failing tests**

```ts
it("draws entry, dashed stop and dashed target for an open trade", () => {
  const l = tradeLines(entry({ entry: 102, stop: 99.75, target: 105, exit: null }), css)
  expect(l.map(x => [x.title, x.price, x.lineStyle])).toEqual(
    [["Entry", 102, 0], ["Stop", 99.75, 2], ["Target", 105, 2]])
  expect(l[1].color).toBe(css.down); expect(l[2].color).toBe(css.brand)
  expect(tradeLines(entry({ exit: 104 }), css)).toEqual([])
  expect(tradeLines(entry({ target: null, exit: null }), css).map(x => x.title)).toEqual(["Entry", "Stop"])
})
it("markers only on intraday views, for this symbol, never for imported rows", () => {
  const es = [entry({ id: 1 }), entry({ id: 2, symbol: "MES" }), entry({ id: 3, source: "imported" })]
  expect(tradeMarkers(es, "MNQ", "5m").map(m => m.id)).toEqual([1, 1])   // entry + exit
  expect(tradeMarkers(es, "MNQ", "1d")).toEqual([])
})
it("day dots are coloured by the day's R and only on the daily chart", () => {
  const d = dayDots([{ date: "2026-11-03", n: 1, r: -1, "pnl_$": -50 }, { date: "2026-11-04", n: 1, r: 0, "pnl_$": 0 }], "1d")
  expect(d.map(x => x.color)).toEqual([css.down, css.brand])
  expect(dayDots([], "5m")).toEqual([])
})
```

- [ ] **Step 2: Run them to check they fail**

Run: `npm --prefix web test -- chart`
Expected: FAIL.

- [ ] **Step 3: Implement**
  - Draw markers with v5's `createSeriesMarkers(series, markers)`, and price lines with `series.createPriceLine`. Clear both and redraw whenever the entries or the theme change.
  - The Trades toggle (`apollo.trades`) hides markers and dots but never the open trade's lines.
  - Clicking near a marker uses `chart.subscribeClick` and the nearest marker time, within one bar, then calls `onMarkerClick(id)`.
  - After Take trade, `App` refreshes the journal list so the lines appear at once.

- [ ] **Step 4: Run the tests and check in the browser**

Run: `npm --prefix web test`. Then, in the preview, create a manual MNQ trade through the API.
Expected: the three lines show and the open R updates in the rail.

- [ ] **Step 5: Commit**

```bash
git add web/src web/tests
git commit -m "feat(web): draw open trades, entry/exit markers and journal day dots"
```

---

### Task 7: The APOLLO menu and pages

**Files:**
- Create: `web/src/components/Menu.tsx`, `web/src/components/Placeholder.tsx`
- Modify: `web/src/index.css` (menu keyframes), `web/src/App.tsx` (hash route), `web/src/components/TopBar.tsx` (burger)
- Test: `web/tests/components/Menu.test.tsx`

**Interfaces:**
- Consumes: `useTheme` and `<Wordmark/>`/`<EndMark/>`.
- Produces:
  - `<Menu page onNavigate(page) onJournal() onNewEntry()/>`;
  - `type Page = "chart" | "backtest" | "models" | "case-study"`;
  - `useHashPage(): [Page, (p: Page) => void]`, which defaults to `chart` for any unknown hash.

- [ ] **Step 1: Write the failing test**

```tsx
it("opens from the burger, lists the five tiles in order, and routes", async () => {
  const nav = vi.fn(), journal = vi.fn()
  render(<><TopBar … /><Menu page="chart" onNavigate={nav} onJournal={journal} onNewEntry={() => {}} /></>)
  await user.click(screen.getByRole("button", { name: "Open menu" }))
  const tiles = within(screen.getByRole("dialog", { name: "Menu" })).getAllByRole("link")
  expect(tiles.map(t => t.textContent)).toEqual(["01Chart", "02Journal", "03Backtest", "04Models", "05Case study"])
  await user.click(screen.getByText("Journal")); expect(journal).toHaveBeenCalled()
})
it("theme tile switches theme; Escape closes", async () => { /* Dark → data-theme=dark; Escape → dialog gone */ })
it("unknown hash falls back to the chart", () => { location.hash = "#/nope"; /* useHashPage() → "chart" */ })
```

- [ ] **Step 2: Run it to check it fails**

Run: `npm --prefix web test -- Menu`
Expected: FAIL.

- [ ] **Step 3: Implement it as a port of Portfoliov2 `src/components/MobileNav.tsx`, used at every width**
  - **Burger:** a `size-9` bordered button with three `h-px w-4` bars. The outer bars get `group-hover:scale-x-50` with `duration-500 ease-[cubic-bezier(0.7,0,0.3,1)]`. On hover, the border and colour turn brand.
  - **Panel:**
    - `Dialog.Content data-menu`, `fixed inset-0 z-50 flex h-dvh flex-col bg-soft px-5`;
    - a top row with the wordmark and **Close ⊣**;
    - the tiles at `mt-auto`, in a grid of 5 columns, or 2 below 768px;
    - each tile is `overflow-hidden border`. Hovering one dims the others with `[&:has(li:hover)>li]:opacity-15`.
  - **Footer row** (`grid-cols-[1fr_2fr]`):
    - a Theme tile with a Light / Dark / Auto segmented control (`aria-pressed`);
    - a brand **New journal entry** tile, `h-36`, with the ⊣ mark at the top right.
  - **Stagger:** `--i` and `--r` per item, as in `MobileNav`.
  - **CSS:** copy Portfoliov2's `index.css` lines exactly:

```css
@media (prefers-reduced-motion: no-preference) {
  [data-menu][data-state='open'] { animation: menu-in 1s cubic-bezier(0.9, 0, 0.1, 1) both; }
  [data-menu][data-state='closed'] { animation: menu-out 0.8s cubic-bezier(0.9, 0, 0.1, 1) both; }
  [data-menu][data-state='open'] [data-menu-item] { animation: link-in 0.75s cubic-bezier(0.7, 0, 0.3, 1) both; animation-delay: calc(0.3s + var(--i) * 0.05s); }
  [data-menu][data-state='closed'] [data-menu-item] { animation: link-out 0.5s cubic-bezier(0.7, 0, 0.3, 1) both; animation-delay: calc(var(--r) * 0.03s); }
}
@keyframes menu-in { from { clip-path: inset(0 0 100% 0); } to { clip-path: inset(0); } }
@keyframes menu-out { from { clip-path: inset(0); } to { clip-path: inset(0 0 100% 0); } }
@keyframes link-in { from { transform: translateY(100%) rotate(5deg); } to { transform: none; } }
@keyframes link-out { from { transform: none; } to { transform: translateY(100%) rotate(5deg); } }
```

  - **Placeholder pages:** Backtest, Models and Case study render `<Placeholder title>`, which reads "This page arrives in the next build." in muted text, with the footer. The tiles stay in the menu so the layout matches the mockup.

- [ ] **Step 4: Run the tests and check in the browser**

Run: `npm --prefix web test`. Then open and close the menu in the preview at 1440px and at 375px.
Expected: the wipe-down and the staggered tiles both play; closing reverses them.

- [ ] **Step 5: Commit**

```bash
git add web/src web/tests
git commit -m "feat(web): APOLLO menu ported from Portfoliov2 MobileNav, hash pages"
```

---

### Task 8: The journal sheet

**Files:**
- Create: `web/src/components/journal/Sheet.tsx`, `TradeList.tsx`, `TradeDetail.tsx`, `EntryForm.tsx`, `Stats.tsx`
- Modify: `web/src/App.tsx` (the sheet opens from the menu, from New journal entry and from a chart marker)
- Test: `web/tests/components/journal/*.test.tsx`

**Interfaces:**
- Consumes: the `api.journal.*` functions, `mediaUrl`, `fmtR`/`fmtPrice` and `toNaiveIso`.
- Produces:
  - `<Sheet open selectedId mode: "view" | "new" onOpenChange/>`;
  - `entryBody(form: EntryFormState): JournalIn`, a pure function that maps the form to the API body.

- [ ] **Step 1: Write the failing tests**

```tsx
it("lists trades newest first with R coloured by sign, and opens the detail", async () => {
  mockApi({ journal: [entry({ id: 2, r: -1 }), entry({ id: 1, r: 1.5, source: "imported", side: null, entry: null })] })
  render(<Sheet open selectedId={null} mode="view" onOpenChange={() => {}} />)
  const rows = await screen.findAllByRole("button", { name: /MNQ/ })
  expect(rows[0]).toHaveTextContent("−1.00R"); expect(within(rows[0]).getByText("−1.00R")).toHaveClass("text-down")
  await user.click(rows[1])
  expect(screen.getAllByText("Not recorded").length).toBeGreaterThan(0)   // case-study row
  expect(screen.getByText("Scaled")).toBeInTheDocument()                  // labelled scaled dollars
})
it("entryBody sends ET wall-clock time without a zone and drops empty fields", () => {
  expect(entryBody(form({ opened_at: "2026-11-10T10:00", target: "", tags: "Gamba, A+ setup" })))
    .toMatchObject({ opened_at: "2026-11-10T10:00:00", tags: ["Gamba", "A+ setup"] })
  expect(entryBody(form({ target: "" }))).not.toHaveProperty("target")
})
it("shows the API's 422 next to the form and keeps what was typed", async () => { /* size 0 → message, values kept */ })
it("stats strip and calendar render from /journal/stats", async () => {
  /* by_source signal/manual/imported counts and win rate, skipped count, worst day, calendar cells coloured by R */
})
it("deletes only after a confirm", async () => { /* Delete → "Delete this trade? This can't be undone." → Delete */ })
```

- [ ] **Step 2: Run them to check they fail**

Run: `npm --prefix web test -- journal`
Expected: FAIL.

- [ ] **Step 3: Implement**
  - **Sheet:** a Radix Dialog with the same wipe as the menu (`data-menu` on its content), at full screen, `grid-cols-[minmax(260px,360px)_1fr]`. Below 768px it stacks the list (40dvh) over the detail.
  - **List:** a sticky header with "Journal" and a brand **New** button. Each row shows the date (ET), symbol, strategy, account and R in mono, with `text-brand` for R ≥ 0 and `text-down` for R < 0.
  - **Detail:**
    - a header row with Close ⊣;
    - a large line with side, symbol and R;
    - a 4-column hairline grid with entry, stop, initial stop, target, exit, size, fees, P&L, account, stage, grade, source, opened, closed and exit reason;
    - "Not recorded" for nulls, and "Scaled" beside P&L when `scaled`;
    - the screenshot (`<img src={mediaUrl(...)}>`), or a dashed drop zone that uploads PNG or JPEG;
    - notes as plain text with line breaks.

    Edit, Delete and Close trade are shown only for non-imported rows.
  - **EntryForm:** opened (`datetime-local`, labelled "Opened (ET)"), symbol, side, entry, stop, target, size, fees, account, stage, strategy, grade, tags (comma-separated) and notes. Edit sends PATCH with the changed fields only.
  - **Stats**, above the list on desktop: a strip with these cells:
    - signal, manual and imported, each with n, win rate and mean R;
    - skipped signals;
    - the worst day.

    Below the strip is a month calendar of daily R, one cell per day and coloured by sign. Clicking a day filters the list.

- [ ] **Step 4: Run the tests and check in the browser**

Run: `npm --prefix web test && npm --prefix web run typecheck`. Then, in the preview, check that:
- the 51 imported case-study trades list;
- a manual entry saves, edits and deletes;
- a screenshot uploads and shows.

- [ ] **Step 5: Commit**

```bash
git add web/src web/tests
git commit -m "feat(web): journal sheet with detail, entry form, stats strip and calendar"
```

---

### Task 9: Smoke test, run notes, final checks

**Files:**
- Create: `web/playwright.config.ts`, `web/e2e/smoke.spec.ts`, `web/e2e/fixtures.ts`, `web/README.md`
- Modify: `.gitignore` if Playwright adds paths

**Interfaces:**
- Consumes: the whole app.
- Produces: `npm --prefix web run e2e`. It isn't in CI, so CI stays fast and needs no browser download.

- [ ] **Step 1: Write the smoke test (spec 7)**

```ts
test("chart, ticker, timeframe, menu, journal and take trade", async ({ page }) => {
  await mockApi(page)   // page.route("http://127.0.0.1:8000/**") with fixtures.ts; take returns {id: 9}
  await page.goto("/")
  await expect(page.getByText("Research tool. Not financial advice.")).toBeVisible()
  await page.getByRole("button", { name: /MNQ/ }).click(); await page.getByText("MES").click()
  await page.getByRole("button", { name: "1H", exact: true }).click()
  await expect(page).toHaveURL(/#\/chart/)
  await page.getByRole("button", { name: "Open menu" }).click()
  await page.getByRole("link", { name: /Journal/ }).click()
  await expect(page.getByRole("dialog")).toContainText("Journal")
  await page.keyboard.press("Escape")
  await page.getByRole("button", { name: "Take trade" }).click()
  await page.getByRole("button", { name: "Save trade" }).click()
  await expect(page.getByText(/Open R/)).toBeVisible()
})
test("API down shows how to start it, then recovers", async ({ page }) => {
  await page.route("http://127.0.0.1:8000/**", r => r.abort())
  await page.goto("/")
  await expect(page.getByText("Start the API: python -m apollo.api.main").first()).toBeVisible()
  await page.unroute("http://127.0.0.1:8000/**"); await mockApi(page)
  await page.evaluate(() => document.dispatchEvent(new Event("visibilitychange")))
  await expect(page.getByText("Top-down")).toBeVisible()
})
```

- [ ] **Step 2: Install the browser and run it**

Run: `npx --prefix web playwright install chromium && npm --prefix web run e2e`
Expected: 2 passed. `webServer` in the config starts `npm run dev` on port 5173.

- [ ] **Step 3: Write `web/README.md`**

It's short. It explains how to run the app with two terminals:
- `python -m apollo.api.main`;
- `npm --prefix web run dev`.

It explains how to run tests in PyCharm Community: Run › Edit Configurations (Shift+Alt+F10 / ⌃⌥R), then add an npm config for `web/package.json`. It also lists the four `localStorage` keys. Write it with the humanizer skill.

- [ ] **Step 4: Run every check**

Run:
```bash
set -o pipefail && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/pyright && .venv/bin/pytest -q \
  && npm --prefix web run typecheck && npm --prefix web test && npm --prefix web run build && npm --prefix web run e2e
```
Expected: everything passes.

- [ ] **Step 5: Check in the browser on real data, in both themes, at 1440px and 375px**

Expected:
- no horizontal scroll;
- the page itself doesn't scroll at the top or bottom edges (Plan 2 rule): only the journal list and detail scroll;
- the console shows no errors.

- [ ] **Step 6: Commit**

```bash
git add web
git commit -m "test(web): Playwright smoke test and run notes"
```

---

## Open for Vaughn

1. **Approve the packages** in the Tech Stack table, including Playwright and its one-off Chromium download.
2. **"Any valid US stock symbol can be typed in"** (spec 5.2) needs the API to fetch unknown symbols from Yahoo on demand and add them to the store. This plan keeps the picker to the 14 configured symbols. Typed-in symbols could be a small task in Plan 7.
3. **Backtest, Models and Case study** show an empty state until Plan 7, but they stay in the menu so it matches the mockup. You could hide them until they're built.

## Self-review notes

- **Spec coverage:**
  - 5.2: layout (Tasks 2, 3 and 5), tokens and themes (Task 2), type (Task 2), menu (Task 7), ticker picker (Task 4), journal sheet (Task 8), taste rules (every task's states).
  - 5.8: dots and markers (Task 6), Take trade and the lines (Tasks 5 and 6), close and confirm auto-close (Tasks 1 and 5), the signal/manual/skipped split (Task 8).
  - 5.9: polling (Tasks 2 and 3).
  - 5.11: page 1 (Tasks 3–6) and the page 2 sheet, stats and calendar (Task 8).
  - Section 7: frontend CI (Task 2) and the smoke test (Task 9).
- **Deferred to Plan 7:**
  - the guided tour and explainers;
  - the Backtest, Models and Case study pages;
  - static snapshot mode;
  - GitHub Pages;
  - the main README.
- **Risk:** `lightweight-charts` v5 changed its marker and series API from the v4 mockup. Task 3 uses `addSeries(CandlestickSeries)`, and Task 6 uses `createSeriesMarkers`.
