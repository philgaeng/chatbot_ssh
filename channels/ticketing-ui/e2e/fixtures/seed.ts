// SPDX-License-Identifier: Apache-2.0

/**
 * The **one** place that names seeded data.
 *
 * QA-04a. Every id a spec relies on lives here so that seed drift breaks one file with a
 * clear message, instead of thirty specs with `expect(locator).toBeVisible()` timeouts.
 * Mirrors `ticketing/constants/demo_officers.py` and `ticketing/seed/mock_tickets.py`.
 *
 * ## Three rules this file exists to enforce
 *
 * **1. Key on `grievance_id`, never on `ticket_id`.** `mock_tickets.py` generates
 * `ticket_id` with `uuid4()` at seed time (`_make_ticket` → `_id()`), so it is different
 * after every `--reset`. `grievance_id` is a literal in the seed and is stable. Use
 * {@link resolveTicketId} to get the runtime uuid for a route that needs one.
 *
 * **2. Never assert on a seeded ticket's `status_code`.** ⚠ Measured 2026-09-06: the seed
 * creates `GRV-2025-001` as `IN_PROGRESS`; the dev database holds it as `ESCALATED`, and
 * its event log names the culprit — `system` / *"Auto-escalated: SLA exceeded at previous
 * step"*, 2026-08-13. The SLA watchdog escalates seeded tickets as they age, so status is a
 * function of **how long the stack has been up**, not of the seed. Grievance id, assignee
 * and SEAH flag are stable; status is not.
 *
 * **3. Role keys here are documentation, not control.** ⚠ Measured 2026-09-06: the server
 * **discards** the `role_keys` a caller sends. `enrich_user` (`ticketing/api/dependencies.py`)
 * replaces them with the officer's DB-effective roles, so `l1-officer@grm.local` presenting
 * `super_admin` still sees 6 tickets, not 281. Identity is the `user_id` alone. The keys
 * below are the real roster values — they matter only to the UI, and only for the moment
 * before `AuthProvider` loads the roster and overwrites them. **Do not invent a combination
 * to grant a test a capability**: it will silently do nothing.
 */
import { BASE_URL } from "../env";
import { bypassCookieValue } from "./officer";

/** A seeded officer, exactly as `GET /api/v1/users/roster` returns them. */
export interface SeededOfficer {
  /** Keycloak username == ticketing user_id == email. The only field the server acts on. */
  readonly userId: string;
  /** Roster role keys — see rule 3 above: documentation, not control. */
  readonly roleKeys: readonly string[];
  readonly organizationId: string;
  /** `display_name`, for readable test titles and failure messages. */
  readonly label: string;
}

/**
 * The seeded roster, verified against `GET /api/v1/users/roster` on 2026-09-06.
 *
 * Not the whole roster — the demo seed also creates ~48 `deleg-*@grm.local` org admins from
 * the SH-7 org-dedup work. Those are fixtures for a different feature and none of them owns
 * a demo ticket; name one here only when a spec actually needs it.
 */
export const OFFICERS = {
  /** `super_admin` — sees every ticket including SEAH. The bypass default when no cookie is set. */
  admin: {
    userId: "admin@grm.local",
    roleKeys: ["super_admin"],
    organizationId: "DOR",
    label: "GRM Admin",
  },
  /** L1 actor. Owns `GRV-2025-005` and `GRV-2025-002`; cannot see SEAH. */
  siteL1: {
    userId: "l1-officer@grm.local",
    roleKeys: ["wf:KL_ROAD_STANDARD:LEVEL_1_SITE:actor"],
    organizationId: "DOR",
    label: "Site Officer L1",
  },
  /** L2 actor and L1 supervisor. Owns `GRV-2025-004`. */
  piuL2: {
    userId: "l2-piu@grm.local",
    roleKeys: [
      "wf:KL_ROAD_STANDARD:LEVEL_1_SITE:supervisor",
      "wf:KL_ROAD_STANDARD:LEVEL_2_PIU:actor",
    ],
    organizationId: "DOR",
    label: "PIU Officer L2",
  },
  /** L3 actor. Owns `GRV-2025-001` — the canary's subject. */
  grcChair: {
    userId: "grc-chair@grm.local",
    roleKeys: ["wf:KL_ROAD_STANDARD:LEVEL_3_GRC:actor"],
    organizationId: "DOR",
    label: "GRC Chair",
  },
  /** SEAH L1 actor. The only demo officer besides `admin` who can see `GRV-2025-SEAH-001`. */
  seahNational: {
    userId: "seah@grm.local",
    roleKeys: ["wf:KL_ROAD_SEAH:SEAH_LEVEL_1_NATIONAL:actor"],
    organizationId: "DOR",
    label: "SEAH Officer",
  },
  /** `project_admin` — for the settings routes 04b loads with an admin cookie. */
  projectAdmin: {
    userId: "project-admin@grm.local",
    roleKeys: ["project_admin"],
    organizationId: "DOR",
    label: "Project Admin",
  },
  /** `org_admin` (SH-7 retired `country_admin`; the seeded email keeps the old name). */
  orgAdmin: {
    userId: "country-admin@grm.local",
    roleKeys: ["org_admin"],
    organizationId: "DOR",
    label: "Country Admin Standard",
  },
} as const satisfies Record<string, SeededOfficer>;

