import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "change-password.spec.js",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:5178", trace: "off", screenshot: "off",
    channel: process.env.PASSWORD_TEST_BROWSER_CHANNEL || undefined },
  webServer: process.env.PASSWORD_TEST_EXTERNAL_SERVER ? undefined : {
    command: "npm run dev -- --host 127.0.0.1 --port 5178 --strictPort",
    url: "http://127.0.0.1:5178",
    env: { VITE_API_BASE_URL: "http://127.0.0.1:5178" },
  },
});
