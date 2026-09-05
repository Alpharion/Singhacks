#!/usr/bin/env node
// Prove the live path: dispatch a real run through Person 2's buyer agent and
// assert the dashboard tells the whole story.
//
// This is the P1 half of the integration gate. Unlike `pnpm e2e` (which pins
// fixture mode and needs no backend), this walks the same journey a judge will:
// the browser posts to /api/procure, the agent actually works, and the UI polls
// GET /api/runs/{runId} until the run reaches a terminal state.
//
//   services/buyer-agent $ .venv/bin/python -m uvicorn buyer_agent.main:app --port 8001
//   apps/web            $ pnpm dev
//   apps/web            $ pnpm verify:live
//
// Exits non-zero on the first failed expectation, so it can gate a demo
// rehearsal. Pass --screenshot <path> to also capture the finished dashboard.

import { chromium } from "@playwright/test";

const baseUrl = process.env.BASE_URL ?? "http://localhost:3000";
const screenshotFlag = process.argv.indexOf("--screenshot");
const screenshotPath = screenshotFlag === -1 ? null : process.argv[screenshotFlag + 1];

/**
 * A deadline late enough that the frozen fixture quotes have not expired.
 *
 * The agent's fixture discovery rebases the demo timestamps onto the deadline
 * it parses, so a request whose deadline lands near the fixture's own anchor
 * leaves the courier quotes already expired and the run fails on "no courier
 * can collect". Live marketplace discovery does not have this problem.
 */
const REQUEST =
  "Secure 100 vegetarian meals for our community kitchen, delivered to Queenstown by 11 PM, " +
  "for no more than 120 XRP including delivery.";

/** Every beat the demo script promises to show (PROJECT_CONTEXT.md section 14). */
const EXPECTED = [
  ["the request is parsed into a goal", /goal parsed/i],
  ["offers are discovered", /offers discovered/i],
  ["an unsuitable offer is refused, with the reason", /missing required dietary tag/i],
  ["plans are compared", /ways to fill the order/i],
  ["a plan is selected", /plan selected/i],
  ["a provider asks for payment over x402", /payment required/i],
  ["the agent authorises the payment", /payment authorised/i],
  ["the payment settles", /payment settled/i],
  ["a reservation comes back", /reservation confirmed/i],
  ["delivery is confirmed", /delivery confirmed/i],
  ["the run reaches its outcome", /food rescued/i],
];

const failures = [];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1500, height: 1200 } });

const consoleErrors = [];
page.on("pageerror", (error) => consoleErrors.push(String(error.message)));
page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push(message.text());
});

function check(label, condition) {
  console.log(`${condition ? "  ok  " : "  FAIL"} ${label}`);
  if (!condition) failures.push(label);
}

try {
  await page.goto(baseUrl, { waitUntil: "networkidle" });

  // Fixture-only affordances must be absent, or we are not really testing live.
  check(
    "the fixture badge is gone",
    (await page.getByText(/demo data — no xrpl settlement/i).count()) === 0,
  );

  await page.locator("#requestText").fill(REQUEST);
  await page.getByRole("button", { name: /dispatch buyer agent/i }).click();
  await page.waitForURL(/\/runs\//, { timeout: 30_000 });
  console.log(`  ->   dispatched: ${new URL(page.url()).pathname}`);

  check(
    "the playback clock is gone",
    (await page.getByRole("progressbar", { name: "Demo progress" }).count()) === 0,
  );

  // The agent is genuinely working, and the dashboard then reveals its events
  // on a clock so the run can be followed. Wait for the closing beat rather than
  // for any text that is on the page from the start.
  await page
    .getByText(/food rescued/i)
    .first()
    .waitFor({ state: "visible", timeout: 120_000 });

  for (const [label, pattern] of EXPECTED) {
    check(label, (await page.getByText(pattern).count()) > 0);
  }

  // Honesty: with the agent in simulated payment mode, nothing on the page may
  // claim the ledger validated anything.
  const simulated = (await page.getByText(/simulated settlement/i).count()) > 0;
  if (simulated) {
    console.log("  ->   agent is in simulated payment mode");
    check(
      'no receipt claims "Validated on XRPL"',
      (await page.getByText(/validated on xrpl/i).count()) === 0,
    );
    check(
      "every receipt is labelled simulated",
      (await page.getByText(/simulated — not settled on xrpl/i).count()) > 0,
    );
  } else {
    console.log("  ->   agent settled on XRPL for real");
    check(
      "settled payments are labelled validated",
      (await page.getByText(/validated on xrpl/i).count()) > 0,
    );
  }

  check("the page logged no errors", consoleErrors.length === 0);
  if (consoleErrors.length > 0) console.log("       " + consoleErrors.join("\n       "));

  if (screenshotPath) {
    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log(`  ->   screenshot: ${screenshotPath}`);
  }
} finally {
  await browser.close();
}

if (failures.length > 0) {
  console.error(`\nlive-check: ${failures.length} expectation(s) failed.`);
  process.exit(1);
}
console.log("\nlive-check: the whole journey is visible in the UI.");
