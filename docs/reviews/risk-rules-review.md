# Risk-rules review before Plan 4

Date: 2026-11-09. Reviewed: the stop, sizing and trade-limit rules in spec 5.6. Lenses: the
`ptj-macro-trend`, `seykota-systematic-trend`, `turtle-trading` and `livermore` skills. Evidence:
the case study and `docs/reviews/journal-2026-11-09.md`.

Every change below is **proposed: for Vaughn to accept or reject before Plan 4.** Nothing here
changes code yet.

## The rules today (spec 5.6)

- **Stop:** 1 tick beyond the protected low or high from the CISD.
- **Size:** 1% of account size per trade (up to 2%). Contracts = risk ÷ (stop distance × point
  value); skip the trade if that comes to 0.
- **Drawdown limit:** shown as "Risk of drawdown limit" in the rail, as a warning only.
- **Limits:** one position per symbol, at most 2 trades per session, flat by 16:00 ET. Skip the
  trade if reward:risk is below 1.5.
- **Not covered:** a daily loss cap, a rule for event days, and adding to positions.

## Lens by lens

### Don't lose big (Paul Tudor Jones)
The PTJ skill starts with "control downside first" and "define the point where the trade is
wrong". The per-trade stop does that. Nothing does it for the day or for the account, and that
is exactly where the case study's damage came from: a 70R day that was 2.8× the drawdown limit.

- **Keep:** the structural stop, one position at a time.
- **Add:** a daily loss cap. After **−2R** realised in a session, no new trades that day.
- **Change:** turn "Risk of drawdown limit" from a warning into a rule. A trade is blocked when
  its planned loss is more than **25% of the drawdown cushion left**.

### Follow the system (Seykota)
Seykota judges "system adherence, not prediction quality". The journal's rule-free "Gamba" days
averaged −20.5R against +5.1R for ModelV2. Apollo already removes discretion from the signal, so
the remaining risk is overriding it.

- **Keep:** at most 2 trades per session and flat by 16:00. Both are clear and checkable.
- **Add:** anything not produced by the signal goes in the journal as `source = manual`, so the
  journal review can compare manual and signal results every week (spec 5.8 already plans this
  split).
- **Add:** when the account's drawdown cushion falls below half of the limit, risk per trade
  drops from 1% to **0.5%** until the account makes a new high.

### Size from risk (Turtle)
The Turtle skill sizes from a volatility unit and caps total heat. Apollo sizes from the
structural stop, which is fine, but nothing stops a very wide stop or a very tight one from
producing an odd position.

- **Keep:** risk-based contract count and skip-if-zero.
- **Add:** skip the trade when the stop is wider than **half of Plan 3's forecast range** for the
  session. A stop that wide means the setup is already stretched.
- **Add:** a minimum stop of **4 ticks**, so a tiny protected swing can't turn into a huge
  contract count.

### Cut losers, press winners (Livermore)
Livermore says "size from risk first, not from excitement" and add only once the market proves
you right. In the journal, 16 of 18 losing trades were cut by −1R and winners ran past plan
(+6.2R against a planned 2.6), so the habits are mostly there. The two exceptions (−3.5R and
−8R) were held past their stops.

- **Keep:** no adding to losers. The stop is a hard order, never moved further away.
- **Test, don't adopt yet:** moving the stop to breakeven at +1R. It can cut big winners, so
  Plan 4 should backtest it as a variant and keep it only if expectancy improves out of sample.
- **Leave out of v1:** adding to winners (pyramiding). It's a separate system to design and test.

## Event days (OpenBB context)

Plan 3b's ablation (run log attempts 4–6) found the range zone holds on scheduled-release days
about as well as on other days: 89.6% with price features only, 91.7% with OpenBB context added.
In this sample, ranges on release days were only about 1% wider (1,075 vs 1,060 points). So the
event rules below are hypotheses, not lessons the data has already taught. FOMC decisions land
at 14:00 ET, inside the trading session; CPI and payrolls come out at 08:30 ET, before the 09:30
entry window opens.

- **Test in Plan 4:** "no new trades from 13:30 ET on FOMC days" and "half size on any
  high-impact day", both against the plain rule, out of sample.

## Proposed changes

| # | Rule | Today | Proposed | Lens | Evidence | Status |
|---|---|---|---|---|---|---|
| 1 | Daily loss cap | None | No new trades after −2R realised in a session | PTJ | −70R day, 2.8× limit | Proposed |
| 2 | Drawdown guard | Warning only | Block a trade whose planned loss is over 25% of the cushion left | PTJ | 81% of limit in one day (2025-10-10) | Proposed |
| 3 | Size after drawdown | Always 1% | 0.5% while the cushion is below half the limit, until a new high | Seykota | Funded losses averaged −21.5R | Proposed |
| 4 | Manual trades | Not separated | Journal `source = manual`, reviewed weekly against the signal | Seykota | Gamba −20.5R vs ModelV2 +5.1R | Proposed |
| 5 | Wide stop | Allowed | Skip if the stop is wider than half the forecast range | Turtle | Size stopped matching risk (R reached −70) | Proposed |
| 6 | Tight stop | Allowed | Minimum stop of 4 ticks | Turtle | Avoids huge contract counts | Proposed |
| 7 | Breakeven stop | None | Backtest as a variant only | Livermore | Winners ran +6.2R on average | Test in Plan 4 |
| 8 | FOMC afternoon | No rule | Backtest "no new trades after 13:30 ET on FOMC days" | PTJ | FOMC lands mid-session | Test in Plan 4 |
| 9 | Event-day size | No rule | Backtest half size on high-impact days | Turtle | Untested; ranges only ~1% wider on release days so far | Test in Plan 4 |

Rules 1–6 change what Apollo's backtest is allowed to do. Rules 7–9 are hypotheses for the
backtest to settle, and each one counts as an attempt in `runs/log.csv`.
