// SPDX-License-Identifier: Apache-2.0

/**
 * Screenshots on demand.
 *
 * QA-04a (Q-08). ⚠ **v1 captures; it does not gate.** No `toHaveScreenshot`, no committed
 * baseline PNGs. Pixel diffing is a *later decision*, not a deferred obligation — the win
 * being bought here is that a human, or a triage agent, can **see** the page a failing run
 * produced. A pixel gate across platforms and font stacks is how an e2e suite becomes
 * noise, and noise is the failure mode this sprint is guarding against.
 *
 * Failure artifacts (a screenshot and a trace on any failed test) are configured in
 * `playwright.config.ts` and need no call here. Use this for the deliberate captures —
 * QA-04b's one-per-route pass, and anything a reviewer will want to look at on a green run.
 */
import type { Page, TestInfo } from "@playwright/test";

/**
 * Capture the page and attach it to the report.
 *
 * The file lands under Playwright's `outputDir` (`test-results/`), which is what CI uploads,
 * *and* is attached to the HTML report so it is visible without unzipping an artifact.
 *
 * @param name file-stem and attachment name — keep it route-shaped (`queue`, `tickets-id`)
 *             so QA-04b's 22 captures sort in a readable order.
 */
export async function captureScreenshot(
  page: Page,
  testInfo: TestInfo,
  name: string,
): Promise<void> {
  const file = testInfo.outputPath(`${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  await testInfo.attach(name, { path: file, contentType: "image/png" });
}
