# Model card: range forecaster

Sets a bound above and below the New York open that the session's high and low should stay inside on 9 days in 10. The Fractal Model's range filter uses it to skip targets the day is unlikely to reach.

Numbers below are for MNQ from `reports/models_MNQ.json`, generated 2026-11-10. Research tool. Not financial advice.

## Data

The same sessions as the regime detector: MNQ hourly and daily bars from Yahoo Finance since November 2024, with the same 17 sessions left out for short days, warm-up and a roll jump.

## Target

Two numbers per session: how far the high went above the open, and how far the low went below it, in points.

## Features

The regime detector's features, plus its four out-of-sample regime probabilities for the day.

## Validation

For each side, a gradient-boosted median regression predicts the excursion. A conformal step then widens the prediction by the 95th percentile of the errors on the previous 120 scored sessions, so each side should hold about 95% of the time and both together about 90%. Everything is walk-forward: the first 250 sessions train, the model refits each month, and the calibration errors come from earlier sessions only.

## Metrics

Over 207 scored sessions both bounds held on 88.4% of days, against the 90% target. The upper bound held on 93.7% and the lower on 94.7%. The bounds averaged 1,079 points wide.

| Regime that day | Both bounds held |
|---|---|
| Chop | 98.2% |
| Normal | 95.2% |
| Trend down | 75.9% |
| Trend up | 68.4% |

On days with a scheduled event both bounds held 84.8% of the time; on other days, 89.4%.

## Failure modes

The bounds break mostly on trend days, which is when a range filter costs the most. Event days are a little worse than the rest. The coverage target holds on average, so a run of broken days can happen even when the model is behaving as designed.

## Limitations

A 1,079-point zone is wide, so as a trade filter it mostly removes far-off targets. Coverage is checked on a few hundred sessions, and the live ledger has no scored days yet.
