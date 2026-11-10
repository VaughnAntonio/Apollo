import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { Bars } from '../../src/components/viz/Bars'
import { Line } from '../../src/components/viz/Line'

it('Line names each series and its last value for screen readers', () => {
  render(<Line label="Equity" yFormat={(v) => `$${v}`} series={[{ name: 'Strategy', color: 'x', points: [{ x: 'a', y: 1 }, { x: 'b', y: -2 }] }]} />)
  expect(screen.getByRole('img').getAttribute('aria-label')).toBe('Equity. Strategy ends at $-2.')
})

it('Line labels each series at its end and reads values on hover', () => {
  const { container } = render(
    <Line
      label="Equity"
      yFormat={(v) => `$${v}`}
      series={[
        { name: 'Strategy', color: 'x', points: [{ x: '2026-01-01', y: 1 }, { x: '2026-01-03', y: 5 }] },
        { name: 'Buy & hold', color: 'y', dashed: true, points: [{ x: '2026-01-01', y: 0 }, { x: '2026-01-02', y: 3 }, { x: '2026-01-03', y: 4 }] },
      ]}
    />,
  )
  expect(screen.getAllByText('Strategy').length).toBe(1)
  const svg = container.querySelector('svg')!
  svg.getBoundingClientRect = () => ({ left: 0, width: 640, top: 0, height: 220 }) as DOMRect
  fireEvent.pointerMove(svg, { clientX: 320 })
  // the middle day: Strategy carries its last value forward
  expect(screen.getByText('2026-01-02')).toBeTruthy()
  expect(screen.getByText('Strategy $1')).toBeTruthy()
  expect(screen.getByText('Buy & hold $3')).toBeTruthy()
})

it('Bars draws one bar per bin and summarises them', () => {
  const { container } = render(
    <Bars label="R per trade" bins={[{ label: '−1.0', value: 3, tone: 'down' }, { label: '+0.5', value: 1, tone: 'up' }]} />,
  )
  expect(container.querySelectorAll('rect[data-bar]').length).toBe(2)
  expect(screen.getByRole('img').getAttribute('aria-label')).toBe('R per trade. −1.0: 3, +0.5: 1.')
})
