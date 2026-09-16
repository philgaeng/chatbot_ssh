// SPDX-License-Identifier: Apache-2.0

/**
 * Playwright — the officer UI's end-to-end suite (QA-04a).
 *
 * Runs against a **already-running, seeded stack**; it never starts one. There is no
 * `webServer` block on purpose: the stack is eleven containers and a database, brought up by
 * `make wsl-up` locally and by `make ephemeral-up` in CI (QA-03/QA-05). Point the suite with
 * `E2E_BASE_URL` — see `e2e/env.ts`.
 *
 *     npm run e2e                    # against http://localhost:3001
 *     npm run e2e -- --ui            # pick tests interactively
 *     E2E_BASE_URL=http://host:3101 npm run e2e
 *
 * Browsers are **not** installed by `npm ci` — no package in the Playwright chain has an
 * install script (verified 2026-09-06 against 1.63.0). Install them once, deliberately:
 *
 *     npx playwright install --with-deps chromium
 */
import { defineConfig, devices } from "@playwright/test";

import { BASE_URL } from "./e2e/env";

export default defineConfig({
  testDir: "./e2e",

  // ⚠ `*.spec.ts`, never `*.test.ts` — vitest's `include` is `**/*.test.ts` (vitest.config.ts)
  // and `npm test` would otherwise collect a Playwright spec and fail in a way that reads like
  // a broken test rather than a misconfiguration.
  testMatch: "**/*.spec.ts",

  globalSetup: "./e2e/global-setup.ts",

  // ── Determinism ────────────────────────────────────────────────────────────────
  // One worker, no parallelism, no retries. All three are deliberate and they are the
  // whole ticket: "a flaky e2e suite is worse than none — it trains everyone to ignore
  // a red build."
  //
  //  * `workers: 1` — every spec shares one database and one set of containers. QA-04c's
  //    flows mutate ticket state; two workers would interleave a resolve with another
  //    spec's queue assertion and produce a failure nobody can reproduce. Development
  //    parallelism (04b/c/d touch disjoint files) is not runtime parallelism.
  //  * `retries: 0` — a retry that turns red green destroys the only signal that matters
  //    here. If a spec needs a retry it is not deterministic yet, and that is a bug in the
  //    spec, not a budget problem.
  //
  // ⭐ Revisit `workers` when wall-clock becomes the constraint — the answer then is a
  // second isolated stack (QA-03 makes that possible), not a second worker on this one.
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: !!process.env.CI,

  timeout: 30_000,
  expect: { timeout: 10_000 },

  reporter: process.env.CI
    ? [["github"], ["list"], ["html", { open: "never" }]]
    : [["list"], ["html", { open: "never" }]],
  outputDir: "test-results",

  use: {
    baseURL: BASE_URL,
    // Artifacts on failure only — see e2e/fixtures/artifacts.ts for deliberate captures.
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    actionTimeout: 10_000,
    navigationTimeout: 20_000,
  },

  projects: [
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"] },
      testIgnore: "**/mobile/**",
    },
    // Mobile is in v1 as **smoke only** (Q-10). `middleware.ts` redirects mobile
    // user-agents to `/m/*`, so a desktop project can never exercise that surface and a
    // mobile project run over the desktop specs would be redirected out of them. Hence a
    // directory split rather than a second run of the same files: QA-04b's `/m/*` smoke
    // goes in `e2e/mobile/`, and nothing else does.
    {
      name: "mobile",
      use: { ...devices["Pixel 5"] },
      testMatch: "**/mobile/**/*.spec.ts",
    },
  ],
});
