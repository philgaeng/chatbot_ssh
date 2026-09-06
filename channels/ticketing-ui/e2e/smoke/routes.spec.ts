// SPDX-License-Identifier: Apache-2.0

/**
 * Route smoke — every desktop `page.tsx` loads, renders, and does not crash (QA-04b).
 *
 * 17 desktop routes here; the 5 `/m/*` routes are in `e2e/mobile/routes.spec.ts`, which runs
 * under the mobile Playwright project because `middleware.ts` redirects mobile user-agents and
 * a desktop browser can never reach that surface. 17 + 5 = the 22 this ticket is counted on.
 *
 * ⭐ **Every route asserts something specific rendered, not just "HTTP 200".** A Next route
 * returns 200 while its client component throws, its data never arrives, or the error boundary
 * takes over — so a status-only smoke suite reports green on a blank page. The `expect` column
 * below is what makes each row a test.
 *
 * ⚠ **Three routes assert a redirect rather than a render**, and one of them is not what QA-04b
 * predicted. See `redirects.spec.ts`.
 */
import { test, expect } from "../fixtures/officer";
import { captureScreenshot } from "../fixtures/artifacts";
import { expectNoCrash, watchForProblems } from "../fixtures/smoke";
import {
  GRIEVANCES,
  OFFICERS,
  createReportShare,
  resolveTicketId,
  type SeededOfficer,
} from "../fixtures/seed";

interface SmokeRoute {
  /** Route as it appears in `app/`, for the test title and the screenshot name. */
  readonly route: string;
  /** A literal path, or a thunk for the parameterised routes that need a seeded id or a made token. */
  readonly path: string | (() => Promise<string>);
  readonly as: SeededOfficer;
  /** Text that proves the page rendered its own content, not an empty shell. */
  readonly expect: string;
  readonly why?: string;
  /**
   * Intercept `api.qrserver.com` and serve a local 1×1 PNG.
   *
   * ⚠ **`/qr-codes` builds every QR image with an `<img src="https://api.qrserver.com/...">`
   * whose query string is the package's full scan URL, intake token included** — so opening
   * the page sends every active token to an unaffiliated third party, once per package
   * (measured 2026-09-06: seven requests on this stack). That is a finding in its own right
   * (`GRM-072`), not something a test should fix.
   *
   * What the stub fixes is the *test*: without it a CI runner with no egress produces seven
   * `net::ERR_CONNECTION_REFUSED` console errors (measured), the run makes seven external
   * requests per PR, and the page's appearance depends on somebody else's uptime. QA-04d's
   * rule applies here too — simulate at the network layer rather than depend on the world.
   */
  readonly stubExternalQrImages?: boolean;
}

/** Smallest valid PNG — enough for an `<img>` to load without reaching the internet. */
const TRANSPARENT_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "base64",
);

const ROUTES: SmokeRoute[] = [
  { route: "/queue",      path: "/queue",      as: OFFICERS.grcChair, expect: "Action Needed" },
  { route: "/tickets",    path: "/tickets",    as: OFFICERS.admin,    expect: "All Tickets" },
  { route: "/escalated",  path: "/escalated",  as: OFFICERS.admin,    expect: "Escalated Tickets" },
  { route: "/reports",    path: "/reports",    as: OFFICERS.admin,    expect: "Reports" },
  {
    route: "/qr-codes",
    path: "/qr-codes",
    as: OFFICERS.admin,
    expect: "QR Codes",
    stubExternalQrImages: true,
    why: "⚠ this page renders its QR images from api.qrserver.com — a third party. See stubExternalQrImages",
  },
  { route: "/account",    path: "/account",    as: OFFICERS.siteL1,   expect: "Account settings" },
  { route: "/help",       path: "/help",       as: OFFICERS.siteL1,   expect: "Officer Guide" },
  {
    route: "/settings",
    path: "/settings",
    as: OFFICERS.admin,
    expect: "Settings",
    why: "admin cookie — a non-admin gets the locked panel, asserted separately below",
  },
  {
    route: "/login/reset-password",
    path: "/login/reset-password",
    as: OFFICERS.admin,
    expect: "Choose a new password",
    why: "a Keycloak flow; with no ?token it must say so rather than crash",
  },
  {
    route: "/tickets/[id]",
    path: async () => `/tickets/${await resolveTicketId(GRIEVANCES.dustAtGrc)}`,
    as: OFFICERS.grcChair,
    expect: GRIEVANCES.dustAtGrc,
  },
  {
    route: "/tickets/[id]/closure",
    path: async () => `/tickets/${await resolveTicketId(GRIEVANCES.resolvedAtL1)}/closure`,
    as: OFFICERS.admin,
    expect: "Case closure summary",
    why: "no summary row exists until the LLM builder runs, so this renders its 'not generated yet' state — from a handled 404/409, which is why smoke.ts separates those from real errors",
  },
  {
    route: "/reports/view/[token]",
    path: async () => `/reports/view/${(await createReportShare()).internalToken}`,
    as: OFFICERS.admin,
    expect: "e2e smoke share",
    why: "a real token — see seed.ts createReportShare, and GRM-071 for why this was not possible before 2026-09-06",
  },
  {
    route: "/reports/public/[token]",
    path: async () => `/reports/public/${(await createReportShare()).publicToken}`,
    as: OFFICERS.admin,
    expect: "e2e smoke share",
  },
];

for (const r of ROUTES) {
  test(`${r.route} renders`, async ({ page, asOfficer }, testInfo) => {
    await asOfficer(r.as);
    if (r.stubExternalQrImages) {
      await page.route("https://api.qrserver.com/**", (route) =>
        route.fulfill({ status: 200, contentType: "image/png", body: TRANSPARENT_PNG }),
      );
    }
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

test("/settings is gated, and the gate renders rather than crashing", async ({
  page,
  asOfficer,
}, testInfo) => {
  await asOfficer(OFFICERS.siteL1);
  const problems = watchForProblems(page);

  await page.goto("/settings");

  // The 22-route count is about pages loading. This one line is about the page loading
  // *differently* for someone who may not administer anything — the same class of check the
  // canary makes for the queue, on the surface where getting it wrong exposes configuration.
  await expect(page.getByText("Settings are only accessible to administrators.")).toBeVisible();
  await expectNoCrash(page, problems, testInfo, "settings-non-admin");

  await captureScreenshot(page, testInfo, "settings-non-admin");
});

function slug(route: string): string {
  return route.replace(/^\//, "").replace(/[[\]]/g, "").replace(/\//g, "-") || "root";
}
