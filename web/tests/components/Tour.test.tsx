import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { Tour } from '../../src/components/Tour'
import { TOUR_STEPS, markTourDone, shouldOfferTour } from '../../src/lib/tour'

function Targets({ skip = [] as string[] }) {
  return (
    <div>
      {TOUR_STEPS.filter((s) => !skip.includes(s.target)).map((s) => (
        <div key={s.target} data-tour={s.target}>
          {s.target}
        </div>
      ))}
    </div>
  )
}

const scroll = vi.fn()
beforeEach(() => {
  localStorage.clear()
  scroll.mockClear()
  Element.prototype.scrollIntoView = scroll
})
afterEach(() => localStorage.clear())

const title = () => screen.getByRole('dialog').querySelector('h2')!.textContent

it('lists the nine steps in the spec order', () => {
  expect(TOUR_STEPS.map((s) => s.target)).toEqual([
    'ticker', 'timeframes', 'regime', 'range', 'checklist', 'signal', 'take-trade', 'journal', 'model-check',
  ])
})

it('walks the steps in order, skipping a missing target', () => {
  render(
    <>
      <Targets skip={['take-trade']} />
      <Tour open onClose={() => {}} />
    </>,
  )
  expect(screen.getByText('1 of 8')).toBeTruthy()
  for (let i = 0; i < 5; i++) fireEvent.click(screen.getByRole('button', { name: 'Next' }))
  expect(title()).toBe(TOUR_STEPS[5].title) // signal
  fireEvent.click(screen.getByRole('button', { name: 'Next' }))
  expect(title()).toBe(TOUR_STEPS[7].title) // journal; take-trade skipped
  expect(screen.getByText('7 of 8')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Back' }))
  expect(title()).toBe(TOUR_STEPS[5].title)
})

it('the last step finishes the tour', () => {
  const onClose = vi.fn()
  render(
    <>
      <Targets skip={TOUR_STEPS.slice(1).map((s) => s.target)} />
      <Tour open onClose={onClose} />
    </>,
  )
  fireEvent.click(screen.getByRole('button', { name: 'Done' }))
  expect(onClose).toHaveBeenCalled()
  expect(localStorage.getItem('apollo.tour')).toBe('done')
})

it('Escape ends the tour and marks it done', () => {
  const onClose = vi.fn()
  const { rerender } = render(
    <>
      <Targets />
      <Tour open onClose={onClose} />
    </>,
  )
  fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
  expect(onClose).toHaveBeenCalled()
  expect(localStorage.getItem('apollo.tour')).toBe('done')
  rerender(
    <>
      <Targets />
      <Tour open={false} onClose={onClose} />
    </>,
  )
  expect(screen.queryByRole('dialog')).toBeNull()
})

it('Skip tour closes it and focus starts inside the popover', () => {
  const onClose = vi.fn()
  render(
    <>
      <Targets />
      <Tour open onClose={onClose} />
    </>,
  )
  expect(screen.getByRole('dialog').contains(document.activeElement)).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: 'Skip tour' }))
  expect(onClose).toHaveBeenCalled()
})

it('is not offered once dismissed, nor when storage is blocked', () => {
  expect(shouldOfferTour()).toBe(true)
  markTourDone()
  expect(shouldOfferTour()).toBe(false)
  localStorage.clear()
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  expect(shouldOfferTour()).toBe(false)
})

it('scrolls each target into view before placing the spotlight', () => {
  render(
    <>
      <Targets />
      <Tour open onClose={() => {}} />
    </>,
  )
  expect(scroll).toHaveBeenCalledWith({ block: 'center' })
  expect((scroll.mock.contexts[0] as HTMLElement).dataset.tour).toBe('ticker')
})

it('with no targets on screen the tour closes at once', () => {
  const onClose = vi.fn()
  render(<Tour open onClose={onClose} />)
  expect(onClose).toHaveBeenCalled()
  expect(screen.queryByRole('dialog')).toBeNull()
})

it('reaches a target that appears after the tour opens', () => {
  const { rerender } = render(
    <>
      <Targets skip={['regime']} />
      <Tour open onClose={() => {}} />
    </>,
  )
  expect(screen.getByText('1 of 8')).toBeTruthy()
  rerender(
    <>
      <Targets />
      <Tour open onClose={() => {}} />
    </>,
  )
  fireEvent.click(screen.getByRole('button', { name: 'Next' }))
  fireEvent.click(screen.getByRole('button', { name: 'Next' }))
  expect(title()).toBe(TOUR_STEPS[2].title)
  expect(screen.getByText('3 of 9')).toBeTruthy()
})
