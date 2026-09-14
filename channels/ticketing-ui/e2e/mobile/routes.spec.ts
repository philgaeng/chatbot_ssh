// SPDX-License-Identifier: Apache-2.0

/**
 * Mobile route smoke — the five `/m/*` routes (QA-04b, Q-10: smoke only, no driven flows).
 *
 * ⚠ **This file runs under the `mobile` Playwright project and only there.** `middleware.ts`
 * redirects mobile user-agents to `/m/*`, and `AppShell`'s `ViewportRouteSync` moves a session
 * between the two surfaces when the viewport crosses 767 px — so a desktop browser cannot stay
 * on these routes and a mobile browser cannot stay on the desktop ones. The split is by
 * directory (`playwright.config.ts`: `mobile` matches `**\/mobile\/**`, `desktop` ignores it),
 * which is why these five live apart from `e2e/smoke/` rather than sharing its table.
 *
 * ⭐ **UA-conditional routing is exactly the kind of thing that breaks silently** — nothing in
 * `tsc`, `eslint` or a unit test can see it, and a human only notices on a phone.
 */
import { test, expect } from "../fixtures/officer";
import { captureScreenshot } from "../fixtures/artifacts";
import { expectNoCrash, watchForProblems } from "../fixtures/smoke";
import { GRIEVANCES, OFFICERS, resolveTicketId, type SeededOfficer } from "../fixtures/seed";

interface MobileRoute {
  readonly route: string;
  readonly path: string | (() => Promise<string>);
  readonly as: SeededOfficer;
  readonly expect: string;
}

const ROUTES: MobileRoute[] = [
  { route: "/m/queue",   path: "/m/queue",   as: OFFICERS.siteL1, expect: "Tickets" },
  { route: "/m/tickets", path: "/m/tickets", as: OFFICERS.admin,  expect: "All Tickets" },
  { route: "/m/tasks",   path: "/m/tasks",   as: OFFICERS.siteL1, expect: "My Tasks" },
  {
    route: "/m/tickets/[id]",
    path: async () => `/m/tickets/${await resolveTicketId(GRIEVANCES.dustAtGrc)}`,
    as: OFFICERS.grcChair,
    expect: GRIEVANCES.dustAtGrc,
  },
];

for (const r of ROUTES) {
  test(`${r.route} renders on a phone`, async ({ page, asOfficer }, testInfo) => {
    await asOfficer(r.as);
    const problems = watchForProblems(page);

    const path = typeof r.path === "string" ? r.path : await r.path();
    const response = await page.goto(path);

    expect(response, `no response for ${r.route}`).not.toBeNull();
    expect(response!.status(), `${r.route} served a server error`).toBeLessThan(500);
    await expect(page.getByText(r.expect, { exact: false }).first()).toBeVisible();
    await expectNoCrash(page, problems, testInfo, slug(r.route));

    await captureScreenshot(page, testInfo, slug(r.route));
  });
}

test("/m redirects to the mobile queue", async ({ page, asOfficer }, testInfo) => {
  await asOfficer(OFFICERS.siteL1);
  const problems = watchForProblems(page);

  await page.goto("/m");

  await page.waitForURL("**/m/queue");
  await expectNoCrash(page, problems, testInfo, "m");
});

test("a phone visiting a desktop route is moved to the mobile one", async ({
  page,
  asOfficer,
}) => {
  await asOfficer(OFFICERS.siteL1);

  // The redirect itself, not a page — this is the behaviour `middleware.ts` exists for, and
  // the reason the mobile project exists at all. If it regresses, officers on phones land on
  // a desktop layout and nothing else in the suite would notice.
  await page.goto("/queue");

  await page.waitForURL("**/m/queue");
});

function slug(route: string): string {
  return route.replace(/^\//, "").replace(/[[\]]/g, "").replace(/\//g, "-");
}
