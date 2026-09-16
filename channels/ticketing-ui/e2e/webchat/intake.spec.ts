// SPDX-License-Identifier: Apache-2.0

/**
 * HR-07's language, SEAH-entry and status-check items (QA-04d).
 *
 * ⭐ **All three are one click deep and cost nothing.** The language choice and the main menu
 * are served by the orchestrator's state machine, not by a model, so none of this hits
 * `MODEL_TRANSLATE` or the classifier — which is the constraint that shaped this sub-ticket
 * (`backend-tests` excludes `@live_llm` because it costs money, and a suite that spends per
 * pull request contradicts that).
 */
import { test, expect, type Page } from "@playwright/test";

import { WEBCHAT_URL } from "../env";
import { captureScreenshot } from "../fixtures/artifacts";
import { englishMenu, openChat } from "./chat";

test("the language switch serves the menu in the language chosen", async ({ page }, testInfo) => {
  await page.goto(WEBCHAT_URL);
  await openChat(page);

  // The greeting is bilingual; the menu that follows is not. That is the observable difference,
  // and asserting the *menu* rather than the greeting is what makes this a test of the switch.
  await page.getByRole("button", { name: /English/ }).click({ force: true });
  await expect(page.getByRole("button", { name: "File a grievance" })).toBeVisible();
  await captureScreenshot(page, testInfo, "webchat-menu-en");

  await page.getByRole("button", { name: "Close session" }).click({ force: true });
  await page.reload();
  await openChat(page);

  await page.getByRole("button", { name: /नेपाली/ }).click({ force: true });
  // Nepali menu — asserted in Nepali, because a menu that answers in English to a Nepali
  // speaker is precisely the regression this item exists to catch.
  await expect(page.getByRole("button", { name: /गुनासो/ }).first()).toBeVisible();
  await captureScreenshot(page, testInfo, "webchat-menu-ne");
});

test("the SEAH route is reachable and swaps in its own close control", async ({
  page,
}, testInfo) => {
  await page.goto(WEBCHAT_URL);
  await englishMenu(page);

  await page.getByRole("button", { name: /sexual exploitation/ }).click({ force: true });

  await expect(page.getByRole("button", { name: "Victim-Survivor" })).toBeVisible();
  await expect(page.getByRole("button", { name: "SEAH focal-point" })).toBeVisible();

  // ⭐ HR-07's "persistent close controls" item, and it is a real behavioural difference:
  // on the SEAH branch "Close session" is replaced by "Close browser tab". Leaving a
  // survivor's session recoverable on a shared device is the risk that motivates it.
  await expect(page.getByRole("button", { name: "Close browser tab" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Close session" })).toBeHidden();

  await captureScreenshot(page, testInfo, "webchat-seah-entry");
});

test("status check offers both ways to find a grievance", async ({ page }, testInfo) => {
  await page.goto(WEBCHAT_URL);
  await englishMenu(page);

  await page.getByRole("button", { name: "Check my status" }).click({ force: true });

  await expect(page.getByRole("button", { name: "Grievance ID" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Phone Number" })).toBeVisible();
  // The composer opens here — a complainant may type the id rather than pick a route.
  await expect(page.locator("#message-input")).toBeEnabled();

  await captureScreenshot(page, testInfo, "webchat-status-check");
});
