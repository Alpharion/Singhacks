import { expect, test } from "@playwright/test";

/**
 * Walks the demo script end to end (PROJECT_CONTEXT.md section 14).
 *
 * Playback is driven by the Next button rather than the timer, so the test is
 * deterministic and does not depend on wall-clock timing.
 */

const RUN_URL = "/runs/run_demo_001";

async function stepTo(page: import("@playwright/test").Page, target: number) {
  const next = page.getByRole("button", { name: "Next step" });
  const progress = page.getByRole("progressbar", { name: "Demo progress" });
  for (let i = 0; i < target; i += 1) {
    const current = Number(await progress.getAttribute("aria-valuenow"));
    if (current >= target) break;
    await next.click();
  }
}

test("a buyer can state a goal and dispatch the agent", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: /surplus food expires faster/i }),
  ).toBeVisible();

  // The delegated authority is stated before anything is spent.
  await expect(page.getByText("S$360.00 · 120 XRP").first()).toBeVisible();
  await expect(
    page.getByText("Max S$210.00 · 70 XRP in any single transaction"),
  ).toBeVisible();

  await page.getByRole("button", { name: /dispatch buyer agent/i }).click();
  await expect(page).toHaveURL(/\/runs\//);
});

test("the run is honestly labelled as demo data", async ({ page }) => {
  await page.goto(RUN_URL);
  await expect(page.getByText(/demo data — no xrpl settlement/i).first()).toBeVisible();
});

test("the agent's work plays through the full demo script", async ({ page }) => {
  await page.goto(RUN_URL);

  const progress = page.getByRole("progressbar", { name: "Demo progress" });
  await expect(progress).toHaveAttribute("aria-valuemax", "13");

  // Pause the timer so the assertions below are not racing it.
  await page.getByRole("button", { name: "Pause" }).click();

  // 1-2: discovery finds three sellers and two couriers.
  await stepTo(page, 2);
  await expect(page.getByText("Green Oven Bakery").first()).toBeVisible();
  await expect(page.getByText("Central Grill").first()).toBeVisible();
  await expect(page.getByText("Economy Van").first()).toBeVisible();

  // 3: the cheapest offer is refused, with the reason shown.
  // The reason appears twice by design - on the offer row and on the decision
  // card - so this asserts on the first occurrence.
  await stepTo(page, 3);
  await expect(
    page.getByText(/missing required vegetarian dietary tag/i).first(),
  ).toBeVisible();

  // 4-5: two plans are compared and the cheaper one wins.
  await stepTo(page, 5);
  await expect(page.getByText("S$222.00").first()).toBeVisible();
  await expect(page.getByText("S$223.50").first()).toBeVisible();
  await expect(page.getByText("Selected").first()).toBeVisible();

  // 6-7: a provider drops out and the agent replans without a human.
  await stepTo(page, 7);
  await expect(page.getByText(/economy van became unavailable/i)).toBeVisible();
  await expect(page.getByText(/replanning delivery/i)).toBeVisible();

  // 8: the provider answers with HTTP 402.
  await stepTo(page, 8);
  await expect(page.getByText("HTTP 402", { exact: true })).toBeVisible();
  await expect(page.getByText(/payment required/i).first()).toBeVisible();

  // 10-12: settlement returns reservations and a booked courier.
  await stepTo(page, 12);
  await expect(page.getByText(/validated on xrpl/i).first()).toBeVisible();
  await expect(page.getByText(/pickup token/i).first()).toBeVisible();

  // 13: the outcome screen the demo closes on.
  await stepTo(page, 13);
  await expect(
    page.getByRole("heading", { name: /100 vegetarian meals secured/i }),
  ).toBeVisible();
  await expect(page.getByText("Total spent")).toBeVisible();
  await expect(page.getByText("Never spent")).toBeVisible();

  // Three distinct settlements - two sellers and one courier. Each is linked
  // from both the payments panel and the outcome summary, so dedupe by href.
  const hrefs = await page.locator('a[href*="testnet.xrpl.org"]').evaluateAll(
    (links) => [...new Set(links.map((link) => link.getAttribute("href")))],
  );
  expect(hrefs).toHaveLength(3);
});

test("spend never exceeds the delegated budget", async ({ page }) => {
  await page.goto(RUN_URL);
  await page.getByRole("button", { name: "Pause" }).click();
  await stepTo(page, 13);

  // S$222 spent + S$138 unspent = the S$360 authorised.
  await expect(page.getByText("S$222.00").first()).toBeVisible();
  await expect(page.getByText("S$138.00").first()).toBeVisible();
  await expect(page.getByText("of S$360.00 authorised").first()).toBeVisible();
});
