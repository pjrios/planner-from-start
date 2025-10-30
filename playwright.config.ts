import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60_000,
  expect: {
    timeout: 5_000,
  },
  use: {
    baseURL: 'http://127.0.0.1:8000',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'uvicorn backend.app:app --host 127.0.0.1 --port 8000',
    url: 'http://127.0.0.1:8000/health',
    timeout: 120_000,
    reuseExistingServer: !process.env.CI,
  },
});
