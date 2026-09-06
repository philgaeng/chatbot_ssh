// SPDX-License-Identifier: Apache-2.0

/**
 * Tier-1 flow (QA-04c): Settings → Organizations & officers.
 *
 * ⚠ **This spec stops short of provisioning an account, deliberately, and the reason is a side
 * effect rather than a difficulty.** `POST` invite calls `keycloak_create_user` whenever
 * `keycloak_admin_url` is set — which it is on the dev stack (measured 2026-09-06) — so every
 * run would create a real Keycloak user and ask the realm to send a set-password email. A test
 * suite that provisions accounts and mails people on each PR is not a test suite. What is
 * driven is everything up to that line: the directory, its search, and the invite form's
 * cascade. **Logged as `GRM-075`**, with what would make it drivable (a stack with no
 * `KEYCLOAK_ADMIN_URL`, or a disposable realm).
 *
 * ⚠ **And the cascade cannot be completed on a freshly seeded database at all** — `GRM-074`.
 * The seed creates two organisations, DOR (`department`) and ADB (`development_partner`), and
 * five position types, every one of them restricted to `directorate`, `provincial_office` or
 * `division_office`. **No seeded organisation has any of those unit types**, so "Pick a
 * position…" has nothing to offer under either. This spec therefore asserts that the position
 * step *unlocks*, never that a particular position exists — pinning one would encode this dev
 * box's leftover `test2` / `Test Position` rows, which no fresh environment has.
 */
import { test, expect } from "../fixtures/officer";
import { captureScreenshot } from "../fixtures/artifacts";
import { OFFICERS } from "../fixtures/seed";

/** Settings is a single page with nested button-driven tabs, not routes. */
async function openOfficerDirectory(page: import("@playwright/test").Page): Promise<void> {
  await page.goto("/settings");
  await page.getByRole("button", { name: "Organizations & officers", exact: true }).click();
  await page.getByRole("button", { name: "Officers", exact: true }).click();
  await page.getByRole("button", { name: "Directory", exact: true }).click();
}

test("the officer directory lists the seeded roster and its search narrows it", async ({
  page,
  asOfficer,
}, testInfo) => {
  await asOfficer(OFFICERS.admin);
  await openOfficerDirectory(page);

  // A seeded officer everyone has — not a count, which drifts with every invite.
  await expect(page.getByText(OFFICERS.grcChair.label, { exact: false }).first()).toBeVisible();
  await expect(page.getByText(OFFICERS.siteL1.label, { exact: false }).first()).toBeVisible();

  await page.getByPlaceholder("Search name, email, or position…").fill(OFFICERS.grcChair.label);

  await expect(page.getByText(OFFICERS.grcChair.label, { exact: false }).first()).toBeVisible();
  // The point of a search box is what it removes. Asserted after a positive, so it cannot
  // pass against a list that simply has not rendered.
  await expect(page.getByText(OFFICERS.siteL1.label, { exact: false })).toBeHidden();

  await captureScreenshot(page, testInfo, "flow-officer-directory-search");
});

test("the invite form unlocks its position step only after an office is chosen", async ({
  page,
  asOfficer,
}, testInfo) => {
  await asOfficer(OFFICERS.admin);
  await page.goto("/settings");
  await page.getByRole("button", { name: "Organizations & officers", exact: true }).click();
  await page.getByRole("button", { name: "Officers", exact: true }).click();
  await page.getByRole("button", { name: "Invite", exact: true }).click();

  // Before an office: the position step is closed and the form says why.
  await expect(page.getByRole("button", { name: "Pick an office first…" })).toBeVisible();
  await expect(page.getByText("Pick an office and a position to continue.")).toBeVisible();

  await page.getByRole("button", { name: "Pick an office (org unit)…" }).click();
  await page.getByRole("button", { name: /Department of Roads \(DOR\)/ }).first().click();

  // After an office: the position step opens. ⚠ What it *contains* is not asserted — see the
  // file header: on a fresh seed it is empty, and that is GRM-074, not a test failure.
  await expect(page.getByRole("button", { name: "Pick a position…" })).toBeVisible();

  await captureScreenshot(page, testInfo, "flow-officer-invite-cascade");
});

test("a non-admin cannot reach settings at all", async ({ page, asOfficer }) => {
  await asOfficer(OFFICERS.siteL1);
  await page.goto("/settings");

  await expect(page.getByText("Settings are only accessible to administrators.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Organizations & officers" })).toBeHidden();
});
