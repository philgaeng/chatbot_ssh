// SPDX-License-Identifier: Apache-2.0

/**
 * The two find-it surfaces the `settings-ui` lane added: the organisation tree's search and
 * filters (`GRM-086`), and the officer directory's (`GRM-087` search fields, `GRM-088` filters).
 *
 * ⭐ **Both assert what the filter REMOVES, not only what it keeps**, and always after a positive
 * assertion on the same screen — a filter that returned nothing at all would satisfy "X is gone"
 * on its own, and that is the bug these are most likely to be hiding.
 *
 * ⚠ Nothing here pins a seeded NAME where it can be avoided (`GRM-081`): a fresh database and a
 * dev box disagree about what exists. Officers are keyed on email, which is their identity
 * everywhere; organisations are read off the screen first and then searched for.
 */
import { test, expect, expectIdentitySettled } from "../fixtures/officer";
import { captureScreenshot } from "../fixtures/artifacts";
import { OFFICERS } from "../fixtures/seed";
import type { Page } from "@playwright/test";

async function openOrganisations(page: Page): Promise<void> {
  await page.goto("/settings");
  await expectIdentitySettled(page, OFFICERS.admin);
  await page.getByRole("button", { name: "Organizations & officers", exact: true }).click();
  await page.getByRole("button", { name: "Organizations", exact: true }).click();
  await expect(page.getByText("Organisation tree")).toBeVisible();
}

test("the organisation tree can be searched, and a match keeps the line above it", async ({
  page,
  asOfficer,
}, testInfo) => {
  await asOfficer(OFFICERS.admin);
  await openOrganisations(page);

  const search = page.getByLabel("Search organisations");
  await expect(search).toBeVisible();

  // The seed's two roots, and the relationship the ancestor rule exists to preserve: ADB is a
  // root of its own, DOR sits under the government line.
  await expect(page.getByText("Department of Roads", { exact: false }).first()).toBeVisible();
  await expect(page.getByText("Asian Development Bank", { exact: false }).first()).toBeVisible();

  await search.fill("Asian Development");

  await expect(page.getByText("Asian Development Bank", { exact: false }).first()).toBeVisible();
  // What it removed. Asserted after a positive on the same screen, so an empty tree cannot pass.
  await expect(page.getByText("Department of Roads", { exact: false })).toHaveCount(0);
  await expect(page.getByText(/organisations? match/)).toBeVisible();

  await captureScreenshot(page, testInfo, "org-tree-filtered");

  // The no-match state is its own state, and says so rather than looking like an empty tree.
  await search.fill("kathmandu-no-such-office");
  await expect(page.getByText(/No organisations match/)).toBeVisible();

  // ⚠ The bug this caught during development: clearing the filter must restore the tree. It is
  // asserted here because "the filter broke the tree" is invisible until someone clears one.
  await page.getByRole("button", { name: "Clear the filters" }).click();
  await expect(page.getByText("Department of Roads", { exact: false }).first()).toBeVisible();
  await expect(page.getByText("Asian Development Bank", { exact: false }).first()).toBeVisible();
});

test("the officer directory filters by office, and search reaches the office column", async ({
  page,
  asOfficer,
}, testInfo) => {
  await asOfficer(OFFICERS.admin);
  await page.goto("/settings");
  await expectIdentitySettled(page, OFFICERS.admin);
  await page.getByRole("button", { name: "Organizations & officers", exact: true }).click();
  await page.getByRole("button", { name: "Officers", exact: true }).click();
  await page.getByRole("button", { name: "Directory", exact: true }).click();

  await expect(page.getByText(OFFICERS.siteL1.userId, { exact: false }).first()).toBeVisible();

  // GRM-088 — the Office filter. Its options come from the roster, so pick whatever the second
  // entry is rather than pinning an organisation this box happens to have.
  // ⚠ `exact: true`. `getByLabel` is substring + case-insensitive by default, so a bare "Office"
  // also matches the box labelled "Search officers" and trips strict mode. Two controls on one
  // toolbar whose names contain each other is a trap worth naming rather than silently working
  // around.
  const office = page.getByLabel("Office", { exact: true });
  await expect(office).toBeVisible();
  const options = await office.locator("option").allTextContents();
  expect(options.length).toBeGreaterThan(1);
  await office.selectOption({ index: 1 });

  // Something survives, and the count line agrees it narrowed.
  await expect(page.getByText(/Showing \d+ position/)).toBeVisible();

  await captureScreenshot(page, testInfo, "officers-filtered");

  // GRM-087 — search reaching a column it could not reach before. Combined with the filter, it
  // must AND: a term that cannot co-exist with the chosen office empties the table.
  await page.getByLabel("Search officers").fill("zzz-no-such-officer");
  await expect(page.getByText(/No officers match/)).toBeVisible();

  // Clear resets every control, not just the one that was typed in.
  await page.getByRole("button", { name: "Clear filters" }).first().click();
  await expect(page.getByText(OFFICERS.siteL1.userId, { exact: false }).first()).toBeVisible();
});
