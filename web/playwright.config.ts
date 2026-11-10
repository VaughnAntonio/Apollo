import { defineConfig, devices } from '@playwright/test'

const publish = process.env.APOLLO_PUBLISH_TEST === '1'

// Port 5175 so the smoke test never clashes with a dev server already on 5173. The API is mocked.
export default defineConfig({
  testDir: 'e2e',
  testMatch: publish ? 'publish.spec.ts' : 'smoke.spec.ts',
  use: { baseURL: 'http://localhost:5175', trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: { command: publish ? 'vite preview --port 5175 --strictPort' : 'npm run dev -- --port 5175', url: publish ? 'http://localhost:5175/Apollo/' : 'http://localhost:5175', reuseExistingServer: false },
})
