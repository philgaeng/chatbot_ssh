// SPDX-License-Identifier: Apache-2.0

/**
 * HR-07's send-lock item — the one its tracker calls out as *"must be human-verified
 * (behavioral)"*, now driven (QA-04d).
 *
 * `app.js` guards the text path with an `isSending` flag, releases it in the send promise's
 * `.finally()`, and arms a **15 s failsafe** (`SEND_LOCK_TIMEOUT_MS`) so a backend that never
 * answers cannot leave a complainant with a permanently dead composer. Both halves are here:
 * the lock holds, and the failsafe releases it.
 *
 * ⚠ **The dead backend is simulated at the network layer, never by stopping a container.**
 * QA-04d is explicit about this and the reasons are worth keeping: `page.route()` is
 * deterministic, needs no privileges on a CI runner, and — decisively — **it does not take the
 * stack down under whatever else is running.** Stopping `backend` mid-suite would fail every
 * concurrent spec for an unrelated reason, and those failures would read as flake. It also
 * tests the thing the item is actually about (the 15 s release) rather than testing Docker.
 */
import { test, expect } from "@playwright/test";

import { WEBCHAT_URL } from "../env";
import { captureScreenshot } from "../fixtures/artifacts";
import { composerOpen } from "./chat";

/** `SEND_LOCK_TIMEOUT_MS` in `channels/REST_webchat/app.js`. */
const SEND_LOCK_TIMEOUT_MS = 15_000;

test("a double Enter sends one message, not two", async ({ page }, testInfo) => {
  await page.goto(WEBCHAT_URL);

  const sends: string[] = [];
  page.on("request", (req) => {
    if (req.method() === "POST" && req.url().includes("/message")) sends.push(req.url());
  });

  await composerOpen(page);
  const before = sends.length; // the intake has already posted; count only what we cause

  await page.locator("#message-input").fill("GRV-2025-001");
  await page.keyboard.press("Enter");
  await page.keyboard.press("Enter");

  // Wait for the send to land, then confirm nothing followed it. Asserting "exactly one"
  // immediately would pass before a duplicate had a chance to be sent — the same
  // ordering trap as a bare negative assertion.
  await expect.poll(() => sends.length - before).toBe(1);
  await page.waitForTimeout(1_500);
  expect(sends.length - before, "the second Enter must not send a second message").toBe(1);

  await captureScreenshot(page, testInfo, "webchat-send-lock");
});

test("a backend that never answers releases the composer within the failsafe", async ({
  page,
}, testInfo) => {
  test.setTimeout(SEND_LOCK_TIMEOUT_MS + 45_000);

  await page.goto(WEBCHAT_URL);
  await composerOpen(page);

  // From here the orchestrator is a black hole: the request hangs and never resolves, which
  // is the failure mode a dropped connection produces and the one `.finally()` cannot save us
  // from. Routed only *after* the intake, so getting to a typing state is unaffected.
  await page.route("**/message", async () => {
    await new Promise(() => {}); // never settles, never aborts
  });

  // ⚠ **The lock disables the SEND BUTTON, not the textarea** (`beginSendLock`:
  // `sendButton.disabled = true`). The first version of this spec asserted on `#message-input`
  // and failed against working code — a test asserting a mechanism the feature does not use,
  // which is the same class of mistake as testing the wrong method entirely (rule 5.3).
  const sendButton = page.getByRole("button", { name: "Send message" });

  await page.locator("#message-input").fill("hello");
  await page.keyboard.press("Enter");

  // The lock takes hold …
  await expect(sendButton).toBeDisabled();

  // … and the failsafe lets go. Without it a complainant whose network dropped mid-send would
  // have to reload to say anything again — on the channel this whole system exists to serve.
  await expect(sendButton).toBeEnabled({ timeout: SEND_LOCK_TIMEOUT_MS + 20_000 });

  await captureScreenshot(page, testInfo, "webchat-send-lock-failsafe");
});
