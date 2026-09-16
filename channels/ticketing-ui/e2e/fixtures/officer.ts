// SPDX-License-Identifier: Apache-2.0

/**
 * Identity for the suite — *be* a seeded officer, without Keycloak.
 *
 * QA-04a (Q-07). A bypass build reads a `grm_bypass_user` cookie and the Next proxy turns it
 * into `X-Internal-*` headers (`app/api/v1/[...path]/route.ts`), so setting one cookie makes
 * the whole session that officer. No Keycloak container, no OIDC redirect, no login form —
 * which is what removes the single heaviest service from the CI stack.
 *
 * **Import `test` and `expect` from here, not from `@playwright/test`.** The `asOfficer`
 * fixture only exists on this extended `test`.
 *
 *     import { test, expect } from "../fixtures/officer";
 *     import { OFFICERS } from "../fixtures/seed";
 *
 *     test("…", async ({ page, asOfficer }) => {
 *       await asOfficer(OFFICERS.grcChair);
 *       await page.goto("/queue");
 *     });
 *
 * ## Why the signature is `asOfficer(officer)` and not `asOfficer(roleKeys, userId?)`
 *
 * QA-04's spec sketches `asOfficer(roleKeys, userId?)`. It is implemented as
 * `asOfficer(officer)` — one roster-backed object — because ⚠ **the role keys are not a
 * control surface: the server discards them.** Measured 2026-09-06: `enrich_user`
 * (`ticketing/api/dependencies.py`) replaces whatever the caller sends with the officer's
 * DB-effective roles, so `l1-officer@grm.local` presenting `super_admin` still sees 6
 * tickets, not 281. A signature that takes role keys first invites a spec to "grant itself"
 * a capability and then assert against a queue that never changed — a test that passes for
 * the wrong reason, which is worse than one that fails.
 *
 * The ticket's real constraint is honoured and strengthened: identity comes from
 * {@link ../fixtures/seed#OFFICERS}, never from a literal invented in a spec.
 */
import { test as base, expect, type BrowserContext } from "@playwright/test";

import { BASE_URL } from "../env";
import type { SeededOfficer } from "./seed";

const BYPASS_COOKIE = "grm_bypass_user";

/**
 * The cookie value the Next proxy parses — `{user_id, role_keys[], organization_id?}`.
 * Exported because `seed.ts` sends it as a header on its plain-`fetch` lookups.
 */
export function bypassCookieValue(officer: SeededOfficer): string {
  return JSON.stringify({
    user_id: officer.userId,
    role_keys: [...officer.roleKeys],
    organization_id: officer.organizationId || undefined,
  });
}

/**
 * Make every request from `context` come from `officer`.
 *
 * Call **before** the first `page.goto` — `AuthProvider` reads the cookie once on mount, so
 * setting it after a navigation leaves the page as whoever it already was until a reload.
 */
export async function asOfficer(
  context: BrowserContext,
  officer: SeededOfficer,
): Promise<void> {
  await context.addCookies([
    {
      name: BYPASS_COOKIE,
      value: bypassCookieValue(officer),
      url: BASE_URL,
    },
  ]);
}

/**
 * Wait until the UI has resolved a real identity, before asserting anything role-dependent.
 *
 * ⚠ **A bypass build renders as `super_admin` until the roster loads.** `AuthProvider` seeds its
 * state with `fallbackBypassToken()`, whose `custom:grm_roles` is `super_admin`
 * (`app/providers/AuthProvider.tsx:191`), and replaces it only once `listOfficerRoster()`
 * resolves. Measured 2026-09-07: that call takes **~10 s on a freshly seeded database** and
 * 0.2 s on a warm one (`GRM-080`), so the window is seconds wide exactly where it matters — a
 * cold CI stack. `l1-officer@grm.local` was served the **full Settings page** there, and the
 * correct "only accessible to administrators" panel on the warm box. The spec asserting that
 * gate had been passing for the wrong reason: racing the roster and winning, on one machine.
 *
 * ⚠ **Do not wait for the officer's display name.** It is not stable across environments —
 * a fresh seed derives it from the email (`L1-Officer`) while a long-lived database has the
 * real one (`Site Officer L1`), because `mock_tickets` never applies
 * `DemoOfficerSpec.first_name/last_name` (`GRM-081`). Waiting for "not Loading…" is the same
 * signal and survives both.
 */
export async function expectIdentitySettled(
  page: import("@playwright/test").Page,
  _officer?: SeededOfficer,
): Promise<void> {
  const switcher = page.getByRole("button", { name: /demo/i });
  await expect(switcher).toBeVisible({ timeout: 45_000 });
  await expect(
    switcher,
    "the roster never loaded — the UI may still be the super_admin fallback (GRM-080)",
  ).not.toContainText("Loading", { timeout: 45_000 });
}

interface OfficerFixtures {
  /** Become a seeded officer for the rest of this test. See {@link asOfficer}. */
  asOfficer: (officer: SeededOfficer) => Promise<void>;
}

// ⚠ The second parameter is named `provide`, not `use` as Playwright's docs write it. The
// name is ours to choose, and `use` collides with React's `use` hook: `react-hooks/rules-of-hooks`
// reads `await use(...)` here as a hook called outside a component and raises an **error**, which
// fails `ui-checks` (`npx eslint . --max-warnings=-1`). Renaming the parameter fixes it at the
// cause; disabling the rule for `e2e/` would suppress a real React check on any future file here.
export const test = base.extend<OfficerFixtures>({
  asOfficer: async ({ context }, provide) => {
    await provide((officer) => asOfficer(context, officer));
  },
});

export { expect };
