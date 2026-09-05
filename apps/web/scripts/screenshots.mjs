#!/usr/bin/env node
// Capture the demo screenshots for docs/demo/screenshots.
//
// Drives playback with the Next button rather than the timer so each shot lands
// on an exact beat. Needs the dev server running on :3000.
//
//   pnpm dev            # in one terminal
//   pnpm screenshots    # in another

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const here = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(here, "../../../docs/demo/screenshots");
const baseUrl = process.env.BASE_URL ?? "http://localhost:3000";

// [file name, beat to stop on, human description]
const SHOTS = [
  ["01-request", 0, "The request and the authority being delegated"],
  ["02-discovery", 2, "Three sellers and two couriers discovered"],
  ["03-rejection", 3, "The cheapest offer refused on a dietary rule"],
  ["04-plans", 5, "Two plans compared, the cheaper one selected"],
  ["05-replan", 7, "A courier drops out and the agent replans"],
  ["06-x402", 8, "The provider answers with HTTP 402"],
  ["07-settled", 12, "Validated XRPL settlement and pickup tokens"],
  ["08-outcome", 13, "The outcome screen"],
];

fs.mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
// 1x rather than retina: these are committed to the repo, and full-page shots of
// the dashboard run to several megabytes each at 2x for no real legibility gain.
const page = await browser.newPage({
  viewport: { width: 1600, height: 1200 },
  deviceScaleFactor: 1,
});

for (const [name, beat, description] of SHOTS) {
  if (name === "01-request") {
    await page.goto(baseUrl, { waitUntil: "networkidle" });
  } else {
    await page.goto(`${baseUrl}/runs/run_demo_001`, { waitUntil: "networkidle" });
    await page.getByRole("button", { name: "Pause" }).click();

    const progress = page.getByRole("progressbar", { name: "Demo progress" });
    const next = page.getByRole("button", { name: "Next step" });
    for (let guard = 0; guard < 40; guard += 1) {
      const current = Number(await progress.getAttribute("aria-valuenow"));
      if (current >= beat) break;
      await next.click();
    }
    // Let the entrance animation settle before capturing.
    await page.waitForTimeout(450);
  }

  const file = path.join(outDir, `${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  console.log(`${path.basename(file)}  —  ${description}`);
}

await browser.close();
console.log(`\n${SHOTS.length} screenshots -> ${outDir}`);
