import { defineConfig } from '@playwright/test'

/**
 * Real Chrome, real backend, real page. `channel: "chrome"` uses the Google Chrome
 * already installed (the browser the team is told to use), so there is no extra
 * 150 MB browser download in setup or in CI.
 */
export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false, // one backend, one account, and rate limits: run in order
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['list']] : [['list']],
  globalSetup: './global-setup.js',
  globalTeardown: './global-teardown.js',
  use: {
    channel: 'chrome',
    headless: true,
    permissions: [],
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
})
