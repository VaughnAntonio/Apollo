import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { api } from '../../src/api/client'
import { Sheet } from '../../src/components/journal/Sheet'
import { TradeDetail } from '../../src/components/journal/TradeDetail'
import { Skeleton } from '../../src/components/State'
import { TickerPicker } from '../../src/components/TickerPicker'
import { entry } from '../fixtures'
import { fetchMock, mockApi } from '../helpers'

it('shows the first message of a pydantic error list', async () => {
  fetchMock(422, { detail: [{ type: 'greater_than', loc: ['body', 'size'], msg: 'Input should be greater than 0' }] })
  await expect(api.journal.create({ opened_at: 'x', symbol: 'MNQ', side: 'long', size: 0 })).rejects.toMatchObject({
    status: 422,
    message: 'Input should be greater than 0',
  })
})

it('the journal sheet does not poll while it is closed', () => {
  const f = mockApi({ '/journal': [], '/journal/stats': {} })
  render(<Sheet open={false} mode="view" selectedId={null} onOpenChange={() => {}} onChanged={() => {}} />)
  const paths = f.mock.calls.map(([u]) => new URL(String(u)).pathname)
  expect(paths).not.toContain('/journal/stats')
  expect(paths).not.toContain('/journal')
})

it('the loading skeleton only pulses when motion is allowed', () => {
  const { container } = render(<Skeleton rows={1} />)
  const bar = container.querySelector('[aria-busy] > div')!
  expect(bar.className).toContain('motion-safe:animate-pulse')
  expect(bar.className.split(' ')).not.toContain('animate-pulse')
})

it('the ticker search points at the highlighted option', async () => {
  mockApi({
    '/symbols': [
      { code: 'MNQ', name: 'Micro E-mini Nasdaq-100', kind: 'future', model_enabled: true },
      { code: 'MES', name: 'Micro E-mini S&P 500', kind: 'future', model_enabled: true },
    ],
  })
  render(<TickerPicker value="MNQ" onChange={() => {}} />)
  fireEvent.click(await screen.findByRole('button', { name: /MNQ/ }))
  const search = screen.getByRole('combobox', { name: 'Search symbols' })
  expect(search.getAttribute('aria-activedescendant')).toBe('symbol-MNQ')
  fireEvent.keyDown(search, { key: 'ArrowDown' })
  expect(search.getAttribute('aria-activedescendant')).toBe('symbol-MES')
  expect(document.getElementById('symbol-MES')?.getAttribute('aria-selected')).toBe('true')
})

it('the ticker picker shows the error when the API is down', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
  render(<TickerPicker value="MNQ" onChange={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: /MNQ/ }))
  expect(await screen.findByRole('alert')).toBeTruthy()
})

it('the delete confirm takes focus and is named by its question', () => {
  render(<TradeDetail entry={entry({ source: 'manual' })} onEdit={() => {}} onDeleted={() => {}} onChanged={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
  const dialog = screen.getByRole('alertdialog', { name: "Delete this trade? This can't be undone." })
  expect(dialog).toBeTruthy()
  expect(document.activeElement?.textContent).toBe('Yes, delete')
})
