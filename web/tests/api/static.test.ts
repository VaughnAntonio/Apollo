import { afterEach, expect, it, vi } from 'vitest'
import { snapshotUrl, staticApi } from '../../src/api/static'
import { mockFiles } from '../helpers'

const bar = (time: number) => ({ time, open: 1, high: 2, low: 0, close: 1, volume: 1 })

afterEach(() => vi.unstubAllEnvs())

it('builds snapshot URLs under the base path', () => {
  vi.stubEnv('BASE_URL', '/Apollo/')
  expect(snapshotUrl('bars/MNQ_5m.json')).toBe('/Apollo/snapshot/bars/MNQ_5m.json')
})

it('reads bars from the snapshot, filters by start, and treats a missing file as no bars', async () => {
  mockFiles({ '/snapshot/bars/MNQ_5m.json': [bar(100), bar(200), bar(300)] })
  expect((await staticApi.bars('MNQ', '5m', 200)).map((b) => b.time)).toEqual([200, 300])
  expect(await staticApi.bars('MES', '5m')).toEqual([])
})

it('a missing signal or forecast reads as no model', async () => {
  mockFiles({})
  expect((await staticApi.signal('NVDA')).status).toBe('no_model')
  expect((await staticApi.forecast('NVDA')).status).toBe('no_model')
})

it('says the snapshot file is missing rather than asking to start the API', async () => {
  mockFiles({})
  await expect(staticApi.journal.stats()).rejects.toMatchObject({ status: 404, message: 'Build file missing' })
})

it('refuses writes', async () => {
  await expect(staticApi.journal.take('MNQ', {})).rejects.toMatchObject({ status: 405, message: 'This build is read-only' })
  await expect(staticApi.journal.remove(1)).rejects.toMatchObject({ status: 405 })
  await expect(staticApi.journal.autoClose('MNQ')).rejects.toMatchObject({ status: 405 })
})
