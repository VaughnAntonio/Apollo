import { expect, it } from 'vitest'
import { emptyForm, entryBody, formFrom, patchBody } from '../../../src/components/journal/EntryForm'
import { entry } from '../../fixtures'

const form = (over: Partial<ReturnType<typeof emptyForm>> = {}) => ({
  ...emptyForm('MNQ'),
  opened_at: '2026-11-10T10:00',
  side: 'long' as const,
  entry: '102',
  stop: '99.75',
  target: '105',
  size: '2',
  ...over,
})

it('entryBody sends ET wall-clock time without a zone and drops empty fields', () => {
  const body = entryBody(form({ target: '', tags: 'Gamba, A+ setup, ' }))
  expect(body).toMatchObject({ opened_at: '2026-11-10T10:00:00', symbol: 'MNQ', entry: 102, size: 2, tags: ['Gamba', 'A+ setup'] })
  expect(body).not.toHaveProperty('target')
  expect(body).not.toHaveProperty('notes')
})

it('entryBody refuses numbers that are not numbers', () => {
  expect(() => entryBody(form({ entry: 'abc' }))).toThrow('Entry must be a number')
  expect(() => entryBody(form({ size: '1.5' }))).toThrow('Contracts must be a whole number above 0')
})

it('patchBody sends only what changed, and an exit closes the trade by hand', () => {
  const e = entry({ exit: null, closed_at: null, notes: 'old', tags: ['A'] })
  const f = formFrom(e)
  expect(patchBody({ ...f, notes: 'new' }, e)).toEqual({ notes: 'new' })
  expect(patchBody({ ...f, exit: '104', closed_at: '2026-11-03T12:00' }, e)).toEqual({
    exit: 104,
    closed_at: '2026-11-03T12:00:00',
    exit_reason: 'manual',
    needs_confirm: false,
  })
  expect(patchBody(f, e)).toEqual({})
})

it('clearing a field sends null so the API clears it', () => {
  const e = entry({ target: 105, account: 'APEX 50k', grade: 'A' })
  expect(patchBody({ ...formFrom(e), target: '', account: '', grade: '' }, e)).toEqual({ target: null, account: null, grade: null })
})

it('clearing the exit reopens the trade instead of confirming an auto-close', () => {
  const e = entry({ exit: 99.75, closed_at: '2026-11-03T16:30:00Z', exit_reason: 'stop_auto', needs_confirm: true })
  expect(patchBody({ ...formFrom(e), exit: '', closed_at: '' }, e)).toEqual({
    exit: null,
    closed_at: null,
    exit_reason: null,
    needs_confirm: false,
  })
  // touching only the close time keeps the reason
  expect(patchBody({ ...formFrom(e), closed_at: '2026-11-03T11:45' }, e)).toEqual({ closed_at: '2026-11-03T11:45:00' })
})
