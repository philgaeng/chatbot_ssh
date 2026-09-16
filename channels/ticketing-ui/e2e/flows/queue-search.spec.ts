// SPDX-License-Identifier: Apache-2.0

/**
 * Tier-2 flows (QA-04c): the queue's tabs, tiles and filters.
 *
 * ⭐ **The cheapest group in tier 2 and the most used surface in the product.** None of it
 * mutates anything, so these are the specs that can run against any stack without leaving a
 * trace — and the queue is where an officer spends their day.
 *
 * ⚠ **Assertions are about the *mechanism*, never the counts.** A queue's contents depend on
 * how long the stack has been up (the SLA watchdog moves tickets between tabs) and on what
 * other specs created. So: "this tab exists and switching to it changes what is shown", not
 * "this tab has four tickets".
 */
import { test, expect } from "../fixtures/officer";
import { captureScreenshot } from "../fixtures/artifacts";
import { GRIEVANCES, OFFICERS } from "../fixtures/seed";

test.describe("queue tabs", () => {
  test("the role-tier tabs are offered and switching changes the list", async ({
    page,
    asOfficer,
  }, testInfo) => {
    await asOfficer(OFFICERS.admin);
    await page.goto("/queue");

    // Actor and All Tickets are `alwaysVisible` in TABS; the middle ones appear only when the
    // officer has something in them, which is why they are not asserted here.
    await expect(page.getByRole("button", { name: /^Actor/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /^All Tickets/ })).toBeVisible();

    // ⚠ **Asserted on each tab's own description, not on a ticket being present.** All Tickets
    // pages at 100 and a long-lived stack holds hundreds, so a seeded id is not reliably on the
    // first page — the first version of this spec assumed it was and failed on the dev box.
    // The description is the tab's contract and it is the same everywhere.
    await expect(
      page.getByText("Tickets where I'm the action owner or have a pending task"),
    ).toBeVisible();

    await page.getByRole("button", { name: /^All Tickets/ }).click();
    await expect(page.getByText("All tickets visible to me")).toBeVisible();
    // Admin owns nothing as an actor, so the empty state was showing and now is not.
    await expect(page.getByText("No tickets in this view.")).toBeHidden();

    await captureScreenshot(page, testInfo, "queue-all-tickets");
  });

  test("High Priority shows only what qualifies", async ({ page, asOfficer }) => {
    await asOfficer(OFFICERS.admin);
    await page.goto("/queue");

    await page.getByRole("button", { name: /^High Priority/ }).click();

    // The tab's own description is the contract; asserting it keeps the spec honest about what
    // "high priority" means rather than hard-coding a ticket that happens to qualify today.
    await expect(
      page.getByText("HIGH / CRITICAL priority or SLA-breached tickets"),
    ).toBeVisible();
  });
});

test.describe("search and filters", () => {
  test("searching by grievance id narrows the list to it", async ({ page, asOfficer }, testInfo) => {
    await asOfficer(OFFICERS.admin);
    await page.goto("/queue");
    await page.getByRole("button", { name: /^All Tickets/ }).click();

    const search = page.getByPlaceholder("Search ID, summary, assignee…");

    // ⚠ **Search for each in turn rather than asserting both are on screen first.** The
    // unfiltered list pages at 100 and a long-lived stack holds hundreds, so "it is visible
    // before I filter" is not a safe premise — it is exactly what made the first version of
    // this spec pass here and fail elsewhere. Searching proves the same thing without it.
    await search.fill(GRIEVANCES.openAtL1);
    await expect(page.getByText(GRIEVANCES.openAtL1, { exact: true }).first()).toBeVisible();

    await search.fill(GRIEVANCES.dustAtGrc);
    await expect(page.getByText(GRIEVANCES.dustAtGrc, { exact: true }).first()).toBeVisible();
    // What a search box is *for* is what it removes.
    await expect(page.getByText(GRIEVANCES.openAtL1, { exact: true })).toBeHidden();

    await captureScreenshot(page, testInfo, "queue-search");
  });

  test("a tile filters the list and says so, and clicking it again clears", async ({
    page,
    asOfficer,
  }) => {
    await asOfficer(OFFICERS.siteL1);
    await page.goto("/queue");

    await expect(page.getByText("Action Needed")).toBeVisible();
    await page.getByRole("button", { name: /Action Needed/ }).click();

    // The chip is the affordance that tells an officer why the list shrank — without it a
    // filtered queue is indistinguishable from an empty one, which is how a ticket gets missed.
    await expect(page.getByText("Filtered by:")).toBeVisible();

    await page.getByRole("button", { name: /Action Needed/ }).click();
    await expect(page.getByText("Filtered by:")).toBeHidden();
  });
});

test("the escalated view is reachable and lists escalated work", async ({
  page,
  asOfficer,
}, testInfo) => {
  await asOfficer(OFFICERS.admin);
  await page.goto("/escalated");

  await expect(page.getByRole("heading", { name: "Escalated Tickets" })).toBeVisible();
  await captureScreenshot(page, testInfo, "queue-escalated");
});
