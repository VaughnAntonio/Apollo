import { act, renderHook } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { ApiError } from '../../src/api/client'
import { usePoll } from '../../src/api/usePoll'
import { setVisibility } from '../helpers'

afterEach(() => {
  vi.useRealTimers()
  setVisibility('visible')
})

it('polls, keeps the last data on error, recovers, and pauses while hidden', async () => {
  vi.useFakeTimers()
  const fn = vi
    .fn()
    .mockResolvedValueOnce(1)
    .mockRejectedValueOnce(new ApiError('down', 0))
    .mockResolvedValue(2)
  const { result } = renderHook(() => usePoll(fn, [], 60_000))
  await act(() => vi.advanceTimersByTimeAsync(0))
  expect(result.current.data).toBe(1)
  await act(() => vi.advanceTimersByTimeAsync(60_000))
  expect(result.current.error?.status).toBe(0)
  expect(result.current.data).toBe(1)
  act(() => setVisibility('hidden'))
  await act(() => vi.advanceTimersByTimeAsync(180_000))
  expect(fn).toHaveBeenCalledTimes(2)
  act(() => setVisibility('visible'))
  await act(() => vi.advanceTimersByTimeAsync(0))
  expect(result.current.data).toBe(2)
  expect(result.current.error).toBeUndefined()
})

it('refetches when its deps change', async () => {
  const fn = vi.fn(async (s: string) => s)
  const { result, rerender } = renderHook(({ s }) => usePoll(() => fn(s), [s]), {
    initialProps: { s: 'MNQ' },
  })
  await vi.waitFor(() => expect(result.current.data).toBe('MNQ'))
  rerender({ s: 'MES' })
  await vi.waitFor(() => expect(result.current.data).toBe('MES'))
})

it('an hourly poll that fails retries every minute until it succeeds', async () => {
  vi.useFakeTimers()
  const fn = vi.fn().mockRejectedValueOnce(new ApiError('down', 0)).mockResolvedValue('ok')
  const { result } = renderHook(() => usePoll(fn, [], 3_600_000))
  await act(() => vi.advanceTimersByTimeAsync(0))
  expect(result.current.error?.status).toBe(0)
  await act(() => vi.advanceTimersByTimeAsync(60_000))
  expect(result.current.data).toBe('ok')
  await act(() => vi.advanceTimersByTimeAsync(600_000))
  expect(fn).toHaveBeenCalledTimes(2) // back on the hourly timer once it works
})
