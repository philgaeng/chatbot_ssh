// SPDX-License-Identifier: Apache-2.0

/**
 * The chat button works from the moment it is on screen (`GRM-107`).
 *
 * ⛔ **Found as a flaky spec, and it was a product bug.** The launcher's click handler was attached
 * only after the first `/introduce` request came back, so for that whole window the button was
 * visible and did nothing. CI caught it on 2026-09-14 in `attachment.spec.ts`: the click landed
 * 60 ms after page load, the reply 40 ms later, and the widget never opened. On a slow rural
 * connection that window is seconds, and a complainant who taps and sees nothing rarely taps again.
 *
 * ⭐ **Deterministic, not lucky.** The introduction is HELD at the network until the assertions have
 * run, so this does not depend on how fast the orchestrator answers — the thing that made the
 * original failure intermittent.
 */
import { test, expect } from "@playwright/test";

import { WEBCHAT_URL } from "../env";

test("the chat opens while the first reply is still on its way — and introduces itself once", async ({ page }) => {
  let introductions = 0;
  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/message", async (route) => {
    if ((route.request().postData() ?? "").includes("/introduce")) {
      introductions += 1;
      await held;
    }
    await route.continue();
  });

  await page.goto(WEBCHAT_URL);
  await expect.poll(() => introductions, { message: "the page never sent its introduction" }).toBe(1);

  // `force`, as in chat.ts: the launcher animates in, and "not stable" is a property of the page.
  await page.getByRole("button", { name: "Open grievance chatbot" }).click({ force: true });

  // ⭐ The regression: the widget must open while the introduction is still unanswered.
  await expect(page.locator("#chat-widget")).toBeVisible();

  // A tap during the first request must not send a second one — the complainant would get the
  // greeting and the language menu twice.
  release();
  await expect(page.getByRole("button", { name: /English/ })).toBeVisible();
  expect(introductions, "the tap sent a second /introduce").toBe(1);
});
