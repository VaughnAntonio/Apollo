import { act, renderHook } from '@testing-library/react'
import { expect, it } from 'vitest'
import { applyTheme, useTheme } from '../../src/lib/theme'

it('auto removes data-theme, light and dark set it, and the choice is stored', () => {
  applyTheme('dark')
  expect(document.documentElement.dataset.theme).toBe('dark')
  applyTheme('auto')
  expect(document.documentElement.dataset.theme).toBeUndefined()
  const { result } = renderHook(() => useTheme())
  act(() => result.current[1]('light'))
  expect(localStorage.getItem('apollo.theme')).toBe('light')
  expect(document.documentElement.dataset.theme).toBe('light')
  expect(result.current[0]).toBe('light')
})

it('ignores a stored value that is not a theme', () => {
  localStorage.setItem('apollo.theme', 'neon')
  const { result } = renderHook(() => useTheme())
  expect(result.current[0]).toBe('auto')
})
