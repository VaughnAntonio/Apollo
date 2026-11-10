export type TourStep = { target: string; title: string; body: string }

/** The guided tour over the chart screen, in the spec's order. Targets are data-tour values. */
export const TOUR_STEPS: TourStep[] = [
  {
    target: 'ticker',
    title: 'Pick a market',
    body: 'Choose any of the 14 futures and stocks Apollo collects. The chart follows your selection. The checklist and signal are available on markets with model support.',
  },
  {
    target: 'timeframes',
    title: 'Timeframes',
    body: 'Switch the chart from 1 minute to 1 day. The Fractal Model reads them top down: the daily bias first, then 4H, 1H and 15m, then a 5m trigger.',
  },
  {
    target: 'regime',
    title: 'Regime forecast',
    body: 'Before each session the regime detector gives the odds that the day trends up, trends down, chops or stays normal.',
  },
  {
    target: 'range',
    title: 'Range forecast',
    body: 'The range forecaster sets a bound above and below the open that should hold on 9 days in 10.',
  },
  {
    target: 'checklist',
    title: 'The checklist',
    body: 'Each row is one step of the Fractal Model. A filled dot has passed, an empty one is still waiting, a red one has failed.',
  },
  {
    target: 'signal',
    title: 'Signal and size',
    body: "When every step passes, the signal shows the entry, stop and target, and sizes the trade using the configured percentage of account value. The signal also shows how much of the drawdown limit that risk uses.",
  },
  {
    target: 'take-trade',
    title: 'Take trade',
    body: 'One click logs the trade in the journal along with what the model said at that moment, so you can compare the two later.',
  },
  {
    target: 'journal',
    title: 'Journal and pages',
    body: 'The menu opens the journal, with every trade, stats by setup and a calendar of daily R. The backtest, models and case study pages are there too.',
  },
  {
    target: 'model-check',
    title: 'Model check',
    body: 'How the models did over the last 60 sessions. When these numbers slip, trust the signal less.',
  },
]

const KEY = 'apollo.tour'

/** Offer the tour only when storage works, so a dismissal is sure to stick. */
export function shouldOfferTour(): boolean {
  try {
    return localStorage.getItem(KEY) !== 'done'
  } catch {
    return false
  }
}

export function markTourDone(): void {
  try {
    localStorage.setItem(KEY, 'done')
  } catch {
    // storage blocked: shouldOfferTour is already false
  }
}
