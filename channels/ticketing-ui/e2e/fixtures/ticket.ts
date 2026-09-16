// SPDX-License-Identifier: Apache-2.0

/**
 * Disposable tickets for the driven flows (QA-04c).
 *
 * ⚠ **The flow specs must not act on seeded tickets.** Escalating or resolving one is
 * irreversible and non-idempotent — a second run would push it a level further, and the demo
 * scenarios `mock_tickets.py` builds would stop meaning what their script says. That is
 * `04_testing.md` Rule 3.5 ("never mutate seed rows") at the browser level, and it is why every
 * mutating spec starts by creating its own ticket here.
 *
 * ## Two things about these tickets that are deliberate
 *
 * **1. They are never deleted, and that is the system's design, not an omission.** This GRM has
 * no erasure path for a grievance on purpose — in a government complaints system a delete
 * button is a suppression button. So flow specs leave rows behind. They are made identifiable
 * instead, `E2E-<timestamp>`, which is Rule 3.4's `_uid()` convention on this side of the wire.
 * On a CI runner the whole stack is thrown away; on a dev box the count grows slowly and
 * visibly. **Do not add a cleanup that deletes tickets.**
 *
 * **2. The assignee is whatever auto-assignment picks, and specs must read it, never assume
 * it.** Assignment ranks candidate officers by active ticket load, so the same call returns a
 * different L1 on a busy database than on a fresh seed (measured 2026-09-06: `l1-officer-3`,
 * then `l1-officer-4`, on consecutive calls). Rule 3.3 — assert on the pool, act as whoever
 * was chosen.
 */
import { BASE_URL } from "../env";

/**
 * The intake API key.
 *
 * ⚠ **The value is only ignored when the stack has no secret configured.** `verify_api_key`
 * requires the *header* always, but skips the comparison when `TICKETING_SECRET_KEY` is unset —
 * the documented dev-bypass branch (HR-01 fail-closed: any other environment refuses to serve
 * without a secret). A dev box usually leaves it unset, which is why the default below works
 * there.
 *
 * ⚠ **CI is not that case, and it cost a red run to find out.** `scripts/ci/gen_env_local_ci.sh`
 * writes a (fake) `TICKETING_SECRET_KEY`, so the comparison branch applies and this default gets
 * a 401 — measured 2026-09-07, run 34063762797: 43 passed, and the 4 that failed were exactly
 * the flows that create a ticket. The job now derives `E2E_TICKETING_API_KEY` from the same
 * `env.local` the stack is built from. **Set it whenever the target stack has a secret.**
 */
const API_KEY = process.env.E2E_TICKETING_API_KEY ?? "e2e-suite-bypass-stack";

export interface CreatedTicket {
  readonly ticketId: string;
  readonly grievanceId: string;
  /** Whoever auto-assignment chose. Read it; never assume it. */
  readonly assignee: string;
}

/**
 * Create a ticket through the intake webhook — the same path the chatbot uses — and read back
 * who it was assigned to.
 *
 * @param label short, spec-identifying text; ends up in the grievance id and the summary so a
 *              leftover row in the queue says which spec made it.
 */
export async function createTicket(
  label: string,
  { seah = false }: { seah?: boolean } = {},
): Promise<CreatedTicket> {
  const grievanceId = `E2E-${label.toUpperCase().replace(/[^A-Z0-9]+/g, "-")}-${Date.now()}`;

  const created = await post("/api/v1/tickets", {
    grievance_id: grievanceId,
    organization_id: "DOR",
    location_code: "P1_MOR",
    project_code: "KL_ROAD",
    priority: "NORMAL",
    grievance_summary: `Created by the e2e suite for: ${label}. Safe to ignore.`,
    grievance_categories: "Environmental Impact",
    grievance_location: "Urlabari, Morang District, Province 1",
    // The chatbot's SEAH menu — routes the ticket to the project's sensitive workflow.
    ...(seah ? { intake_route: "seah_intake", is_seah: true } : {}),
  });

  const ticketId = (created as { ticket_id: string }).ticket_id;
  if (seah) {
    // ⚠ The intake key cannot read a SEAH case back — a sensitive workflow's cases are visible only
    // to its cast (D-007), and `getTicket` answers 403. That refusal is the system working. The
    // spec reads the assignee through a SEAH officer's own session instead (`readTicketAs`).
    return { ticketId, grievanceId, assignee: "" };
  }
  const detail = await getTicket(ticketId);

  if (!detail.assigned_to_user_id) {
    throw new Error(
      `ticket ${grievanceId} was created but auto-assignment left it unassigned.\\n` +
        `  The flows cannot be driven without an assignee. This usually means the seeded\\n` +
        `  officer coverage is incomplete — run, in the backend container:\\n` +
        `    python -m ticketing.seed.ensure_officer_coverage --apply\\n` +
        `  ⚠ Never \`mock_tickets --reset\` to fix this: it wipes projects and officers too.`,
    );
  }

  return { ticketId, grievanceId, assignee: detail.assigned_to_user_id };
}

/** Read a ticket as the intake caller — used to learn the assignee and to check outcomes. */
export async function getTicket(ticketId: string): Promise<{
  status_code: string;
  assigned_to_user_id: string | null;
  current_step_id: string | null;
  grievance_id: string;
}> {
  const res = await fetch(`${BASE_URL}/api/v1/tickets/${ticketId}`, {
    headers: { "x-api-key": API_KEY },
    signal: AbortSignal.timeout(15_000),
  });
  if (!res.ok) {
    throw new Error(`GET /api/v1/tickets/${ticketId} returned HTTP ${res.status}`);
  }
  return res.json() as Promise<{
    status_code: string;
    assigned_to_user_id: string | null;
    current_step_id: string | null;
    grievance_id: string;
  }>;
}

async function post(path: string, body: unknown): Promise<unknown> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "x-api-key": API_KEY, "content-type": "application/json" },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(30_000),
  });

  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(
      `POST ${path} returned HTTP ${res.status}.\\n` +
        `  ${detail.slice(0, 300)}\\n` +
        `  ⚠ A 401 here means this stack has a real TICKETING_SECRET_KEY — pass it as\\n` +
        `  E2E_TICKETING_API_KEY. A 503 means it is neither a bypass stack nor configured,\\n` +
        `  which the suite's global setup should already have caught.`,
    );
  }
  return res.json();
}
