# Model card: regime detector

Forecasts, before the New York open, whether the session will trend up, trend down, chop or stay normal. The idea comes from predictive maintenance: the health indicators engineers compute on a vibrating bearing are computed here on hourly returns.

Numbers below are for MNQ from `reports/models_MNQ.json`, generated 2026-11-10. Research tool. Not financial advice.

## Data

Hourly and daily MNQ bars from Yahoo Finance, collected nightly by a GitHub Action. Yahoo serves two years of hourly history, so the sample starts in November 2024. Of 504 sessions, 487 are used: 11 short sessions (holidays and early closes), 5 warm-up sessions without enough history for the indicators, and 1 session with a contract roll jump are left out. Market context (VIX, VIX3M, VXN and the economic calendar) comes from OpenBB's keyless providers.

## Target

The New York session's label, using the case study's body-ratio rule: body ratio is |close − open| / (high − low). Above 0.6 the day is a trend, up or down by the sign of the body. Below 0.3 it is chop. Anything else is normal.

## Features

Health indicators on the hourly returns up to the 08:00 ET cutoff: RMS and its slope, kurtosis, skew, crest factor, the envelope's mean and kurtosis, and spectral kurtosis in low, mid and high bands. Also the overnight range, the gap, distance from the 50-day average, distance in ATRs, and yesterday's label. Context features: VIX, its 5-day change, the VIX term structure, VXN, the VXN to VIX ratio, and flags for FOMC, CPI, payrolls and other scheduled events.

## Validation

Walk-forward with an expanding window. The first 250 sessions only train. After that the model is refitted at the start of each month and scores the sessions it has not seen. Two models are fitted, a logistic regression and gradient boosting; the one with the lower log-loss on sessions before the holdout (2026-08-06) is used. Three baselines are scored the same way: always the most common regime, yesterday's regime, and each regime at its frequency so far. Every research run is logged in `runs/log.csv`, so the number of attempts behind a result is public.

## Metrics

Scored on 237 sessions with both feature sets:

| Model | Accuracy | Log-loss |
|---|---|---|
| Logistic regression (chosen) | 36.7% | 1.443 |
| Gradient boosting | 35.0% | 1.703 |
| Most common regime | 41.4% | 8.103 |
| Yesterday's regime | 28.3% | 9.910 |
| Frequency so far | 41.4% | 1.303 |

The chosen model does not beat the frequency baseline. The ablation tells the same story: health features alone reach a log-loss of 1.338, context alone 1.392, and both together 1.443, so adding features makes the probabilities worse on this sample. Permutation importance on the last 60 sessions ranks the "other event" flag, the overnight range and the FOMC flag highest.

## Failure modes

Trend days are the hardest to call, and they are the days a filter would most need to get right. The model called normal on 178 of 237 sessions, and it caught none of the 42 up-trend days and 1 of the 32 down-trend days. A day with a scheduled event can flip the regime after the cutoff, and the model only sees that the event is on the calendar.

## Limitations

Two years of hourly data gives a few hundred scored sessions, which is small for four classes. The label threshold comes from the case study and was not tuned. The forward ledger only started in November 2026, so there is no live record yet.
