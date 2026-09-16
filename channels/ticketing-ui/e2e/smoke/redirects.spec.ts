// SPDX-License-Identifier: Apache-2.0

/**
 * The three routes whose correct behaviour is a redirect, not a render (QA-04b).
 *
 * ⚠ **Assert where they land, never what they draw.** QA-04b's own warning: an entry route
 * that renders is usually a bug, so a spec that asserts a render here encodes a bug report as
 * a requirement — the same trap QA-04d is warned about on the webchat.
 *
 * ⭐ **One of the three is not what the ticket predicted, and the difference is the auth mode.**
 * QA-04b says `/auth/callback` *"finds no OAuth params and redirects to `/login?error=…`"*.
 * That is the **Keycloak** build. On the **bypass** build this suite runs against,
 * `AuthProvider` starts `isAuthenticated` `true` unconditionally, so `/auth/callback`'s first
 * effect wins and it lands on `/queue`. Measured 2026-09-06. The same mechanism sends `/login`
 * to `/queue` — which is also what made QA-04a's original readiness check a race, since the
 * bypass button is real but transient.
 *
 * So these assertions describe the **bypass** build, deliberately, and say so. When a Keycloak
 * login smoke test lands in its own job (Q-07), that is where the other branch gets asserted.
 */
import { test, expect } from "../fixtures/officer";
import { captureScreenshot } from "../fixtures/artifacts";
import { expectNoCrash, watchForProblems } from "../fixtures/smoke";
import { OFFICERS } from "../fixtures/seed";

const REDIRECTS = [
  {
    route: "/",
    to: "/queue",
    why: "the root is a server-side `redirect('/queue')` — app/page.tsx",
  },
  {
    route: "/login",
    to: "/queue",
    why: "bypass builds are always authenticated, so app/login/page.tsx:45 bounces immediately",
  },
  {
    route: "/auth/callback",
    to: "/queue",
    why: "bypass: the isAuthenticated effect wins. On Keycloak this would be /login?error=…",
  },
] as const;

for (const r of REDIRECTS) {
  test(`${r.route} redirects to ${r.to}`, async ({ page, asOfficer }, testInfo) => {
    await asOfficer(OFFICERS.siteL1);
    const problems = watchForProblems(page);

    await page.goto(r.route);

    // waitForURL, not a URL assertion after the fact: the redirect is asynchronous on two of
    // the three, and reading page.url() too early is exactly the race QA-04a shipped once.
    await page.waitForURL(`**${r.to}`);
    await expectNoCrash(page, problems, testInfo, slug(r.route));

    await captureScreenshot(page, testInfo, slug(r.route));
  });
}

test("/login/reset-password says a link with no token is unusable", async ({
  page,
  asOfficer,
}) => {
  await asOfficer(OFFICERS.siteL1);
  await page.goto("/login/reset-password");

  // The page's whole job without a token is to say so — a blank form would be worse than
  // an error, because the officer would fill it in and lose the work.
  await expect(
    page.getByText("This reset link is missing a token", { exact: false }),
  ).toBeVisible();
});

function slug(route: string): string {
  return route.replace(/^\//, "").replace(/\//g, "-") || "root";
}
