// SPDX-License-Identifier: Apache-2.0

/**
 * GRM-122 — which organization a workflow belongs to, driven in the browser (`ui/08` frame 4).
 *
 * The organization decides which resolution actions a workflow can offer, so:
 *   1. a platform admin cannot create a workflow without choosing one;
 *   2. the editor shows it and moves it.
 *
 * ⚠ **The refused move is NOT driven here, deliberately.** It needs a workflow carrying actions, and
 * the only way to get one without the resolution panel (`GRM-119`) is a clone of a seeded workflow —
 * which copies its steps, and a draft with steps cannot be deleted (`GRM-124`: the DELETE is a 500).
 * The spec would leave a workflow behind on every run. The refusal is pinned at the API level
 * (`tests/ticketing/test_workflow_organization.py`) and was driven in a browser once, 2026-09-15.
 * Add it here once `GRM-119` can put an action on a step-less draft, or `GRM-124` is fixed.
 *
 * ⚠ **Works only with the seeded organizations, on purpose.** A fresh seed has no organization
 * below DOR, and an e2e run must not create one (`GRM-092`: an organization row outlives the test).
 * So the move goes DOR → ADB — two top organizations — which is exactly the "another ministry" case.
 * ⚠ **Never moves a seeded workflow.** It acts on a step-less draft it creates, and deletes it at the
 * end (these are not grievance records).
 */
import type { Page } from "@playwright/test";

import { test, expect, expectIdentitySettled } from "../fixtures/officer";
import { captureScreenshot } from "../fixtures/artifacts";
import { OFFICERS } from "../fixtures/seed";

const DOR = "Department of Roads (DOR)";
const ADB = "Asian Development Bank (ADB)";

async function openWorkflowsTab(page: Page): Promise<void> {
  await page.goto("/settings");
  await expectIdentitySettled(page, OFFICERS.admin);
  await page.getByRole("button", { name: "Workflows", exact: true }).first().click();
  await expect(page.getByRole("button", { name: "+ New workflow" })).toBeVisible();
}

async function workflowIdsNamed(page: Page, names: string[]): Promise<string[]> {
  const res = await page.request.get("/api/v1/workflows");
  if (!res.ok()) return [];
  const { items } = (await res.json()) as { items: { workflow_id: string; display_name: string }[] };
  return items.filter((w) => names.includes(w.display_name)).map((w) => w.workflow_id);
}

test("a new workflow must belong to an organization, and the editor moves it", async (
  { page, asOfficer },
  testInfo,
) => {
  const stamp = Date.now();
  const blank = `E2E belongs-to ${stamp}`;
  await asOfficer(OFFICERS.admin);

  try {
    // ── 1. a platform admin must choose the organization ──────────────────────────────────────
    await openWorkflowsTab(page);
    await page.getByRole("button", { name: "+ New workflow" }).click();
    await page.getByPlaceholder("e.g. KL Road Standard GRM").fill(blank);
    const create = page.getByRole("button", { name: "Create workflow" });
    await expect(create).toBeDisabled();
    await page.getByLabel("Belongs to *").selectOption({ label: DOR });
    await page.getByText("Blank (0 steps)").click();
    await captureScreenshot(page, testInfo, "workflow-new-belongs-to");
    await create.click();

    // ── 2. the editor shows it, and moves it ──────────────────────────────────────────────────
    await expect(page.getByRole("heading", { name: blank })).toBeVisible();
    const belongsTo = page.getByText(/^Belongs to:/);
    await expect(belongsTo).toContainText(DOR);
    await page.getByRole("button", { name: "Change", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByText("Projects using this workflow: none")).toBeVisible();
    await dialog.getByLabel("Belongs to").selectOption({ label: ADB });
    await captureScreenshot(page, testInfo, "workflow-change-organization");
    await dialog.getByRole("button", { name: "Save" }).click();
    await expect(dialog).toHaveCount(0);
    await expect(belongsTo).toContainText(ADB);
  } finally {
    for (const id of await workflowIdsNamed(page, [blank])) {
      await page.request.delete(`/api/v1/workflows/${id}`);
    }
  }
});
