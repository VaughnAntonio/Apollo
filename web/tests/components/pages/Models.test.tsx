import { render, screen, within } from '@testing-library/react'
import { expect, it } from 'vitest'
import type { ModelsReport, ModelsRun } from '../../../src/api/types'
import { Models, rolling } from '../../../src/components/pages/Models'
import { Heatmap } from '../../../src/components/viz/Heatmap'
import { ApiFailure, mockApi } from '../../helpers'

const score = (log_loss: number, accuracy = 0.36) => ({
  n: 239, accuracy, log_loss, confusion: [[0, 3, 2, 37], [0, 1, 7, 24], [1, 6, 14, 45], [3, 2, 23, 71]],
})

function run(fs: ModelsRun['feature_set'], over: { chosen?: string; logit?: number; frequency?: number } = {}): ModelsRun {
  return {
    code: 'MNQ', generated: '2026-11-10T18:00:00+00:00', feature_set: fs, sessions_total: 503, sessions_used: 489,
    dropped: { short_session: 9, warmup: 5, roll_jump: 0 },
    regime: {
      logit: score(over.logit ?? 1.44), gbm: score(1.69, 0.34), majority: score(9.9, 0.41),
      yesterday: score(12.1, 0.3), frequency: score(over.frequency ?? 1.31, 0.3),
    },
    chosen: over.chosen ?? 'logit',
    range: { n: 209, both: 0.895, up: 0.947, down: 0.947, mean_width: 1063.4, by_regime: { chop: 0.98, trend_up: 0.76 } },
    sessions: Array.from({ length: 70 }, (_, i) => ({ date: `2026-0${1 + Math.floor(i / 28)}-${String((i % 28) + 1).padStart(2, '0')}`, label: 'chop', hit_both: i % 10 !== 0 })),
    importance: [{ feature: 'kurt', drop: 0.034 }, { feature: 'crest', drop: 0.029 }],
  }
}

export function models(over: { chosen?: string; logit?: number; frequency?: number; since?: string } = {}): ModelsReport {
  return {
    health: run('health'), context: run('context'), both: run('both', over),
    ledger: over.since ? { since: over.since, n: 3, scored: 2, hit_both: 0.5 } : { since: null, n: 0, scored: 0, hit_both: null },
  }
}

it('marks the chosen model and admits when it loses to the frequency baseline', async () => {
  mockApi({ '/models': models({ chosen: 'logit', logit: 1.44, frequency: 1.31 }) })
  render(<Models symbol="MNQ" />)
  expect(await screen.findByText('The regime model does not beat the frequency baseline yet.')).toBeTruthy()
  const regime = screen.getByRole('table', { name: 'Regime models' })
  expect(within(within(regime).getByRole('row', { name: /logit/ })).getByText('chosen')).toBeTruthy()
})

it('says nothing of the sort when the chosen model wins', async () => {
  mockApi({ '/models': models({ logit: 1.2, frequency: 1.31 }) })
  render(<Models symbol="MNQ" />)
  await screen.findByRole('table', { name: 'Regime models' })
  expect(screen.queryByText(/does not beat/)).toBeNull()
})

it('shows live since when the ledger has entries, and the waiting line when it does not', async () => {
  mockApi({ '/models': models({ since: '2026-11-11' }) })
  const { unmount } = render(<Models symbol="MNQ" />)
  expect(await screen.findByText('Live since 2026-11-11')).toBeTruthy()
  expect(screen.getByText('2 of 3 forecasts scored, both bounds held on 50%')).toBeTruthy()
  unmount()
  mockApi({ '/models': models() })
  render(<Models symbol="MNQ" />)
  expect(await screen.findByText('The forward record starts with the first pre-open forecast.')).toBeTruthy()
})

it('heatmap cells are labelled with actual, predicted and count', () => {
  render(<Heatmap labels={['chop', 'normal']} matrix={[[3, 1], [0, 5]]} label="Confusion" />)
  expect(screen.getByLabelText('actual chop, predicted normal: 1')).toBeTruthy()
})

it('says so when this symbol has no models report', async () => {
  mockApi({ '/models': new ApiFailure(404, 'no models report yet') })
  render(<Models symbol="NVDA" />)
  expect(await screen.findByText('No models report for NVDA yet')).toBeTruthy()
})

it('rolling hit rate needs a full window', () => {
  const s = Array.from({ length: 4 }, (_, i) => ({ date: `d${i}`, label: 'chop', hit_both: i !== 1 }))
  expect(rolling(s, 3)).toEqual([{ x: 'd2', y: 2 / 3 }, { x: 'd3', y: 2 / 3 }])
})
