import { defineConfig } from '@playwright/test';
const evidence = process.env.E2E_EVIDENCE_DIR || 'test-results';

export default defineConfig({
  testDir: './e2e',
  testIgnore: process.env.E2E_RECOVERY ? [] : ['**/recovery.spec.js'],
  timeout: 60000,
  expect: { timeout: 10000 },
  workers: 1,
  retries: 0,
  outputDir: `${evidence}/artifacts`,
  reporter: [['list'], ['json', { outputFile: process.env.E2E_REPORT || `${evidence}/browser.json` }]],
  use: {
    baseURL: 'http://127.0.0.1:8080',
    browserName: 'chromium',
    viewport: { width: 1440, height: 900 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    launchOptions: { args: ['--disable-background-networking'] },
  },
});
