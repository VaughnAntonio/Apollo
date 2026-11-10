import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { TickerPicker } from '../../src/components/TickerPicker'
import { mockApi } from '../helpers'

const sym = (code: string, name: string, kind: 'future' | 'stock') => ({ code, name, kind, model_enabled: kind === 'future' })
const SYMBOLS = [
  sym('MNQ', 'Micro E-mini Nasdaq-100', 'future'),
  sym('MES', 'Micro E-mini S&P 500', 'future'),
  sym('NVDA', 'NVIDIA', 'stock'),
]

afterEach(() => localStorage.clear())

it('groups futures and stocks, filters by code or name, and remembers the pick', async () => {
  mockApi({ '/symbols': SYMBOLS })
  const onChange = vi.fn()
  render(<TickerPicker value="MNQ" onChange={onChange} />)
  fireEvent.click(await screen.findByRole('button', { name: /MNQ/ }))
  expect(screen.getByText('Futures')).toBeTruthy()
  expect(screen.getByText('US stocks')).toBeTruthy()
  const search = screen.getByPlaceholderText('Search futures or US stocks')
  fireEvent.change(search, { target: { value: 'nvi' } })
  expect(screen.queryByText('MES')).toBeNull()
  fireEvent.keyDown(search, { key: 'Enter' })
  expect(onChange).toHaveBeenCalledWith('NVDA')
  expect(localStorage.getItem('apollo.symbol')).toBe('NVDA')
})

it('says so when nothing matches', async () => {
  mockApi({ '/symbols': SYMBOLS })
  render(<TickerPicker value="MNQ" onChange={() => {}} />)
  fireEvent.click(await screen.findByRole('button', { name: /MNQ/ }))
  fireEvent.change(screen.getByPlaceholderText('Search futures or US stocks'), { target: { value: 'zzz' } })
  expect(screen.getByText('No symbol matches zzz')).toBeTruthy()
})

it('falls back to MNQ when the stored symbol is no longer configured', async () => {
  mockApi({ '/symbols': SYMBOLS })
  const onChange = vi.fn()
  render(<TickerPicker value="GONE" onChange={onChange} />)
  await vi.waitFor(() => expect(onChange).toHaveBeenCalledWith('MNQ'))
})
