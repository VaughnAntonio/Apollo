import { expect, test } from '@playwright/test'
import type { Bar, Sym } from '../src/api/types'
import { TIMEFRAMES } from '../src/lib/chart'

test('the built site ships closed candles for every market and timeframe', async ({ page, request }) => {
  const base = '/Apollo/'
  const symbolsResponse = await request.get(`${base}snapshot/symbols.json`)
  expect(symbolsResponse.ok()).toBe(true)
  const symbols: Sym[] = await symbolsResponse.json()
  expect(symbols.some((symbol) => symbol.kind === 'future')).toBe(true)
  expect(symbols.some((symbol) => symbol.kind === 'stock')).toBe(true)
  for (const { code } of symbols) {
    await Promise.all(TIMEFRAMES.map(async ({ tf }) => {
      const pair = `${code}_${tf}`
      const response = await request.get(`${base}snapshot/bars/${pair}.json`)
      expect(response.ok(), pair).toBe(true)
      const bars: Bar[] = await response.json()
      expect(bars.length, pair).toBeGreaterThan(0)
      expect(bars.every((b, i) =>
        Number.isFinite(b.close_time) && b.close_time! > b.time &&
        (i === 0 || b.time > bars[i - 1].time) &&
        [b.open, b.high, b.low, b.close].every(Number.isFinite),
      ), pair).toBe(true)
    }))
  }

  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.setViewportSize({ width: 320, height: 700 })
  await page.goto(`${base}#/guide`)
  await page.getByRole('button', { name: 'Take the tour' }).click()
  const dialog = page.getByRole('dialog', { name: 'Pick a market' })
  await expect(dialog).toBeVisible()
  const box = await dialog.boundingBox()
  expect(box!.x).toBeGreaterThanOrEqual(0)
  expect(box!.x + box!.width).toBeLessThanOrEqual(320)
  await page.keyboard.press('Tab')
  await expect(dialog.getByRole('button', { name: 'Skip tour' })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: 'Open menu' })).toBeFocused()

  await expect(page.getByRole('toolbar', { name: 'Drawing tools' })).toBeVisible()
  const tools = page.getByRole('toolbar', { name: 'Drawing tools' })
  const trend = tools.getByRole('button', { name: 'Trend line' })
  await trend.click()
  const pane = page.locator('canvas').filter({ visible: true }).first()
  const plot = await pane.boundingBox()
  const x = plot!.x + plot!.width / 2
  const y = plot!.y + plot!.height / 2
  await page.mouse.move(x, y)
  await page.mouse.down()
  await pane.dispatchEvent('pointercancel', { bubbles: true, pointerType: 'mouse' })
  await page.mouse.up()
  await page.mouse.click(x, y)
  await expect(trend).toHaveAttribute('aria-pressed', 'true')
  await page.mouse.click(x + 24, y + 16)
  await expect(tools.getByRole('button', { name: 'Cursor' })).toHaveAttribute('aria-pressed', 'true')

  await page.getByRole('button', { name: /^MNQ/ }).click()
  await page.getByRole('option', { name: /NVDA.*Chart only/ }).click()
  await expect(page.getByRole('button', { name: /^NVDA/ })).toBeVisible()
  await expect(page.getByText(/Latest bar open/)).toBeVisible()

  await page.goto(`${base}#/guide`)
  await page.getByRole('button', { name: 'Start NVDA replay' }).click()
  await expect(page.getByRole('img', { name: 'NVDA 1d replay candles' })).toBeVisible()
  await page.getByRole('button', { name: 'View 5m' }).click()
  await expect(page.getByRole('img', { name: 'NVDA 5m replay candles' })).toBeVisible()
  const slider = page.getByRole('slider', { name: 'Replay time' })
  await expect(slider).toHaveValue('0')
  await page.getByRole('button', { name: 'Next candle' }).click()
  await expect(slider).toHaveValue('1')
  expect(errors).toEqual([])
})
