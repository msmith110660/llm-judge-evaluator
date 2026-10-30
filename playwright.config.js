// @ts-check
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 60_000,
  reporter: [['list']],
  use: {
    headless: true,
    viewport: { width: 1400, height: 1000 },
    // Optional: point at a specific Chromium build (useful in CI images)
    launchOptions: process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
  },
});
