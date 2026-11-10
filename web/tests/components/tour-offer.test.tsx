import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import App from '../../src/App'
import { mockApi } from '../helpers'

vi.mock('../../src/components/Chart', () => ({ Chart: () => <div>chart</div> }))

beforeEach(() => {
  localStorage.clear()
  location.hash = ''
  Element.prototype.scrollIntoView = vi.fn()
  mockApi({ '/journal': [], '/symbols': [] })
})
afterEach(() => {
  localStorage.clear()
  vi.unstubAllEnvs()
})

it('offers the tour once on a first visit, and Start opens it', () => {
  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: 'Start' }))
  expect(screen.getByRole('dialog')).toBeTruthy()
  expect(screen.queryByText('New here? Take the 1-minute tour.')).toBeNull()
})

it('No thanks dismisses it for good', () => {
  const { unmount } = render(<App />)
  fireEvent.click(screen.getByRole('button', { name: 'No thanks' }))
  expect(screen.queryByText('New here? Take the 1-minute tour.')).toBeNull()
  unmount()
  render(<App />)
  expect(screen.queryByText('New here? Take the 1-minute tour.')).toBeNull()
})

it('is never offered on the public snapshot', () => {
  vi.stubEnv('VITE_MODE', 'static')
  render(<App />)
  expect(screen.queryByText('New here? Take the 1-minute tour.')).toBeNull()
})
