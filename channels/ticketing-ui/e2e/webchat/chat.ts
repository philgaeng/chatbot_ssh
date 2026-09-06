// SPDX-License-Identifier: Apache-2.0

/**
 * Shared moves for the webchat specs (QA-04d).
 *
 * ⚠ **Helpers live here, not in a spec file.** Exporting one from a `*.spec.ts` makes every
 * importing spec pull that file's tests into the run — `npx playwright test webchat/intake`
 * silently executed the session specs too, which is confusing when you are debugging one file.
 */
import { expect, type Page } from "@playwright/test";

/** The webchat persists its session id here — HR-07 change #1. */
export const SESSION_KEY = "rasa_session_id";

export const sessionId = (page: Page): Promise<string | null> =>
  page.evaluate((k) => localStorage.getItem(k), SESSION_KEY);

/**
 * Open the widget.
 *
 * ⚠ `force: true`, deliberately. The launcher animates in and Playwright's actionability check
 * fails it as *"element is not stable"* — a real property of the page, not flake. Waiting the
 * animation out with a sleep would be `waitForTimeout` by another name (rule 6a.5); the
 * assertion that follows is what proves the click landed.
 */
export async function openChat(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Open grievance chatbot" }).click({ force: true });
  await expect(page.getByRole("button", { name: /English/ })).toBeVisible();
}

/** Open the widget and take the English branch — the entry point for every menu test. */
export async function englishMenu(page: Page): Promise<void> {
  await openChat(page);
  await page.getByRole("button", { name: /English/ }).click({ force: true });
  await expect(page.getByRole("button", { name: "Check my status" })).toBeVisible();
}

/**
 * Reach a state where the composer accepts typing.
 *
 * Most of the intake is button-driven — the composer sits disabled with *"Please use the
 * buttons above"* — so a spec about typing has to get somewhere that wants text first. The
 * status-check branch is the cheapest such place: one click, no model, no data.
 */
export async function composerOpen(page: Page): Promise<void> {
  await englishMenu(page);
  await page.getByRole("button", { name: "Check my status" }).click({ force: true });
  await expect(page.locator("#message-input")).toBeEnabled();
}
