// SPDX-License-Identifier: Apache-2.0

/**
 * Settings → Projects & packages → a project → Organizations (`GRM-089`) and Staffing (`GRM-090`).
 *
 * ✅ **Runs, and passes — verified 2026-09-07 against the local stack, 5× clean.**
 *
 * ⚠ **It was written blind first, and both of its selectors were wrong.** Recorded because the
 * failures are the argument for running a spec before trusting it, not against writing one:
 *
 *  1. It opened a project with `getByRole("button", { name: /project/i })`, which matches
 *     **"+ New Project"** first — one assertion away from creating a project per run on a system
 *     with no delete path.
 *  2. It matched rail sections with `exact: true`, but those buttons carry a status hint after
 *     the label ("Staffing" + "Add a Level 1 officer…" + "FIX 2").
 *
 * Neither was visible to tsc, which passed on both.
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
 * Open the first project in the list and select one setup section.
 *
 * ⚠ Deliberately not keyed on a project NAME. A fresh seed and this dev box disagree about what
 * exists (`GRM-081` is the same class of problem for officers), and a spec that pins
 * "Kakarbhitta-Laukahi Road" passes on one and fails on the other.
 *
 * ⚠⚠ **Two things here were wrong when this file was written blind, and both are recorded rather
 * than quietly fixed, because they are the cost of writing a spec you cannot run:**
 *
 *  1. It opened the project with `getByRole("button", { name: /project/i })` — which matches
 *     **"+ New Project"** first. The spec was one assertion away from creating a project per run
 *     on a system with no delete path. A project row is not clickable; it carries an **Edit**
 *     button, and that is what opens the console.
 *  2. It selected the rail section with `exact: true`. Rail buttons carry a status hint after the
 *     label ("Staffing" + "Add a Level 1 officer…" + "FIX 2"), so the accessible name is never
 *     just the label. Matched on the prefix, scoped to the rail, so a stray "Packages" elsewhere
 *     on the page cannot win.
 */
async function openProjectSection(page: Page, section: string): Promise<void> {
  await page.goto("/settings");
  await expectIdentitySettled(page, OFFICERS.admin);
  await page.getByRole("button", { name: "Projects & packages", exact: true }).click();

  await page.getByRole("button", { name: "Edit", exact: true }).first().click();

  const rail = page.getByRole("navigation", { name: "Project setup sections" });
  await expect(rail).toBeVisible();
  await rail.getByRole("button", { name: new RegExp(`^${section}`) }).first().click();
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
  //
  // ⚠ Scoped to the level headers by their own text, NOT a bare `button[aria-expanded]`. The
  // first blind version matched any expandable button on the page — the account menu in the
  // banner has one — so it would have gone green whether or not this feature existed. That is
  // the failure mode a spec written against a stack you cannot open produces: not a red test, a
  // vacuous green one.
  const levelHeaders = page.locator("button[aria-expanded]").filter({ hasText: /^\s*\d+\s*Level/ });
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
  //
  // ⚠ The pane's open/closed state is a function of three async loads. Reading `aria-expanded` the
  // instant a header appeared sampled a value still about to change, and made this spec FLAKY —
  // twice, for two different reasons:
  //
  //  1. 2026-09-07 — a seeding effect raced the admin's own click (fixed in CastStaffing).
  //  2. 2026-09-14 (`GRM-107`) — a level rendered before the ROSTER had loaded, so a slot staffed
  //     through its named role read as empty: "Needs an officer", open, beside a rail saying 0
  //     blockers. This spec read "open", the roster landed and closed it, and the click re-opened
  //     it. The poll this comment used to call the fix waited for the headers to EXIST, which
  //     proves nothing about whether they had settled. The fix is in the component — nothing is
  //     drawn until every load has answered — and is pinned by the spec below.
  await expect.poll(async () => levelHeaders.count(), { timeout: 10_000 }).toBeGreaterThan(0);
  const first = levelHeaders.first();
  await expect(first).toHaveAttribute("aria-expanded", /true|false/);
  const before = await first.getAttribute("aria-expanded");
  await first.click();
  await expect(first).toHaveAttribute("aria-expanded", before === "true" ? "false" : "true");
});

test("a staffing level is not drawn until the officers have loaded, so it cannot claim a false blocker", async ({
  page,
  asOfficer,
}) => {
  // `GRM-107`. With the roster HELD at the network, the steps and the cast answer and the roster does
  // not — the exact window in which a role-staffed slot used to read as empty and open its level on
  // "Needs an officer". Deterministic: nothing here depends on how fast any request is.
  await asOfficer(OFFICERS.admin);
  await page.goto("/settings");
  // The identity switcher reads the roster too, so hold it only after that has settled.
  await expectIdentitySettled(page, OFFICERS.admin);

  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  let rosterHeld = 0;
  await page.route("**/api/v1/users/roster*", async (route) => {
    rosterHeld += 1;
    await held;
    await route.continue();
  });
  // Everything ELSE a level depends on: count it out and back, so "no level drawn" below is asserted
  // after the steps and cast have answered — not vacuously, before they were ever asked for.
  let asked = 0;
  let answered = 0;
  const isLevelData = (url: string) => /\/api\/v1\/workflows\/[^/?]+$|\/cast\?/.test(url);
  page.on("request", (r) => void (isLevelData(r.url()) && (asked += 1)));
  page.on("requestfinished", (r) => void (isLevelData(r.url()) && (answered += 1)));
  page.on("requestfailed", (r) => void (isLevelData(r.url()) && (answered += 1)));

  await page.getByRole("button", { name: "Projects & packages", exact: true }).click();
  await page.getByRole("button", { name: "Edit", exact: true }).first().click();
  const rail = page.getByRole("navigation", { name: "Project setup sections" });
  await rail.getByRole("button", { name: /^Staffing/ }).first().click();

  await expect.poll(() => rosterHeld, { message: "the staffing pane never asked for the roster" }).toBeGreaterThan(0);
  await expect
    .poll(() => asked > 0 && answered === asked, { message: "the steps and cast never finished loading" })
    .toBe(true);

  const levelHeaders = page.locator("button[aria-expanded]").filter({ hasText: /^\s*\d+\s*Level/ });
  await expect(levelHeaders, "a level was drawn before the roster answered").toHaveCount(0);
  await expect(page.getByText(/Needs (an officer|\d+ officers)/)).toHaveCount(0);

  release();
  await expect(levelHeaders.first()).toBeVisible();
});

