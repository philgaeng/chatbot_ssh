// SPDX-License-Identifier: Apache-2.0

/**
 * Settings → Projects & packages → a project → Organizations (`GRM-089`) and Staffing (`GRM-090`).
 *
 * ⚠⚠ **NEVER RUN. Written 2026-09-07 against a stack that could not be started** — Docker is not
 * reachable in the authoring environment, so this file has been typechecked and nothing more.
 * **Treat a failure here as "the spec is wrong" until someone has watched it pass once.** It is
 * committed rather than withheld because the alternative — landing UI with no spec at all — is
 * what `GRM-085`'s tab reorder showed the cost of: every existing settings spec selected by name,
 * so nothing would have caught the order changing back.
 *
 * ⚠ **It stops short of actually creating an organization, deliberately** — the same shape as
 * `settings-officers.spec.ts` stopping short of provisioning an account (`GRM-075`). Creating one
 * writes a real row, and `DELETE /organizations/{id}` refuses once anything references it, so a
 * suite that created an organization per run would silently fill the dev database with
 * `E2E Test Org 17`. What is driven is everything up to that line: the affordance exists in both
 * pickers, the modal opens, and cancelling returns to the picker rather than to the button
 * before it. **Logged as `GRM-092`** with what would make the rest drivable.
 */
import { test, expect, expectIdentitySettled } from "../fixtures/officer";
import { captureScreenshot } from "../fixtures/artifacts";
import { OFFICERS } from "../fixtures/seed";
import type { Page } from "@playwright/test";

/**
 * The first project in the list, whichever it is.
 *
 * ⚠ Deliberately not keyed on a project name. A fresh seed and this dev box disagree about what
 * exists (`GRM-081` is the same class of problem for officers), and a spec that pins
 * "South Asia Subregional…" passes on one and fails on the other.
 */
async function openProjectSection(page: Page, section: string): Promise<void> {
  await page.goto("/settings");
  await expectIdentitySettled(page, OFFICERS.admin);
  await page.getByRole("button", { name: "Projects & packages", exact: true }).click();

  const firstProject = page.getByRole("button", { name: /project/i }).first();
  await firstProject.click();

  await page.getByRole("button", { name: section, exact: true }).first().click();
}

test("a project's Organizations pane can create the organization it is about to name", async ({
  page,
  asOfficer,
}, testInfo) => {
  await asOfficer(OFFICERS.admin);
  await openProjectSection(page, "Organizations");

  // Open a picker. The button reads "+ Name the <role>" when empty and "+ Add another" once one
  // is named, and which of the two is showing depends on seed state — so match either.
  await page.getByRole("button", { name: /\+ (Name the|Add another)/ }).first().click();

  const picker = page.getByRole("combobox").first();
  await expect(picker).toBeVisible();

  // The affordance GRM-089 adds. Last in the list, not first: an action at the top of a picker is
  // the one people hit reaching for the first name.
  await expect(
    picker.getByRole("option", { name: /Create a new organization/ }),
  ).toBeAttached();

  await picker.selectOption({ label: "+ Create a new organization…" });
  await expect(page.getByText("New organization", { exact: false })).toBeVisible();

  await captureScreenshot(page, testInfo, "project-orgs-create-modal");

  // Cancel returns to the PICKER, not to the button before it — the admin's place in the flow is
  // what the modal interrupted, and making them re-open it is the papercut this item is about.
  await page.getByRole("button", { name: "×" }).click();
  await expect(page.getByRole("combobox").first()).toBeVisible();
});

test("staffing levels collapse, and an unstaffed one says so in words", async ({
  page,
  asOfficer,
}, testInfo) => {
  await asOfficer(OFFICERS.admin);
  await openProjectSection(page, "Staffing");

  // Each level header is a disclosure button (GRM-090).
  const levelHeaders = page.locator("button[aria-expanded]");
  await expect(levelHeaders.first()).toBeVisible();

  await captureScreenshot(page, testInfo, "project-staffing-collapsed");

  // ⚠ Asserted conditionally on purpose. Whether any level blocks depends on how the stack was
  // seeded and on what previous specs staffed — pinning "2 blockers" would encode this dev box.
  // What IS invariant: a level that reports a blocker is OPEN, and reports it in words.
  const blocking = page.getByText(/Needs (an officer|\d+ officers)/).first();
  if (await blocking.count()) {
    await expect(blocking).toBeVisible();
    const owner = page.getByRole("button", { expanded: true }).first();
    await expect(owner).toBeVisible();
  }

  // The disclosure toggles, whichever state it started in.
  const first = levelHeaders.first();
  const before = await first.getAttribute("aria-expanded");
  await first.click();
  await expect(first).toHaveAttribute("aria-expanded", before === "true" ? "false" : "true");
});
