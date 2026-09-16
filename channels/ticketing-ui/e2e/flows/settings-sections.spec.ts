// SPDX-License-Identifier: Apache-2.0

/**
 * Tier-2 flows (QA-04c): every settings section opens and renders its own content.
 *
 * ⚠ **The tier-2 list named sections that are not what the app has.** It said "officers
 * (`officers-v2`), roles, workflows, projects & packages, org, platform, project types,
 * quarterly-report schedule, go-live panel" — a list of *component directories*. The UI groups
 * them into four top tabs with sub-tabs inside, and the ticket told us to verify against the
 * tree before starting, so this is what renders (measured 2026-09-07):
 *
 *   Organizations & officers  → Organizations · Officers (Directory / Invite) · Org tree · Position types
 *   Workflows                 → Workflows · Project types
 *   Projects & packages       → the project list
 *   Settings                  → Locations · Quarterly reports · Advanced (JSON) · Admin access
 *
 * ⚠ **These are deliberately shallow.** Each asserts a section opens and shows content that
 * only it shows — which is what catches an admin surface crashing or rendering empty. Driving
 * each one's *edits* is a much larger job, and several are one-way (creating a project, a
 * workflow, an org) on a system with no delete path. Where an edit is worth driving it gets its
 * own spec, as the officer directory does in `settings-officers.spec.ts`.
 */
import { test, expect, expectIdentitySettled } from "../fixtures/officer";
import { captureScreenshot } from "../fixtures/artifacts";
import { OFFICERS } from "../fixtures/seed";
import type { Page } from "@playwright/test";

async function openSettings(page: Page, tab: string): Promise<void> {
  await page.goto("/settings");
  await expectIdentitySettled(page);
  await page.getByRole("button", { name: tab, exact: true }).first().click();
}

/**
 * ⚠ **The sub-tabs are not all the same ARIA role, so the spec has to say which.** Organizations,
 * Officers, Workflows and Project types are `role="button"`; Org tree and Position types — the
 * second strip, inside Organizations & officers — are `role="tab"`. Same visual affordance,
 * different roles, which matters to anything navigating by role including a screen reader.
 * Recorded here rather than papered over with a text selector, so the inconsistency stays visible.
 */
const SECTIONS: { tab: string; sub?: string; subRole?: "tab"; shows: string; shot: string }[] = [
  { tab: "Organizations & officers", sub: "Organizations", shows: "Organisation tree", shot: "settings-orgs" },
  { tab: "Organizations & officers", sub: "Position types", subRole: "tab", shows: "Position", shot: "settings-position-types" },
  { tab: "Workflows", sub: "Workflows", shows: "Templates", shot: "settings-workflows" },
  { tab: "Workflows", sub: "Project types", shows: "type", shot: "settings-project-types" },
  { tab: "Projects & packages", shows: "New Project", shot: "settings-projects" },
  { tab: "Settings", sub: "Locations", shows: "Browse location tree", shot: "settings-locations" },
  { tab: "Settings", sub: "Quarterly reports", shows: "uarterly", shot: "settings-quarterly" },
  { tab: "Settings", sub: "Advanced (JSON)", shows: "JSON", shot: "settings-advanced" },
  { tab: "Settings", sub: "Admin access", shows: "dmin", shot: "settings-admin-access" },
];

/**
 * The strip's ORDER, pinned (GRM-085).
 *
 * ⚠ Every other spec here selects a tab by accessible name, which is why the 2026-09-07 reorder
 * broke none of them — and is also why nothing would have noticed the order changing back. Once
 * an order is a decision it needs one assertion that fails when it moves; without this, the only
 * record of it is a comment.
 *
 * Read with `page.tsx`: the order is outcome-first (Projects leads because it is what the admin
 * came to do, and because `activeMain` already defaults to it), deliberately the reverse of the
 * dependency order. Asserted for `admin`, who sees all four; `mainTabs` filters by role and
 * `.filter()` preserves order, so every other role gets a subsequence of this.
 */
test("settings: the main tabs are in outcome-first order", async ({ page, asOfficer }) => {
  await asOfficer(OFFICERS.admin);
  await page.goto("/settings");
  await expectIdentitySettled(page);

  const strip = page.getByTestId("settings-main-tabs");
  await expect(strip).toBeVisible();
  await expect(strip.getByRole("button")).toHaveText([
    "Projects & packages",
    "Organizations & officers",
    "Workflows",
    "Settings",
  ]);
});

for (const section of SECTIONS) {
  const name = section.sub ? `${section.tab} → ${section.sub}` : section.tab;
  test(`settings: ${name} opens and renders`, async ({ page, asOfficer }, testInfo) => {
    await asOfficer(OFFICERS.admin);
    await openSettings(page, section.tab);

    if (section.sub) {
      await page.getByRole(section.subRole ?? "button", { name: section.sub, exact: true }).first().click();
    }

    await expect(page.getByText(section.shows, { exact: false }).first()).toBeVisible();
    // The error boundary would also "render", so exclude it explicitly — a crashed admin
    // section is exactly the failure these shallow specs exist to catch.
    await expect(page.getByText("Something went wrong")).toBeHidden();

    await captureScreenshot(page, testInfo, section.shot);
  });
}
