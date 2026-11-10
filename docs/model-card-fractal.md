# Model card: the codified Fractal Model

A rule-based version of TTrades' Fractal Model. On the daily chart, candle 2 sweeps candle 1's high or low at a point of interest and closes back inside. On the hourly chart, a change in the state of delivery (CISD) confirms the turn. The trade enters at the CISD, puts the stop beyond the protected swing and targets the far side of candle 1.

Numbers below are for MNQ from `reports/backtest_MNQ_D-1H.json` (development period only). Research tool. Not financial advice.

## Data

MNQ daily bars from 2019 and hourly bars from November 2024, from Yahoo Finance. Daily setups older than the hourly history can't be checked for a CISD, so 208 of them are left out rather than counted as misses. The 1H-5m layer needs 5-minute bars, which Yahoo keeps for 60 days; all of them fall inside the holdout, so that layer has no development trades yet.

## Target

Not a prediction model: each setup either becomes a trade or is skipped for a stated reason. A trade's result is measured in R, the multiple of the dollars it risked.

## Features

The rules in `config/strategy.toml`: a sweep of at least 1 tick at a swing or a fair-value gap within 20 bars, a CISD on the hourly chart after candle 2 closes, an entry window of 09:00 to 15:00 ET, a minimum reward of 1.5R, and risk of 1% of the account per trade. Variants switch on the regime filter, the range filter, the risk rules, a breakeven stop and an event filter.

## Validation

Everything from 2026-08-06 on is a locked holdout. The development backtest never sees it, and a final run on it is allowed once, from committed code, with the configuration that was locked first. Costs include commission and 1 tick of slippage each side. Results come with a 95% bootstrap range, a prop-firm Monte Carlo, and buy & hold and MA 20/50 benchmarks over the same dates. Every run is logged in `runs/backtests.csv`.

## Metrics

From 2024-11-13 to 2026-07-27, the plain model found 72 setups and took 14 trades. The rest were invalidated (30), short of the minimum reward (15), never confirmed (9), too small to size (3) or outside the entry window (1).

| | Plain variant |
|---|---|
| Trades | 14 |
| Expectancy | −0.36R (95% range −0.74R to +0.07R) |
| Win rate | 21% |
| Max drawdown | −5.06R |
| Profit factor | 0.37 |
| Pass an Apex 50k evaluation, 1% risk | 0.2% |
| Pass, 2% risk | 2.9% |

Holding 1 MNQ contract over the same dates made $14,001; the MA 20/50 rule made $11,901. With the regime filter on, only 1 trade remains; with the range filter alone, 3.

## Failure modes

The setup fights strong trends. 13 of the 14 trades were shorts during a rising market, and 11 of those lost. Invalidation before entry is the most common outcome, so the model trades rarely, under one trade a month.

## Limitations

Fourteen trades can't separate a small edge from noise, and the range of plausible expectancy still includes zero. The rules are one reading of a discretionary method, so a skilled trader applying the same idea could choose differently. Data is free and delayed, and the 4H chart is built from hourly bars.
