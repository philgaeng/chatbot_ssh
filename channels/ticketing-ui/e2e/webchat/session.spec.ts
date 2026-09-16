// SPDX-License-Identifier: Apache-2.0

/**
 * HR-07's session item — the one its own tracker says to verify, and the one it warns about
 * (QA-04d).
 *
 * ⚠ **Assert id stability and rotation, NOT intake resumption.** HR-07's deviation row is
 * explicit: the orchestrator's `/introduce` handler (`backend/orchestrator/state_machine.py`)
 * hard-resets the session on **every** page load — *"so refresh always starts a clean
 * session"* — and the webchat sends `/introduce` on every load. So a refresh keeps the id and
 * **restarts the conversation, by design**. A spec asserting the conversation continues would
 * encode a bug report as a requirement, which is the trap this sub-ticket is warned about.
 *
 * What HR-07 change #1 actually bought, and what is asserted here: no fresh `temp_…` id per
 * visit, so no orphaned entries accumulating in the orchestrator's in-memory session dict, a
 * stable socket room, and uploads that stay associated with the right session.
 */
import { test, expect } from "@playwright/test";

import { WEBCHAT_URL } from "../env";
import { captureScreenshot } from "../fixtures/artifacts";
import { openChat, sessionId } from "./chat";

test("the session id is persisted on the first visit and survives a refresh", async ({
  page,
}, testInfo) => {
  await page.goto(WEBCHAT_URL);

  // Persisted at startup, before anyone has typed anything — that is change #1.
  await expect.poll(() => sessionId(page), { message: "no session id was persisted" }).not.toBeNull();
  const first = await sessionId(page);

  await page.reload();
  await expect.poll(() => sessionId(page)).not.toBeNull();

  expect(await sessionId(page), "a refresh must not mint a new session id").toBe(first);
  await captureScreenshot(page, testInfo, "webchat-session-persisted");
});

test("closing the session rotates the id", async ({ page }) => {
  await page.goto(WEBCHAT_URL);
  await openChat(page);
  await expect.poll(() => sessionId(page)).not.toBeNull();
  const before = await sessionId(page);

  await page.getByRole("button", { name: "Close session" }).click({ force: true });

  // Rotation is the other half of the contract: persistence must not mean "stuck forever",
  // or a complainant on a shared device would inherit the previous person's session.
  await expect
    .poll(() => sessionId(page), { message: "the id did not rotate", timeout: 20_000 })
    .not.toBe(before);
});
