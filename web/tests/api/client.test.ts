import { expect, it, vi } from 'vitest'
import { api, mediaUrl } from '../../src/api/client'
import { fetchMock } from '../helpers'

it("turns a 422 into ApiError with the API's detail", async () => {
  fetchMock(422, { detail: 'there is no trade signal right now' })
  await expect(api.journal.take('MNQ', {})).rejects.toMatchObject({
    status: 422,
    message: 'there is no trade signal right now',
  })
})

it("says how to start the API when it's unreachable", async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
  await expect(api.symbols()).rejects.toMatchObject({
    status: 0,
    message: 'Start the API: python -m apollo.api.main',
  })
})

it('sends bars start as a UTC ISO time and posts JSON', async () => {
  const f = fetchMock(200, [])
  await api.bars('MNQ', '5m', 1_762_000_000)
  const url = new URL(String(f.mock.calls[0][0]))
  expect(url.pathname).toBe('/bars')
  expect(url.searchParams.get('start')).toBe(new Date(1_762_000_000_000).toISOString())
  const g = fetchMock(200, { id: 3 })
  await api.journal.take('MES', { size: 1 })
  const [u, init] = g.mock.calls[0]
  expect(String(u)).toContain('/journal/take?symbol=MES')
  expect(init.method).toBe('POST')
  expect(JSON.parse(init.body)).toEqual({ size: 1 })
})

it('mediaUrl maps a stored path to the media route', () => {
  expect(mediaUrl('journal_media/1-abc.png')).toBe('http://127.0.0.1:8000/media/1-abc.png')
})
