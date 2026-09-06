// SPDX-License-Identifier: Apache-2.0

/**
 * Global setup — prove the stack is up and is the *right build* before a single spec runs.
 *
 * QA-04a. Three checks, in order, all bounded by `E2E_READY_TIMEOUT_MS`:
 *
 *   1. `ticketing_api` `/health` answers `{"status":"ok"}`
 *   2. the officer UI root answers with something below 500
 *   3. the UI is an **`AUTH_MODE=bypass` build**
 *
 * ⚠ **Check 3 needs a real browser, and that is not a design preference.** `/login` bails
 * out to client-side rendering (`BAILOUT_TO_CLIENT_SIDE_RENDERING` — `AuthProvider` calls
 * `useSearchParams` inside a Suspense boundary), so the served HTML contains none of the
 * page's text. Measured 2026-09-06: `curl http://localhost:3001/login | grep "Continue to
 * demo queue"` finds nothing on a bypass build. Grepping the HTML would therefore fail
 * *identically* on a bypass build and a Keycloak build — a check that cannot distinguish
 * the two states it exists to distinguish. So we open the page.
 *
 * **Every failure here must name what to do.** A readiness probe that times out with
 * `Error: timeout` sends the reader to the wrong place; the whole value of this file is
 * that a broken stack is diagnosed in one line of output instead of 30 minutes.
 */
import { chromium, type FullConfig } from "@playwright/test";

import { API_BASE_URL, BASE_URL, READY_TIMEOUT_MS } from "./env";

/** The bypass build's tell — `app/login/page.tsx`'s `if (AUTH_BYPASS)` branch. */
const BYPASS_BUTTON = "Continue to demo queue";

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

  await assertBypassBuild(deadline);
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
 * Assert the UI was built with `AUTH_MODE=bypass`.
 *
 * The auth mode is a **build-time** constant (`NEXT_PUBLIC_AUTH_MODE` is inlined by the
 * compiler — `lib/auth/runtime-config.ts`), so a Keycloak-built image cannot be talked into
 * bypass at runtime and the whole suite would fail on OIDC redirects. Failing here, once,
 * with the reason is worth more than 30 specs each timing out at `/login`.
 */
async function assertBypassBuild(deadline: number): Promise<void> {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    await page.goto(`${BASE_URL}/login`, { waitUntil: "domcontentloaded" });

    const remaining = Math.max(5_000, deadline - Date.now());
    try {
      await page.getByRole("button", { name: BYPASS_BUTTON }).waitFor({
        state: "visible",
        timeout: remaining,
      });
    } catch {
      throw new Error(
        `this suite needs an AUTH_MODE=bypass build of the officer UI.\n` +
          `  ${BASE_URL}/login did not render the "${BYPASS_BUTTON}" button, which only a\n` +
          `  bypass build shows (app/login/page.tsx). A Keycloak build will redirect every\n` +
          `  spec to OIDC and fail confusingly.\n` +
          `  Fix: rebuild grm_ui with AUTH_MODE=bypass (env.local), or point E2E_BASE_URL at a\n` +
          `  bypass stack. In CI this is the \`-bypass\` image variant (QA-02 / Q-04).`,
      );
    }
  } finally {
    await browser.close();
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
