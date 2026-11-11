import { defineConfig } from "@playwright/test";
import { fileURLToPath } from "node:url";

export default defineConfig({
  testDir: "./browser",
  outputDir: fileURLToPath(new URL("../../artifacts/report-smoke/results", import.meta.url)),
  timeout: 30_000,
  expect: { timeout: 5_000 },
  workers: 1,
  retries: 0,
  forbidOnly: true,
  reporter: "list",
  use: {
    browserName: "chromium",
    serviceWorkers: "block",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 1000 } } },
    { name: "mobile", use: { viewport: { width: 390, height: 844 } } },
  ],
});
