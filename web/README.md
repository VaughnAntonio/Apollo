# Apollo web app

The chart, checklist, signal and journal for Apollo Predictor. It reads everything from the local API in `src/apollo/api`, which only answers on your own computer.

## Run it

You need two terminals, both opened in the repository root.

```bash
.venv/bin/python -m apollo.api.main
```

```bash
npm --prefix web run dev
```

Then open http://localhost:5173. The first signal and forecast of the day take a minute or two while the models refit. After that they come from a cache.

If another project already uses port 5173, start the web app on another port and tell the API which one:

```bash
npm --prefix web run dev -- --port 5174
```

```bash
.venv/bin/python -m apollo.api.main --web-port 5174
```

The API refuses requests from any other origin, so the two ports must match.

## Tests

```bash
npm --prefix web test
```

```bash
npm --prefix web run typecheck
```

```bash
npm --prefix web run e2e
```

`e2e` runs the Playwright smoke test against a mocked API on port 5175. Run `npx --prefix web playwright install chromium` once before the first run.

In PyCharm Community, add an npm run configuration: Run › Edit Configurations (Shift+Alt+F10 / ⌃⌥R), then + › npm, with `web/package.json` as the package file and `test`, `dev` or `e2e` as the script.

## What the browser remembers

The app keeps four choices in `localStorage`: `apollo.theme` (light, dark or auto), `apollo.symbol`, `apollo.tf` and `apollo.trades` (whether trade markers show). If the browser blocks storage, the app falls back to auto, MNQ, 5m and markers on.

Research tool. Not financial advice.
