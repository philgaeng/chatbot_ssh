// SPDX-License-Identifier: Apache-2.0

/**
 * `/closure/[token]` — the complainant's public case-outcome page (QA-04b).
 *
 * ⚠ **This is the one route of the 22 that cannot be smoked entirely against real data, and
 * the reason is a cost, not a gap in the harness.** The token is
 * `ticketing.ticket_resolved_summaries.closure_public_token`, and no such row exists until a
 * ticket is resolved **and** its closure summary is generated. Generation runs the LLM builder
 * (`ticketing/tasks/llm.py`), and — measured 2026-09-06 — that task **retries rather than
 * degrading** when the model is unavailable (`if not llm_out: raise self.retry(...)`), so the
 * row is never written without a live, paid model call. `backend-tests` deliberately excludes
 * `@live_llm` because *"it costs money"*; a smoke suite that spends on every PR would
 * contradict that outright.
 *
 * QA-04b sanctions the alternative: *"a closure row should be inserted directly (or its
 * summary stubbed)"*. Inserting directly is not available to a Playwright process without
 * giving the suite a database driver and credentials — a coupling worth avoiding for one page.
 * So: **stubbed**, and covered from both ends.
 *
 * | Test | What is real | What it proves |
 * |---|---|---|
 * | invalid token | ⭐ everything — the real API answers 404 | the route, the fetch, the error state, and that a bad link cannot leak |
 * | stubbed payload | the page; the API response is canned | the happy-path render: no crash, and the fields reach the page |
 *
 * ⭐ **What the stub does not prove is stated rather than implied:** it does not check that the
 * API returns this shape. If `summary_public_json` changes, this spec keeps passing. That is
 * the honest cost of not paying for a model per run, and it is recorded in the sprint's
 * `PROGRESS.md` under "Parameterised routes skipped, and why" — it is a **partial**, not a 22nd
 * route quietly counted as whole.
 */
import { test, expect } from "../fixtures/officer";
import { captureScreenshot } from "../fixtures/artifacts";
import { expectNoCrash, watchForProblems } from "../fixtures/smoke";
import { GRIEVANCES, OFFICERS } from "../fixtures/seed";

test("an invalid closure link says so, against the real API", async ({
  page,
  asOfficer,
}, testInfo) => {
  await asOfficer(OFFICERS.siteL1);
  const problems = watchForProblems(page);

  await page.goto("/closure/not-a-real-closure-token");

  await expect(
    page.getByText("This closure link is invalid or not ready yet."),
  ).toBeVisible();
  // The 404 that produces this state is a *handled* resource failure — expectNoCrash records
  // it as an attachment and does not fail on it. See e2e/fixtures/smoke.ts.
  await expectNoCrash(page, problems, testInfo, "closure-invalid");

  await captureScreenshot(page, testInfo, "closure-invalid");
});

test("a closure page renders the outcome it is given", async ({ page, asOfficer }, testInfo) => {
  await asOfficer(OFFICERS.siteL1);
  const problems = watchForProblems(page);

  // Stubbed at the network layer rather than in the database — see this file's header.
  await page.route("**/api/v1/public/closure/*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        grievance_id: GRIEVANCES.dustAtGrc,
        primary_language: "en",
        generated_at: "2026-09-01T00:00:00Z",
        summary_public_json: {
          project_name: "KL Road",
          original_complaint: "Dust from road construction is entering homes.",
          resolution_category_label: "Mitigation agreed",
          resolution_text_public: "The contractor will wet-spray the road twice daily.",
          complaint_filed_at: "2026-08-01T00:00:00Z",
          resolved_at: "2026-09-01T00:00:00Z",
          resolved_duration_days: 31,
        },
      }),
    }),
  );

  await page.goto("/closure/stubbed-token");

  await expect(page.getByText(GRIEVANCES.dustAtGrc, { exact: false })).toBeVisible();
  await expect(page.getByText("KL Road", { exact: false }).first()).toBeVisible();
  await expect(
    page.getByText("The contractor will wet-spray the road twice daily.", { exact: false }),
  ).toBeVisible();
  await expectNoCrash(page, problems, testInfo, "closure-rendered");

  await captureScreenshot(page, testInfo, "closure-rendered");
});
