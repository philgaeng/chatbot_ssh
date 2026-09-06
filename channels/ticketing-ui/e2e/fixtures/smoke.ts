// SPDX-License-Identifier: Apache-2.0

/**
 * What "the page is not broken" means, in one place (QA-04b).
 *
 * QA-04's wording is *"assert no 5xx, no uncaught console error, no Next error boundary"*.
 * Turning that into code needs one distinction the phrase hides, and getting it wrong makes
 * the suite either blind or permanently red:
 *
 * **A failed `fetch` the application handles is not a crash.** Chromium logs every non-2xx
 * response as a console error — *"Failed to load resource: the server responded with a status
 * of 404 (Not Found)"* — whether the page ignored it or rendered a careful empty state from
 * it. Measured 2026-09-06, three routes do this **on their correct path**: `/closure/<bad>`
 * and `/reports/view/<bad>` render their "this link is invalid" states from a 404, and
 * `/tickets/<id>/closure` gets a 404 or a 409 depending on whether a summary exists yet, then
 * renders a "generate it" panel. Gating on raw console errors would fail all three for doing
 * exactly what they should.
 *
 * So the gate is:
 *
 *  1. **an uncaught exception** (`pageerror`) — always a defect, never ambiguous;
 *  2. **a console error that is not a resource-load failure** — a real `console.error` from
 *     application code, which is what the ticket means by *uncaught*;
 *  3. **the Next error boundary** — `app/error.tsx` and `app/global-error.tsx` both render
 *     *"Something went wrong"*, and `error.tsx` also `console.error`s, so (1) and (3) overlap
 *     deliberately: whichever fires first names the problem.
 *
 * Handled resource failures are **recorded and attached** rather than dropped, so a route that
 * starts 404ing something new is visible in the report even though it does not fail the run.
 */
import { expect, type Page, type TestInfo } from "@playwright/test";

/** Chromium's wording for a non-2xx subresource; see the header for why these are separated. */
const RESOURCE_FAILURE = /^Failed to load resource:/;

/** Both error boundaries render this heading. */
export const ERROR_BOUNDARY_TEXT = "Something went wrong";

export interface PageProblems {
  /** Uncaught exceptions — always a defect. */
  readonly pageErrors: string[];
  /** `console.error` from application code. */
  readonly consoleErrors: string[];
  /** Non-2xx subresources. Recorded, not gated. */
  readonly handledResourceFailures: string[];
}

/**
 * Start listening. Call **before** `page.goto` — listeners attached afterwards miss
 * everything that happened during the navigation, which is most of what matters.
 */
export function watchForProblems(page: Page): PageProblems {
  const pageErrors: string[] = [];
  const consoleErrors: string[] = [];
  const handledResourceFailures: string[] = [];

  page.on("pageerror", (err) => pageErrors.push(err.stack ?? String(err)));
  page.on("console", (msg) => {
    if (msg.type() !== "error") return;
    const text = msg.text();
    (RESOURCE_FAILURE.test(text) ? handledResourceFailures : consoleErrors).push(text);
  });

  return { pageErrors, consoleErrors, handledResourceFailures };
}

/**
 * Assert the page did not crash, and attach what was seen either way.
 *
 * @param page   the page, to check for the error boundary
 * @param name   route-shaped label, used for the attachment name
 */
export async function expectNoCrash(
  page: Page,
  problems: PageProblems,
  testInfo: TestInfo,
  name: string,
): Promise<void> {
  if (problems.handledResourceFailures.length > 0) {
    await testInfo.attach(`${name}-handled-resource-failures`, {
      body: problems.handledResourceFailures.join("\n"),
      contentType: "text/plain",
    });
  }

  expect(problems.pageErrors, "uncaught exception on the page").toEqual([]);
  expect(problems.consoleErrors, "console.error from application code").toEqual([]);
  await expect(
    page.getByText(ERROR_BOUNDARY_TEXT, { exact: false }),
    "the Next error boundary rendered — the page crashed while rendering",
  ).toBeHidden();
}