/**
 * Seeded grievance ids — `mock_tickets.py`'s two demo scenarios plus four supporting tickets.
 * Named by what each one *is*, so a spec reads as intent rather than as an id.
 */
export const GRIEVANCES = {
  /** Scenario 1 — dust / children falling sick. Assigned to {@link OFFICERS.grcChair}, at L3. */
  dustAtGrc: "GRV-2025-001",
  /** Supporting — resolved, assigned to {@link OFFICERS.siteL1}. */
  resolvedAtL1: "GRV-2025-002",
  /** Supporting — assigned to `l2-piu-2@grm.local`. */
  atPiuSecond: "GRV-2025-003",
  /** Supporting — assigned to {@link OFFICERS.piuL2}. */
  atPiu: "GRV-2025-004",
  /** Supporting — open, assigned to {@link OFFICERS.siteL1}. */
  openAtL1: "GRV-2025-005",
  /** Scenario 2 — SEAH harassment. Visible only to SEAH cast members and `super_admin`. */
  seahHarassment: "GRV-2025-SEAH-001",
} as const;

/**
 * ⚠ **Three parameterised routes take a token the seed never creates.** QA-04b resolved them
 * differently, and the difference is worth knowing before you copy either approach:
 *
 * | Route | How it is covered |
 * |---|---|
 * | `/reports/view/[token]`, `/reports/public/[token]` | **Real token**, made by {@link createReportShare}. Full stack, no stub |
 * | `/closure/[token]` | **Invalid token against the real API** (the "link is invalid" state), plus a **stubbed** happy path — see `e2e/smoke/closure.spec.ts` for why |
 *
 * ⭐ Making the report tokens real required fixing a bug rather than writing a fixture:
 * `POST /api/v1/reports/share` returned **HTTP 500** on any database where nobody had shared
 * a report before (`GRM-071`, fixed 2026-09-06). It is worth saying out loud that *needing a
 * route to work in order to test it* is what found a defect two sprints of manual sweeps had
 * not — the endpoint had no test at all, only a row in `route_snapshot.txt`.
 */

/** Internal + public tokens for one freshly created report share. */
export interface ReportShareTokens {
  readonly internalToken: string;
  readonly publicToken: string;
}

/**
 * Create a report share and return both tokens.
 *
 * ⚠ **This writes to the database** — unlike everything else in this file, which only reads.
 * It is bounded: `create_report_share` keeps the newest 50 and drops the rest, so repeated
 * suite runs cannot grow the `report_share_links` settings row without limit. Nothing else
 * prunes it, so do not raise that cap without re-reading this.
 */
export async function createReportShare(
  as: SeededOfficer = OFFICERS.admin,
): Promise<ReportShareTokens> {
  const url = `${BASE_URL}/api/v1/reports/share`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      cookie: `grm_bypass_user=${bypassCookieValue(as)}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({ name: "e2e smoke share", report_kind: "overview" }),
    signal: AbortSignal.timeout(30_000),
  });

  if (!res.ok) {
    throw new Error(
      `could not create a report share: POST ${url} returned HTTP ${res.status}.\n` +
        `  The two /reports/*/[token] routes cannot be smoked without one.\n` +
        `  ⚠ A 500 here is most likely GRM-071 returning — sharing used to fail on any database\n` +
        `  where nobody had shared before (ticketing/services/report_shares.py wrote the wrong\n` +
        `  column name). If it is back, the fix and its tests are in tests/ticketing/test_report_shares.py.`,
    );
  }

  const body = (await res.json()) as { internal_token: string; public_token: string };
  return { internalToken: body.internal_token, publicToken: body.public_token };
}

/**
 * Resolve a seeded `grievance_id` to the `ticket_id` this seed run generated.
 *
 * Goes through the Next proxy (`/api/v1/*`) with an officer's bypass cookie — the same path
 * the browser takes — so a proxy regression fails here rather than as a mystery in a spec.
 *
 * @param grievanceId one of {@link GRIEVANCES}
 * @param as which officer asks; must be able to see the ticket. Defaults to `admin`, who sees all.
 */
export async function resolveTicketId(
  grievanceId: string,
  as: SeededOfficer = OFFICERS.admin,
): Promise<string> {
  const url = `${BASE_URL}/api/v1/tickets?q=${encodeURIComponent(grievanceId)}&page_size=5`;
  const res = await fetch(url, {
    headers: { cookie: `grm_bypass_user=${bypassCookieValue(as)}` },
    signal: AbortSignal.timeout(15_000),
  });

  if (!res.ok) {
    throw new Error(
      `could not resolve ticket for ${grievanceId}: GET ${url} returned HTTP ${res.status}.\n` +
        `  Is the stack seeded? \`make wsl-seed-full\`.`,
    );
  }

  const body = (await res.json()) as { items: { ticket_id: string; grievance_id: string }[] };
  const match = body.items.find((t) => t.grievance_id === grievanceId);

  if (!match) {
    throw new Error(
      `no seeded ticket with grievance_id=${grievanceId}, as ${as.label} (${as.userId}).\n` +
        `  Either the seed has not run, or ${as.label} cannot see it (SEAH tickets are visible\n` +
        `  only to the SEAH cast and super_admin).\n` +
        `  Seed: \`make wsl-seed-full\`. ⚠ Never \`mock_tickets --reset\` on a dev database you\n` +
        `  care about — it wipes projects, organizations and officers with it (KICKOFF §5).`,
    );
  }

  return match.ticket_id;
}
