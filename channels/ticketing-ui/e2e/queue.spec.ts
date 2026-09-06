// SPDX-License-Identifier: Apache-2.0

/**
 * The canary (QA-04a).
 *
 * **Two tests, deliberately.** This file exists to prove the harness works end to end —
 * that a browser reaches the UI, that a cookie makes it a specific seeded officer, and that
 * the officer it becomes changes what the server returns. Route coverage is QA-04b, driven
 * flows are QA-04c: writing thirty specs against a harness nobody has reviewed is the thing
 * this ticket is shaped to avoid.
 *
 * ⚠ **Nothing here asserts on ticket status.** `GRV-2025-001` is seeded `IN_PROGRESS` and
 * ages into `ESCALATED` under the SLA watchdog — see `fixtures/seed.ts` rule 2.
 */
import { test, expect } from "./fixtures/officer";
import { captureScreenshot } from "./fixtures/artifacts";
import { GRIEVANCES, OFFICERS } from "./fixtures/seed";

test.describe("officer queue — canary", () => {
  test("the GRC chair's Actor tab shows the ticket assigned to them", async (
    { page, asOfficer },
    testInfo,
  ) => {
    await asOfficer(OFFICERS.grcChair);
    await page.goto("/queue");

    // The queue lands on the Actor tab (`useState<Tab>("actor")`), which is the tickets this
    // officer owns the next action on. GRV-2025-001 is seeded as theirs, at L3.
    await expect(page.getByText(GRIEVANCES.dustAtGrc, { exact: true })).toBeVisible();

    await captureScreenshot(page, testInfo, "queue-grc-chair");
  });

  test("a different officer gets a different queue", async ({ page, asOfficer }) => {
    await asOfficer(OFFICERS.siteL1);
    await page.goto("/queue");

    // Assert what this officer *does* see first. Ordering matters: a "not visible"
    // assertion passes trivially against a list that has not finished loading, so it can
    // only be trusted once something on the loaded list has been seen.
    await expect(page.getByText(GRIEVANCES.openAtL1, { exact: true })).toBeVisible();

    // The GRC chair's ticket is not this officer's to act on. If this ever goes green for
    // the wrong reason, it is because the positive assertion above stopped being true —
    // which is why the two live in one test rather than two.
    await expect(page.getByText(GRIEVANCES.dustAtGrc, { exact: true })).toBeHidden();
  });
});
