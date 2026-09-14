// SPDX-License-Identifier: Apache-2.0

/**
 * Tier-1 driven flows on a ticket (QA-04c): note · escalate · resolve.
 *
 * These are the first specs in the suite that **change state**, and every one of them acts on a
 * ticket it created (`fixtures/ticket.ts`) rather than on a seeded one. Escalating a seeded
 * ticket is irreversible and would quietly rewrite a demo scenario.
 *
 * ⚠ **Escalate and resolve both require an image attachment, enforced on the server** —
 * `ticketing/engine/ticket_actions.py` raises *"At least one image attachment is required
 * before escalating"*, and the UI blocks the form before you can even open it. That is **not**
 * what `CLAUDE.md` says ("warning encouraged but not blocked"); the code has been the stricter
 * one and no live spec records it (`GRM-073`). These specs upload a photo because the system
 * genuinely requires one — **if this ever starts passing without the upload, the requirement
 * was removed and that is the finding.**
 */
import type { Page } from "@playwright/test";

import { test, expect } from "../fixtures/officer";
import { captureScreenshot } from "../fixtures/artifacts";
import { createTicket, getTicket } from "../fixtures/ticket";
import { OFFICERS, type SeededOfficer } from "../fixtures/seed";
import path from "node:path";

/** A real (tiny) PNG — the escalate/resolve gate checks for an *image* attachment. */
const SITE_PHOTO = path.join(__dirname, "..", "fixtures", "site-photo.png");

/** Act as whoever auto-assignment chose; see fixtures/ticket.ts on why this is read, not assumed. */
function asAssignee(userId: string): SeededOfficer {
  return { userId, roleKeys: [], organizationId: "DOR", label: userId };
}

/**
 * Upload the site photo through the compose bar's (hidden) file input, and wait for the thread
 * to confirm it.
 *
 * ⚠ **Wait for the thread bubble specifically, not for the filename.** The name appears twice
 * once the upload lands — once in the thread and once in the Attachments panel — and a bare
 * `getByText` is a strict-mode violation. Waiting for the *thread* entry is also the stronger
 * assertion: the panel can list a file the thread never received.
 */
async function attachSitePhoto(page: Page): Promise<void> {
  await page.locator('input[type="file"]').first().setInputFiles(SITE_PHOTO);
  await expect(page.getByText(`📎 Attached: ${path.basename(SITE_PHOTO)}`)).toBeVisible();
}

test("queue → open the ticket → add an internal note", async ({ page, asOfficer }, testInfo) => {
  const ticket = await createTicket("note");
  await asOfficer(asAssignee(ticket.assignee));

  await page.goto("/queue");
  // The queue is the entry point on purpose: this asserts auto-assignment actually put the
  // ticket in front of the officer, which no API test of the note endpoint would catch.
  await page.getByText(ticket.grievanceId, { exact: true }).click();

  await expect(page.getByRole("heading", { name: ticket.grievanceId })).toBeVisible();

  const note = `Site visit scheduled — e2e ${Date.now()}`;
  await page.getByPlaceholder("Add a note…").fill(note);
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText(note)).toBeVisible();
  await captureScreenshot(page, testInfo, "flow-internal-note");
});

test("acknowledge → attach a photo → escalate", async ({ page, asOfficer }, testInfo) => {
  const ticket = await createTicket("escalate");
  await asOfficer(asAssignee(ticket.assignee));

  await page.goto(`/tickets/${ticket.ticketId}`);

  // A fresh ticket offers only Acknowledge; Escalate and Resolve appear once it is in progress.
  await page.getByRole("button", { name: "Acknowledge", exact: true }).click();
  await expect(page.getByRole("button", { name: "Escalate", exact: true })).toBeVisible();

  // The gate, asserted before it is satisfied — this is the half that would silently stop
  // being true if the server check were removed.
  await page.getByRole("button", { name: "Escalate", exact: true }).click();
  await expect(page.getByText("Add at least one photo before escalating")).toBeVisible();

  await attachSitePhoto(page);

  await page.getByRole("button", { name: "Escalate", exact: true }).click();
  await page.getByPlaceholder("Why is this case being escalated?").fill(
    "Contractor did not act within the SLA. Escalating for PIU review.",
  );
  await page.getByRole("button", { name: "Confirm escalation" }).click();

  // Assert the outcome in the database, not just on the page: the UI could render an
  // optimistic state and the action still have failed.
  await expect
    .poll(async () => (await getTicket(ticket.ticketId)).status_code, {
      message: "the ticket should have escalated",
      timeout: 15_000,
    })
    .toBe("ESCALATED");

  await captureScreenshot(page, testInfo, "flow-escalate");
});

test("acknowledge → attach a photo → resolve", async ({ page, asOfficer }, testInfo) => {
  const ticket = await createTicket("resolve");
  await asOfficer(asAssignee(ticket.assignee));

  await page.goto(`/tickets/${ticket.ticketId}`);
  await page.getByRole("button", { name: "Acknowledge", exact: true }).click();
  await expect(page.getByRole("button", { name: "Resolve", exact: true })).toBeVisible();

  await attachSitePhoto(page);

  await page.getByRole("button", { name: "Resolve", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Resolve case" })).toBeVisible();
  await captureScreenshot(page, testInfo, "flow-resolve-form");

  // The category select is populated from the resolution catalogue, so pick by index rather
  // than by a label this spec would then be pinning.
  const category = page.locator("select").filter({ hasText: /./ }).first();
  await category.selectOption({ index: 1 });
  await page
    .getByRole("textbox")
    .last()
    .fill(
      "Contractor agreed to wet-spray the road surface twice daily and the site team will " +
        "verify at each visit. Complainant informed of the outcome.",
    );

  await page.getByRole("button", { name: "Confirm resolve" }).click();

  await expect
    .poll(async () => (await getTicket(ticket.ticketId)).status_code, {
      message: "the ticket should have resolved",
      timeout: 20_000,
    })
    .toBe("RESOLVED");

  // The closure half of the flow: an officer must be able to reach the closure summary page
  // for a resolved case. ⚠ The summary itself is generated by the LLM builder and is NOT
  // asserted here — that would make the suite pay for a model on every run (see
  // e2e/smoke/closure.spec.ts). What is asserted is that the page opens and offers to build it.
  await page.goto(`/tickets/${ticket.ticketId}/closure`);
  await expect(page.getByText("Case closure summary", { exact: false })).toBeVisible();
  await captureScreenshot(page, testInfo, "flow-resolve-closure");
});

test.describe("the officer sees only their own", () => {
  test("a ticket assigned to someone else is not on my Actor tab", async ({ page, asOfficer }) => {
    const ticket = await createTicket("scoping");

    // Deliberately a different officer from the assignee, chosen from the seeded roster.
    const other =
      ticket.assignee === OFFICERS.grcChair.userId ? OFFICERS.siteL1 : OFFICERS.grcChair;
    await asOfficer(other);

    await page.goto("/queue");
    // Positive first — a "not visible" assertion is worthless against a list still loading.
    await expect(page.getByText("Action Needed")).toBeVisible();
    await expect(page.getByText(ticket.grievanceId, { exact: true })).toBeHidden();
  });
});
