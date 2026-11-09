# Apollo Predictor

Design: `docs/superpowers/specs/2026-11-08-apollo-predictor-design.md`. Plans: `docs/superpowers/plans/`.

## Skills to use in this repo

- Writing any prose (code comments, docstrings, README, docs, model cards, UI copy, commit messages, PR descriptions): apply the `humanizer` skill in `.claude/skills/humanizer/` (from github.com/blader/humanizer, MIT). Use its embedded mode: write the final text only. Keep code, identifiers, commands and paths unchanged.
- Code: `superpowers` workflow (plans, test-driven development, verification), `ponytail` (smallest change that solves the task) and `karpathy-guidelines`.
- UI: `design-taste-frontend-v1`, tuned down for minimalism, plus the Portfoliov2 tokens in the spec. Charts: `dataviz`.
- Risk and journal review: the investor skills in `.claude/skills/` (`ptj-macro-trend`, `seykota-systematic-trend`, `turtle-trading`, `livermore`, `marks-cycles`, `simons-quant`, `druckenmiller`, from questflowai/investorskills, MIT). Use them to review risk rules and, through `journal-review`, Vaughn's journal. Never put them in the trading signal or the backtest (spec 5.15).
- Market context: OpenBB keyless providers only (`cboe`, `nasdaq`, `federal_reserve`) via `apollo.context` (spec 5.14). Nasdaq's calendar lists US events one day late; `normalise_events` corrects it.

## Rules

- Free data and hosting only. Ask Vaughn before adding a dependency or pushing.
- No lookahead: features at time t use only data available at t.
- Mark deliberate shortcuts with `# shortcut:`.
