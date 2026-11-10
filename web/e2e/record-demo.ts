// Records the README demo from the static build. Run by hand, not in CI:
//   VITE_MODE=static VITE_BASE=/Apollo/ npm --prefix web run build
//   npm --prefix web run preview -- --base /Apollo/ --port 5177
//   node web/e2e/record-demo.ts
//   ffmpeg -i <the .webm it prints> -vf "fps=12,scale=960:-1" docs/media/demo.gif
import { chromium } from '@playwright/test'

const BASE = 'http://localhost:5177/Apollo/' // the preview command above
const OUT = decodeURIComponent(new URL('../../.superpowers/demo/', import.meta.url).pathname) // the path has a space

const browser = await chromium.launch()
const context = await browser.newContext({
  viewport: { width: 1280, height: 760 },
  colorScheme: 'dark',
  recordVideo: { dir: OUT, size: { width: 1280, height: 760 } },
})
const page = await context.newPage()
const pause = (ms: number) => page.waitForTimeout(ms)

await page.goto(`${BASE}#/chart`)
await pause(2500)
await page.getByRole('button', { name: /MNQ/ }).click()
await pause(800)
await page.getByRole('combobox', { name: 'Search symbols' }).fill('MES')
await pause(800)
await page.keyboard.press('Enter')
await pause(2000)
await page.getByRole('button', { name: /MES/ }).click()
await page.getByRole('combobox', { name: 'Search symbols' }).fill('MNQ')
await page.keyboard.press('Enter')
await pause(1500)
await page.getByRole('button', { name: 'Open menu' }).click()
await pause(1800)
await page.getByRole('link', { name: /Backtest/ }).click()
await pause(2500)
await page.mouse.wheel(0, 700)
await pause(2000)
await page.getByRole('button', { name: 'Open menu' }).click()
await pause(1500)
await page.getByRole('link', { name: /Models/ }).click()
await pause(2500)
await page.mouse.wheel(0, 900)
await pause(2500)

const video = page.video()
await context.close()
await browser.close()
console.log(await video?.path())
