import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { expect, it } from 'vitest'
import { Backtest, rBins } from '../../../src/components/pages/Backtest'
import { rec } from '../../fixtures'
import { ApiFailure, mockApi } from '../../helpers'

it('shows the ablation table with every variant and labels it development', async () => {
  mockApi({ '/backtest/summary': [rec('plain', -0.36), rec('both', 0.12)] })
  render(<Backtest symbol="MNQ" />)
  expect(await screen.findByText(/Development backtest, holdout locked from 2026-08-06/)).toBeTruthy()
  const rows = within(screen.getByRole('table', { name: 'Variants' })).getAllByRole('row')
  expect(rows.map((r) => r.textContent)).toEqual(expect.arrayContaining([expect.stringContaining('−0.36R')]))
  expect(rows).toHaveLength(3)
  expect(screen.getByText(/38 backtest runs logged/)).toBeTruthy()
})

it('selecting a variant switches the detail sections to it', async () => {
  mockApi({
    '/backtest/summary': [rec('plain', -0.36), rec('both', 0.12, { monthly: [{ month: '2026-03', n: 1, r: 1, 'net_$': 9 }] })],
  })
  render(<Backtest symbol="MNQ" />)
  fireEvent.click(await screen.findByRole('button', { name: 'both' }))
  expect(within(screen.getByRole('table', { name: 'Monthly' })).getByText('2026-03')).toBeTruthy()
})

it('switches layer with the tabs', async () => {
  const f = mockApi({ '/backtest/summary': [rec('plain', -0.36)] })
  render(<Backtest symbol="MNQ" />)
  await screen.findByRole('table', { name: 'Variants' })
  fireEvent.click(screen.getByRole('tab', { name: '1H-5m' }))
  await waitFor(() =>
    expect(f.mock.calls.map(([u]) => new URL(String(u)).searchParams.get('layer'))).toContain('1H-5m'),
  )
  // the D-1H rows never show under the 1H-5m tab
  expect(screen.queryByRole('table', { name: 'Variants' })).toBeNull()
})

it('says so when this symbol has no backtest', async () => {
  mockApi({ '/backtest/summary': new ApiFailure(404, 'no backtest report yet') })
  render(<Backtest symbol="MES" />)
  expect(await screen.findByText('No backtest for MES yet')).toBeTruthy()
})

it('bins R in half-R steps, losses marked down', () => {
  expect(rBins([-1.04, -0.2, 0.3, 2.1])).toEqual([
    { label: '−1.5', value: 1, tone: 'down' },
    { label: '−1.0', value: 0, tone: 'down' },
    { label: '−0.5', value: 1, tone: 'down' },
    { label: '+0.0', value: 1, tone: 'up' },
    { label: '+0.5', value: 0, tone: 'up' },
    { label: '+1.0', value: 0, tone: 'up' },
    { label: '+1.5', value: 0, tone: 'up' },
    { label: '+2.0', value: 1, tone: 'up' },
  ])
})
