import { defineConfig, devices } from "@playwright/test";

/**
 * One automated pass over the demo path.
 *
 * Pinned to fixture mode. The app now defaults to `live`, but this suite walks
 * the scripted playback beats, so it must drive the fixture clock rather than a
 * running buyer agent - which also keeps it green with no backend.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "pnpm dev",
    url: "http://localhost:3000",
    // Never reuse a server the developer happens to have running: it is
    // probably in live mode, and these specs would fail confusingly.
    reuseExistingServer: false,
    timeout: 120_000,
    env: { NEXT_PUBLIC_DATA_SOURCE: "fixtures" },
  },
});
