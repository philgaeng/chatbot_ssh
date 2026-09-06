// SPDX-License-Identifier: Apache-2.0

/**
 * Global setup — prove the stack is up and is the *right build* before a single spec runs.
 *
 * QA-04a. Three checks, in order, all bounded by `E2E_READY_TIMEOUT_MS`:
 *
 *   1. `ticketing_api` `/health` answers `{"status":"ok"}`
 *   2. the officer UI root answers with something below 500
 *   3. a `grm_bypass_user` cookie actually becomes an identity
 *
 * ## Why check 3 asks the session endpoint rather than looking at a page
 *
 * ⚠ **The first version of this file loaded `/login` and looked for the "Continue to demo
 * queue" button. That was a race, and it is exactly the flake this suite must not have.**
 * `app/login/page.tsx:44` redirects whenever `isAuthenticated` — and in a bypass build
 * `isAuthenticated` starts `true` unconditionally, so **`/login` always leaves for `/queue`**
 * (measured 2026-09-06: every load ends at `/queue`, cookie or no cookie). The button is real
 * but transient; the old check passed only by querying it before the effect landed. On a
 * slower runner it would have failed for no reason at all.
 *
 * So check 3 asks the mechanism the suite actually depends on: **does a `grm_bypass_user`
 * cookie become an officer?** One plain `fetch` of `/api/v1/users/me/session`, through the
 * Next proxy, with a cookie for a known seeded officer. A 200 whose `user_id` is that officer
 * proves five things at once — the UI is serving, the proxy forwards, the proxy is in bypass
 * mode (a Keycloak build ignores the cookie entirely, `app/api/v1/[...path]/route.ts`),
 * `ticketing_api` accepts internal headers, and the seeded roster is present. No browser, no
 * paint order, no dependency on a copy string a UI ticket may legitimately reword.
 *
 * **Every failure here must name what to do.** A readiness probe that times out with
 * `Error: timeout` sends the reader to the wrong place; the whole value of this file is
 * that a broken stack is diagnosed in one line of output instead of 30 minutes.
 */
import type { FullConfig } from "@playwright/test";

import { API_BASE_URL, BASE_URL, READY_TIMEOUT_MS } from "./env";
import { bypassCookieValue } from "./fixtures/officer";
import { OFFICERS } from "./fixtures/seed";

const POLL_INTERVAL_MS = 1_000;

export default async function globalSetup(_config: FullConfig): Promise<void> {
  const deadline = Date.now() + READY_TIMEOUT_MS;

  await waitForHttp({
    what: `ticketing_api health (${API_BASE_URL}/health)`,
    url: `${API_BASE_URL}/health`,
    accept: async (res) => {
      if (!res.ok) return false;
      const body = (await res.json()) as { status?: string };
      return body.status === "ok";
    },
    deadline,
    fix:
      "Start the stack: `make wsl-up`. If it is up, check `docker logs nepal_chatbot-ticketing_api-1`.\n" +
      "  If ticketing_api runs on a different port here, set E2E_API_BASE_URL.",
  });

  await waitForHttp({
    what: `officer UI root (${BASE_URL})`,
    url: BASE_URL,
    accept: (res) => res.status < 500,
    deadline,
    fix:
      "Start the stack: `make wsl-up`. If it is up, check `docker logs nepal_chatbot-grm_ui-1`.\n" +
      "  If the UI runs on a different port here, set E2E_BASE_URL.",
  });

  await assertBypassIdentity();
}

interface Probe {
  what: string;
  url: string;
  accept: (res: Response) => boolean | Promise<boolean>;
  deadline: number;
  fix: string;
}

async function waitForHttp({ what, url, accept, deadline, fix }: Probe): Promise<void> {
  let lastFailure = "no attempt completed";

  while (Date.now() < deadline) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(5_000) });
      if (await accept(res)) return;
      lastFailure = `HTTP ${res.status}`;
    } catch (err) {
      lastFailure = err instanceof Error ? err.message : String(err);
    }
    await sleep(POLL_INTERVAL_MS);
  }

  throw new Error(
    `e2e stack not ready: ${what} never became healthy within ${READY_TIMEOUT_MS} ms.\n` +
      `  Last attempt: ${lastFailure}\n` +
      `  Fix: ${fix}`,
  );
}

/**
 * Assert that a `grm_bypass_user` cookie resolves to that officer.
 *
 * The auth mode is a **build-time** constant (`NEXT_PUBLIC_AUTH_MODE` is inlined by the
 * compiler — `lib/auth/runtime-config.ts`), so a Keycloak-built image cannot be talked into
 * bypass at runtime and every spec would fail on OIDC redirects or a 401. Failing here, once,
 * with the reason is worth more than thirty specs each timing out somewhere else.
 */
async function assertBypassIdentity(): Promise<void> {
  const who = OFFICERS.grcChair;
  const url = `${BASE_URL}/api/v1/users/me/session`;

  let res: Response;
  try {
    res = await fetch(url, {
      headers: { cookie: `grm_bypass_user=${bypassCookieValue(who)}` },
      signal: AbortSignal.timeout(15_000),
    });
  } catch (err) {
    throw new Error(
      `e2e stack not ready: ${url} could not be reached.\n` +
        `  Last attempt: ${err instanceof Error ? err.message : String(err)}\n` +
        `  Fix: the UI answered on ${BASE_URL} a moment ago, so this is most likely the\n` +
        `  proxy's upstream — check TICKETING_API_URL on grm_ui.`,
    );
  }

  if (!res.ok) {
    throw new Error(
      bypassMessage(`${url} returned HTTP ${res.status}, not 200.`),
    );
  }

  const session = (await res.json()) as { user_id?: string };
  if (session.user_id !== who.userId) {
    throw new Error(
      bypassMessage(
        `the grm_bypass_user cookie for ${who.userId} resolved to ` +
          `${session.user_id ?? "(nothing)"} instead.`,
      ),
    );
  }
}

function bypassMessage(what: string): string {
  return (
    `this suite needs an AUTH_MODE=bypass build of the officer UI.\n` +
      `  ${what}\n` +
      `  A bypass build's Next proxy turns the grm_bypass_user cookie into X-Internal-* headers;\n` +
      `  a Keycloak build ignores the cookie entirely (app/api/v1/[...path]/route.ts), so every\n` +
      `  spec would run as nobody and fail confusingly.\n` +
      `  Fix: rebuild grm_ui with AUTH_MODE=bypass (env.local), or point E2E_BASE_URL at a bypass\n` +
      `  stack. In CI this is the \`-bypass\` image variant (QA-02 / Q-04).\n` +
      `  ⚠ If the mode is right, check the seed: this asks for ${OFFICERS.grcChair.userId}.`
  );
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
