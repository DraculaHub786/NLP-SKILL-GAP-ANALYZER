import { defineConfig, devices } from "@playwright/test";

/**
 * E2E smoke test (plan §5.2).
 *
 * `webServer` boots the backend + frontend automatically, reusing already
 * running instances (reuseExistingServer). On this machine the Playwright
 * chromium CDN download is unreliable, so set PLAYWRIGHT_CHANNEL=chrome (or
 * msedge) to run against the installed system browser with zero download:
 *
 *   PLAYWRIGHT_CHANNEL=chrome npx playwright test
 */
const channel = process.env.PLAYWRIGHT_CHANNEL;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  retries: 0,
  reporter: "line",
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        ...(channel ? { channel } : {}),
      },
    },
  ],
  webServer: [
    {
      command: "python -m uvicorn app.main:app --host 127.0.0.1 --port 8080",
      url: "http://127.0.0.1:8080/api/v1/health",
      cwd: "../backend",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: "npm run dev",
      url: "http://localhost:5173",
      cwd: ".",
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
});
