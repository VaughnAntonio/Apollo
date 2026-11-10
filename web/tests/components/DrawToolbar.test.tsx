import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { expect, it, vi } from 'vitest'
import { DrawToolbar } from '../../src/components/DrawToolbar'
import type { Tool } from '../../src/lib/draw'

function Harness({ selected = false, count = 2, onDelete = () => {}, onClear = () => {} }) {
  const [tool, setTool] = useState<Tool>('cursor')
  return <DrawToolbar tool={tool} onTool={setTool} selected={selected} count={count} onDelete={onDelete} onClear={onClear} />
}

it('names every tool and marks the one in use', () => {
  render(<Harness />)
  for (const name of ['Cursor', 'Trend line', 'Ray', 'Horizontal line', 'Vertical line', 'Rectangle', 'Fibonacci retracement'])
    expect(screen.getByRole('button', { name })).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Cursor' }).getAttribute('aria-pressed')).toBe('true')
  fireEvent.click(screen.getByRole('button', { name: 'Rectangle' }))
  expect(screen.getByRole('button', { name: 'Rectangle' }).getAttribute('aria-pressed')).toBe('true')
  expect(screen.getByRole('button', { name: 'Cursor' }).getAttribute('aria-pressed')).toBe('false')
})

it('deletes only when a drawing is selected', () => {
  const onDelete = vi.fn()
  const { rerender } = render(<Harness onDelete={onDelete} />)
  expect((screen.getByRole('button', { name: 'Delete selected drawing' }) as HTMLButtonElement).disabled).toBe(true)
  rerender(<Harness selected onDelete={onDelete} />)
  fireEvent.click(screen.getByRole('button', { name: 'Delete selected drawing' }))
  expect(onDelete).toHaveBeenCalledOnce()
})

it('asks for a second click before clearing every drawing', () => {
  const onClear = vi.fn()
  render(<Harness onClear={onClear} />)
  fireEvent.click(screen.getByRole('button', { name: 'Remove all drawings' }))
  expect(onClear).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Click again to remove all 2 drawings' }))
  expect(onClear).toHaveBeenCalledOnce()
})
