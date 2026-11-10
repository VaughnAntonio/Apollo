import { render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { ErrorBoundary } from '../../src/components/ErrorBoundary'

function Boom(): never {
  throw new Error('Cannot update oldest data')
}

it('shows a message instead of blanking the page when a panel throws', () => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
  render(
    <div>
      <ErrorBoundary label="chart">
        <Boom />
      </ErrorBoundary>
      <p>Still here</p>
    </div>,
  )
  expect(screen.getByRole('alert').textContent).toBe('The chart stopped: Cannot update oldest data. Reload the page.')
  expect(screen.getByText('Still here')).toBeTruthy()
})
