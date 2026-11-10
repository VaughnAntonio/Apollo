import { defineConfig, devices } from '@playwright/test'

// Port 5175 so the smoke test never clashes with a dev server already on 5173. The API is mocked.
export default defineConfig({
  testDir: 'e2e',
  use: { baseURL: 'http://localhost:5175', trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: { command: 'npm run dev -- --port 5175', url: 'http://localhost:5175', reuseExistingServer: false },
})
