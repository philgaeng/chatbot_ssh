// SPDX-License-Identifier: Apache-2.0

/**
 * Tier-2 flow (QA-04c): a ticket walked L1 → L2 → L3 and convened at the GRC.
 *
 * ⭐ **This is demo scenario 1, driven.** `mock_tickets.py` *seeds* a ticket already sitting at
 * L3 so the demo can show a convening; nothing until now proved a ticket can actually **get**
 * there. The chain is the product: an escalation that silently fails to reassign leaves a case
 * with nobody acting on it, and no single-action test can see that.
 *
 * It covers three of tier 2's named actions in one pass — ACKNOWLEDGE at each level, ESCALATE
 * twice, and GRC_CONVENE — plus the auto-assignment between them, which is the part with no
 * other coverage at all.
 *
 * ⚠ **Every officer is read from the ticket, never assumed.** Assignment ranks by active load,
 * so which L1 or L2 gets it differs run to run (`fixtures/ticket.ts`). The GRC chair is the one
 * fixed point, because `LEVEL_3_GRC`'s actor is a single seeded officer.
 */
import type { Page } from "@playwright/test";
import path from "node:path";

import { test, expect } from "../fixtures/officer";
import { captureScreenshot } from "../fixtures/artifacts";
import { createTicket, getTicket } from "../fixtures/ticket";
import { OFFICERS, type SeededOfficer } from "../fixtures/seed";

const SITE_PHOTO = path.join(__dirname, "..", "fixtures", "site-photo.png");

function asAssignee(userId: string): SeededOfficer {
  return { userId, roleKeys: [], organizationId: "DOR", label: userId };
}

/** Acknowledge, attach the required photo, and escalate with a reason. */
async function escalateOneLevel(page: Page, ticketId: string, why: string): Promise<void> {
  await page.goto(`/tickets/${ticketId}`);
  await page.getByRole("button", { name: "Acknowledge", exact: true }).click();
  await expect(page.getByRole("button", { name: "Escalate", exact: true })).toBeVisible();

  await page.locator('input[type="file"]').first().setInputFiles(SITE_PHOTO);
  await expect(page.getByText(`📎 Attached: ${path.basename(SITE_PHOTO)}`)).toBeVisible();

  await page.getByRole("button", { name: "Escalate", exact: true }).click();
  await page.getByPlaceholder("Why is this case being escalated?").fill(why);
  await page.getByRole("button", { name: "Confirm escalation" }).click();
}

test("a case walks L1 → L2 → L3 and the GRC chair convenes a hearing", async ({
  page,
  asOfficer,
  context,
}, testInfo) => {
  test.setTimeout(120_000);

  const ticket = await createTicket("grc-chain");

  // ── L1 → L2 ────────────────────────────────────────────────────────────────────────
  await asOfficer(asAssignee(ticket.assignee));
  await escalateOneLevel(page, ticket.ticketId, "No contractor response within the SLA.");

  await expect
    .poll(async () => (await getTicket(ticket.ticketId)).status_code, { timeout: 20_000 })
    .toBe("ESCALATED");

  // ⭐ The assertion with no other coverage: escalation must hand the case to somebody, and to
  // somebody *different*. A chain that escalates without reassigning is a case nobody owns.
  const l2 = (await getTicket(ticket.ticketId)).assigned_to_user_id;
  expect(l2, "escalation must reassign").not.toBe(ticket.assignee);
  expect(l2, "escalation must leave the case assigned").toBeTruthy();

  // ── L2 → L3 ────────────────────────────────────────────────────────────────────────
  await context.clearCookies();
  await asOfficer(asAssignee(l2!));
  await escalateOneLevel(page, ticket.ticketId, "Contractor disputes the findings; referring to GRC.");

  await expect
    .poll(async () => (await getTicket(ticket.ticketId)).assigned_to_user_id, { timeout: 20_000 })
    .not.toBe(l2);

  const l3 = (await getTicket(ticket.ticketId)).assigned_to_user_id;
  expect(l3, "the third level is the GRC chair — a single seeded officer").toBe(
    OFFICERS.grcChair.userId,
  );

  // ── Convene ───────────────────────────────────────────────────────────────────────
  //
  // Not the officer who handed the case on: at the GRC step the control belongs to whoever holds it.
  await page.goto(`/tickets/${ticket.ticketId}`);
  await expect(page.getByRole("heading", { name: ticket.grievanceId })).toBeVisible();
  await expect(page.getByRole("button", { name: "Convene GRC" })).toHaveCount(0);

  // ⭐ The GRC chair convenes — by the cast role `wf:KL_ROAD_STANDARD:LEVEL_3_GRC:actor`. Until
  // `GRM-084` the control also required the legacy `grc_chair` role key, which no officer holds,
  // so only the super admin could convene and this spec had to drive it as the admin.
  await context.clearCookies();
  await asOfficer(OFFICERS.grcChair);
  await page.goto(`/tickets/${ticket.ticketId}`);

  const hearing = page.locator('input[type="date"]').first();
  await expect(hearing).toBeVisible();
  await hearing.fill("2026-10-15");

  await page.getByRole("button", { name: "Convene GRC" }).click();

  await expect(page.getByRole("button", { name: "Convene GRC" })).toBeHidden({ timeout: 20_000 });
  const convened = await getTicket(ticket.ticketId);
  expect(convened.status_code).toBe("GRC_HEARING_SCHEDULED");
  expect(convened.assigned_to_user_id, "convening does not move the case").toBe(OFFICERS.grcChair.userId);
  await captureScreenshot(page, testInfo, "flow-grc-convened");
});
