import { defineConfig } from "@playwright/test";

const PORT = 8091;

export default defineConfig({
  testDir: "e2e",
  timeout: 30_000,
  use: {
    baseURL: `http://localhost:${PORT}`,
    viewport: { width: 1360, height: 900 },
    // CI installs Playwright's Chromium; elsewhere a local Chrome can be named.
    launchOptions: process.env.PW_CHROME ? { executablePath: process.env.PW_CHROME } : {},
  },
  webServer: {
    // a simulated quarter run by the hub, served with the built dashboard
    command: `cd .. && python -m imdh.eval.load --url sqlite:///web/e2e.db && IMDH_DATABASE_URL=sqlite:///web/e2e.db IMDH_STATIC_DIR=web/dist PORT=${PORT} python -m imdh.service`,
    url: `http://localhost:${PORT}/api/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 90_000,
  },
  reporter: [["list"]],
});
