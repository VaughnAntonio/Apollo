---
name: journal-review
description: Use when Vaughn asks to review his trading journal, a week of trades, or his discipline. Applies the PTJ, Seykota, Turtle and Livermore skills as lenses to his MNQ trades and writes a dated report.
---

# Journal review

Review Vaughn's trades the way four rule-driven traders would, using only numbers from the
data. The goal is one concrete change for next week, not a lecture.

## Inputs

Use the first source that exists:

1. Apollo's journal export: run
   `.venv/bin/python -m apollo.journal.stats --out docs/reviews/journal-export.csv` and read that
   CSV. It holds real trades, so it stays out of git. Rows with `scaled` true are the case study's.
2. The case study's public data: `data/public/trades_public.csv` (one row per journalled
   trade) and `data/public/days_public.csv` (one row per trading day) in
   `VaughnAntonio/mnq-trading-case-study`. If no local clone exists, run
   `gh repo clone VaughnAntonio/mnq-trading-case-study -- --depth 1` into the scratchpad.

Dollar amounts in the case-study files are scaled by one hidden factor. Quote R-multiples and
ratios, which are unchanged, and label any dollar figure "scaled".

## Lenses

Read each skill's `SKILL.md` in `.claude/skills/` before using it.

| Lens | Skill | Question it asks of the journal |
|---|---|---|
| Don't lose big | `ptj-macro-trend` | Was any day's loss large against the account's drawdown limit? Was a loser ever added to? |
| Follow the system | `seykota-systematic-trend` | Do days tagged "Gamba", or trades without a strategy or grade, do worse than rule-based ones? |
| Size from risk | `turtle-trading` | Is risk per trade steady, or does size swing? How much of the limit was at risk at once? |
| Cut losers, press winners | `livermore` | Are losses held near -1R or allowed past it? Are winners cut early (average win R vs planned R:R)? |

## Process

1. Load the data and print, for each account stage (backtest, forward test, eval, funded): the
   number of days and trades, win rate, average win R and average loss R, the worst day in R,
   and the worst day as a multiple of the drawdown limit (`prop_limits_public.csv`).
2. For each lens, compute only what its question needs, from the data. Don't invent trades,
   prices or dates. If a lens can't be judged (for example, no add-on trades are recorded),
   say so.
3. Rank the three biggest rule breaks, with the date, stage, R-multiple and the lens they break.
4. Pick one change for next week. It must be specific and checkable, such as "stop trading for
   the day at -2R", not "be more disciplined".

## Output

Write `docs/reviews/journal-<YYYY-MM-DD>.md`, using the humanizer skill for the prose:

```md
# Journal review, <date>

Data: <source, date range, n days, n trades>

## Numbers by stage
<one table>

## Lenses
### Don't lose big (PTJ)
Verdict: <holds / breaks / can't tell> — <the numbers behind it>
### Follow the system (Seykota)
### Size from risk (Turtle)
### Cut losers, press winners (Livermore)

## Three biggest rule breaks
1. <date, stage, R, lens, what happened>

## One change for next week
<the rule, and how to check it>
```

## Guardrails

- Every number must trace back to a row in the data. Recompute rather than recall.
- This is a review of past discipline, not a trade signal and not financial advice.
- Keep it short: the reader should be done in two minutes.
