// SPDX-License-Identifier: Apache-2.0

/**
 * Where the e2e suite points, and how long it is allowed to wait.
 *
 * QA-04a. **Never hardcode a host in a spec** — the same suite runs against the local
 * WSL stack, against an ephemeral stack on a CI runner (QA-05), and potentially against
 * a stack whose ports QA-03 has parameterised. Everything it needs to find is here.
 *
 * | Variable | Default | What it points at |
 * |---|---|---|
 * | `E2E_BASE_URL`       | `http://localhost:3001` | the officer UI (`grm_ui`), reached **directly** — Q-12 |
 * | `E2E_API_BASE_URL`   | `http://localhost:5002` | `ticketing_api`, for the `/health` readiness probe only |
 * | `E2E_READY_TIMEOUT_MS` | `90000` | budget for global setup's readiness poll |
 *
 * ⚠ **Two base URLs, and only one of them is used by tests.** Specs talk to the UI
 * (`E2E_BASE_URL`) and reach the API the way the app does — through the Next proxy at
 * `/api/v1/*`. `E2E_API_BASE_URL` exists because `/health` is **not** behind that proxy
 * (the proxy only forwards `/api/v1/*`), so readiness cannot be established through it.
 * If you find yourself adding a second use for it, ask first whether the spec should be
 * going through the proxy instead — that is the path the officer's browser actually takes.
 */

/** Officer UI base — no trailing slash. */
export const BASE_URL = stripTrailingSlash(process.env.E2E_BASE_URL ?? "http://localhost:3001");

/** ticketing_api base — readiness probe only; see the note above. */
export const API_BASE_URL = stripTrailingSlash(
  process.env.E2E_API_BASE_URL ?? "http://localhost:5002",
);

/**
 * How long global setup waits for the stack. Generous, because a cold `docker compose up`
 * on a CI runner takes a while — but **bounded**, because a hang is the failure mode that
 * teaches everyone to ignore the suite.
 */
export const READY_TIMEOUT_MS = Number(process.env.E2E_READY_TIMEOUT_MS ?? 90_000);

function stripTrailingSlash(url: string): string {
  return url.endsWith("/") ? url.slice(0, -1) : url;
}
