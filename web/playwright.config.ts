import process from "node:process";
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 2,
  timeout: 30_000,
  globalTimeout: 8 * 60_000,
  expect: { timeout: 7_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:4174",
    timezoneId: "America/Toronto",
    locale: "en-CA",
    reducedMotion: "reduce",
    serviceWorkers: "block",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium-desktop", use: { ...devices["Desktop Chrome"], channel: "chromium", viewport: { width: 1440, height: 1000 } } },
    { name: "webkit-desktop", use: { ...devices["Desktop Safari"], viewport: { width: 1440, height: 1000 } } },
    { name: "chromium-mobile", use: { ...devices["Pixel 7"], channel: "chromium" } },
    { name: "webkit-mobile", use: { ...devices["iPhone 13"] } },
  ],
  webServer: {
    command: "npm run build && npm exec vite preview -- --host 127.0.0.1 --port 4174 --strictPort",
    url: "http://127.0.0.1:4174",
    reuseExistingServer: false,
    timeout: 90_000,
  },
});
