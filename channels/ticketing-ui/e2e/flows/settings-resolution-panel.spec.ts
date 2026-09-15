// SPDX-License-Identifier: Apache-2.0

/**
 * GRM-119 — a workflow's resolution panel, driven in the browser (`ui/08` frames 1–3).
 *
 * On a draft workflow of DOR it creates: the empty state blocks Publish; actions are added from DOR's
 * shared ones, reordered and removed, each change saving at once; at 8 the panel refuses a ninth; the
 * create dialog opens from the search.
 *
 * ⚠ **Creating and editing an action are NOT driven here, deliberately.** An action is never deleted
 * (historical cases cite its code), so every run would add a permanent action to DOR's catalog — shown
 * in every DOR workflow's picker from then on. A local action would also need an organization below
 * DOR, and an e2e run must not create one (`GRM-092`). Both are pinned at the API level
 * (`tests/ticketing/test_resolution_authoring.py`); the dialog is opened, checked, and cancelled.
 *
 * ⚠ **The SEAH panel (one line, no controls) is NOT driven either:** no seeded user can open a SEAH
 * workflow's editor — the Workflows list hides sensitive workflows from anyone who cannot *see* SEAH
 * cases, which includes the platform admin who configures them (`GRM-125`). It is pinned by the API
 * (`is_sensitive`, writes refused) and by `lib/resolution.test.ts`.
 *
 * ⚠ **Never changes a seeded workflow.**
 */
import type { Page } from "@playwright/test";

import { test, expect, expectIdentitySettled } from "../fixtures/officer";
import { captureScreenshot } from "../fixtures/artifacts";
import { OFFICERS } from "../fixtures/seed";

const DOR = "Department of Roads (DOR)";
const PANEL = "What officers can choose when closing a case";

async function openWorkflowsTab(page: Page): Promise<void> {
  await page.goto("/settings");
  await expectIdentitySettled(page, OFFICERS.admin);
  await page.getByRole("button", { name: "Workflows", exact: true }).first().click();
  await expect(page.getByRole("button", { name: "+ New workflow" })).toBeVisible();
}

async function addAction(page: Page, label: string): Promise<void> {
  await page.getByRole("button", { name: "+ Add an action" }).click();
  await page.getByLabel("Add an action").fill(label);
  await page.getByRole("button", { name: label, exact: true }).click();
  await expect(page.getByRole("region", { name: PANEL }).getByText(label, { exact: true })).toBeVisible();
}

test("the resolution panel: empty blocks publish, add, reorder, remove, full at 8", async ({ page, asOfficer }, testInfo) => {
  test.setTimeout(90_000);
  const name = `E2E resolution panel ${Date.now()}`;
  await asOfficer(OFFICERS.admin);

  try {
    await openWorkflowsTab(page);
    await page.getByRole("button", { name: "+ New workflow" }).click();
    await page.getByPlaceholder("e.g. KL Road Standard GRM").fill(name);
    await page.getByLabel("Belongs to *").selectOption({ label: DOR });
    await page.getByText("Blank (0 steps)").click();
    await page.getByRole("button", { name: "Create workflow" }).click();
    await expect(page.getByRole("heading", { name })).toBeVisible();

    // ── empty: Publish waits ─────────────────────────────────────────────────────────────────
    const panel = page.getByRole("region", { name: PANEL });
    await expect(panel.getByText("0 of 8")).toBeVisible();
    await expect(panel.getByText("Add at least one action before publishing.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Publish", exact: true })).toBeDisabled();

    // ── add, reorder, remove — each saves at once ────────────────────────────────────────────
    await addAction(page, "Hazard repaired");
    await addAction(page, "Grievance classified");
    await expect(panel.getByText("2 of 8")).toBeVisible();
    await expect(page.getByRole("button", { name: "Publish", exact: true })).toBeEnabled();
    await panel.getByRole("button", { name: "Move Grievance classified up" }).click();
    await expect(panel.getByRole("button", { name: "Move Grievance classified up" })).toBeDisabled();  // now first

    // DOR's own workflow: a new action would be national, so the dialog asks no "counts as".
    await page.getByRole("button", { name: "+ Add an action" }).click();
    await page.getByLabel("Add an action").fill("E2E never created");
    await page.getByRole("button", { name: "+ Create “E2E never created”" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByLabel("Action")).toHaveValue("E2E never created");
    await expect(dialog.getByLabel("Default text for the officer")).toBeVisible();
    await expect(dialog.getByText("In national reports, count this as")).toHaveCount(0);
    await captureScreenshot(page, testInfo, "resolution-panel-create-dialog");
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(dialog).toHaveCount(0);

    // ── full at 8 ────────────────────────────────────────────────────────────────────────────
    for (const label of ["Complainant demand rejected", "Grievance accepted — other remedy", "Made safe — signs, barriers or traffic control",
                         "Dust or noise controlled", "No hazard found on inspection", "Not on a project road — passed on"]) {
      await addAction(page, label);
    }
    await expect(panel.getByText("8 of 8")).toBeVisible();
    await expect(page.getByRole("button", { name: "+ Add an action" })).toBeDisabled();
    await expect(panel.getByText("A workflow can offer at most 8 actions. Remove one to add another.")).toBeVisible();
    await captureScreenshot(page, testInfo, "resolution-panel-full");

    await panel.getByRole("listitem").filter({ hasText: "Dust or noise controlled" }).getByRole("button", { name: "Remove" }).click();
    await expect(panel.getByText("7 of 8")).toBeVisible();
    await expect(page.getByRole("button", { name: "+ Add an action" })).toBeEnabled();
  } finally {
    const res = await page.request.get("/api/v1/workflows");
    if (res.ok()) {
      const { items } = (await res.json()) as { items: { workflow_id: string; display_name: string }[] };
      for (const w of items.filter((i) => i.display_name === name)) {
        await page.request.delete(`/api/v1/workflows/${w.workflow_id}`);
      }
    }
  }
});
