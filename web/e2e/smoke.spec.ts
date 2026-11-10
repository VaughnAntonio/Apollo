import { expect, test } from '@playwright/test'
import { mockApi } from './fixtures'

test('chart, ticker, timeframe, menu, journal and take trade', async ({ page }) => {
  await mockApi(page)
  await page.goto('/#/chart')
  await expect(page.getByText('Research tool. Not financial advice.')).toBeVisible()
  await expect(page.getByText('Bull C2 at a swing low')).toBeVisible()

  await page.getByRole('button', { name: /MNQ/ }).click()
  await page.getByRole('option', { name: /MES/ }).click()
  await expect(page.getByRole('button', { name: /MES/ })).toBeVisible()
  await page.getByRole('button', { name: /MES/ }).click()
  await page.getByRole('option', { name: /MNQ/ }).click()

  await page.getByRole('button', { name: '1H', exact: true }).click()
  await expect(page.getByRole('button', { name: '1H', exact: true })).toHaveAttribute('aria-current', 'true')

  await page.getByRole('button', { name: 'Open menu' }).click()
  await page.getByRole('link', { name: /Journal/ }).click()
  await expect(page.getByRole('dialog', { name: 'Journal' })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)

  await page.getByRole('button', { name: 'Take trade' }).click()
  await page.getByRole('button', { name: 'Save trade' }).click()
  await expect(page.getByText('Open R')).toBeVisible()
  await expect(page.getByText('Open trade')).toBeVisible()
})

test('API down shows how to start it, then recovers', async ({ page }) => {
  await page.route('http://127.0.0.1:8000/**', (r) => r.abort())
  await page.goto('/#/chart')
  await expect(page.getByText('Start the API: python -m apollo.api.main').first()).toBeVisible()
  await page.unrouteAll({ behavior: 'ignoreErrors' })
  await mockApi(page)
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')))
  await expect(page.getByText('Bull C2 at a swing low')).toBeVisible()
})
