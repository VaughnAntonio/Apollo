# MNQ Predictor

Design: `docs/superpowers/specs/2026-11-08-mnq-predictor-design.md`. Plans: `docs/superpowers/plans/`.

## Skills to use in this repo

- Writing any prose (code comments, docstrings, README, docs, model cards, UI copy, commit messages, PR descriptions): apply the `humanizer` skill in `.claude/skills/humanizer/` (from github.com/blader/humanizer, MIT). Use its embedded mode: write the final text only. Keep code, identifiers, commands and paths unchanged.
- Code: `superpowers` workflow (plans, test-driven development, verification), `ponytail` (smallest change that solves the task) and `karpathy-guidelines`.
- UI: `design-taste-frontend-v1`, tuned down for minimalism, plus the Portfoliov2 tokens in the spec. Charts: `dataviz`.

## Rules

- Free data and hosting only. Ask Vaughn before adding a dependency or pushing.
- No lookahead: features at time t use only data available at t.
- Mark deliberate shortcuts with `# shortcut:`.
