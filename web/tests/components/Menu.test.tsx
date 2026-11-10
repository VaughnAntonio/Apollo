import { act, fireEvent, render, renderHook, screen, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { Menu, useHashPage } from '../../src/components/Menu'

afterEach(() => {
  location.hash = ''
  localStorage.clear()
})

const renderMenu = (over: Partial<Parameters<typeof Menu>[0]> = {}) => {
  const props = { page: 'chart' as const, onNavigate: vi.fn(), onJournal: vi.fn(), onNewEntry: vi.fn(), ...over }
  render(<Menu {...props} />)
  return props
}

it('opens from the burger, lists the six tiles in order, and routes', () => {
  const p = renderMenu()
  fireEvent.click(screen.getByRole('button', { name: 'Open menu' }))
  const dialog = screen.getByRole('dialog', { name: 'Menu' })
  const tiles = within(dialog).getAllByRole('link')
  expect(tiles.map((t) => t.textContent)).toEqual(['01Chart', '02Journal', '03Backtest', '04Models', '05Case study', '06Guide'])
  expect(tiles[0].getAttribute('aria-current')).toBe('page')
  fireEvent.click(within(dialog).getByText('Journal'))
  expect(p.onJournal).toHaveBeenCalled()
  expect(screen.queryByRole('dialog')).toBeNull()
})

it('a page tile navigates, and New journal entry opens the form', () => {
  const p = renderMenu()
  fireEvent.click(screen.getByRole('button', { name: 'Open menu' }))
  fireEvent.click(screen.getByText('Models'))
  expect(p.onNavigate).toHaveBeenCalledWith('models')
  fireEvent.click(screen.getByRole('button', { name: 'Open menu' }))
  fireEvent.click(screen.getByRole('button', { name: /New journal entry/ }))
  expect(p.onNewEntry).toHaveBeenCalled()
})

it('the theme tile switches theme, and Escape closes', () => {
  renderMenu()
  fireEvent.click(screen.getByRole('button', { name: 'Open menu' }))
  fireEvent.click(screen.getByRole('button', { name: 'Dark' }))
  expect(document.documentElement.dataset.theme).toBe('dark')
  expect(screen.getByRole('button', { name: 'Dark' }).getAttribute('aria-pressed')).toBe('true')
  fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
  expect(screen.queryByRole('dialog')).toBeNull()
})

it('reads the page from the hash, and an unknown hash falls back to the chart', () => {
  location.hash = '#/models'
  const { result } = renderHook(() => useHashPage())
  expect(result.current[0]).toBe('models')
  act(() => result.current[1]('backtest'))
  expect(location.hash).toBe('#/backtest')
  expect(result.current[0]).toBe('backtest')
  location.hash = '#/nope'
  const { result: r2 } = renderHook(() => useHashPage())
  expect(r2.current[0]).toBe('chart')
})
