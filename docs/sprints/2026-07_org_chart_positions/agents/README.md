# Agent runbooks — Org Chart & Positions

One runbook per workstream; each is a self-contained brief for a single agent run. Give the agent the runbook plus repo access — it should not need anything else.

> **Standing rule — keep PROGRESS current.** Update [`../PROGRESS.md`](../PROGRESS.md) at **every commit**: ticket status, checklist ticks, deviations, and (for schema work) the migration-head table. A commit that changes sprint state without a matching PROGRESS update is **incomplete**. This rule holds across the whole sprint — [`../README.md`](../README.md), this file, [`BUILD-HANDOVER.md`](BUILD-HANDOVER.md), and every spec. (Restated as Common rule #6 below.)

| Runbook | Tickets | Model | Branch |
|---|---|---|---|
| [**BUILD-HANDOVER.md**](BUILD-HANDOVER.md) | **the build launch** — SH-4-finder, OC-01..04, SH-7, RB-1..4 | **Opus** | per-workstream off `dev/organisation` — **start here** |
| [ux-evaluation.md](ux-evaluation.md) | OC-06 | **Opus** | `orgchart/oc-06-ux-eval` — **run first** (doc only) |
| [backend-org-tree.md](backend-org-tree.md) | OC-01, OC-02 | **Opus** | `orgchart/oc-01-02-tree` |
| [backend-positions.md](backend-positions.md) | OC-03, OC-04 | **Opus** | `orgchart/oc-03-04-positions` — after tree lands |
| [portal.md](portal.md) | OC-05 | **Opus** | `orgchart/oc-05-portal` — after backend **and** HR-06 |

## Best practices baked in (from the devil's advocate)

This is new-feature work, so we apply the July-2026 review lessons **from the first commit** — not as a later hardening pass. Every runbook below already encodes these; they are acceptance criteria, not aspirations.

| Review finding | Rule this sprint applies from day one |
|---|---|
| **Fail-open / ungated endpoints** (§2.1–2.2 codebase) | Every new endpoint (`/position-types`, `/organizations/import`, `/users/{id}/positions`, `/users/{id}/supervisor`) is gated at the **country tier** by reusing `ticketing/services/admin_access.py` — no new ad-hoc checks. Once HR-01/HR-02 land, sit behind fail-closed auth + `require_ticket_access` where applicable. |
| **SEAH-wall holes** (§2.2) | Reporting-line features (visibility, escalation-notify) carry the SEAH predicate **inline** in the query/guard, never as a separable post-filter. SEAH-leak tests are written **before** the feature and are mandatory acceptance criteria (OC-04). |
| **Zero tests / no CI** (§2.4) | Tests ship in the same commit as the code. Every endpoint gets an **authz matrix** (persona × endpoint); every behavior gets a positive + negative test. Suites run under the HR-05 CI gate. |
| **Silent-corruption / lock-free writes** (§2.3) | Enforcement rows (`user_roles`/`officer_scopes`) are only ever written through the existing `upsert_user_role_row`/`create_scope_row` helpers, so `validate_jurisdiction` and existing invariants stay in one place. No feature reads `officer_positions` to make an access decision. |
| **God-file growth** (portal §, Tier-3) | New UI is **new `components/settings/*` components**. The only edit to the 4,717-line `app/settings/page.tsx` is ~5 lines of tab wiring. |
| **Missing i18n policy** (specs §4.5) | `display_name_ne` columns ship from day one (doc 16 §10). Nepali text is **translator-gated** exactly like SEAH copy — never invented, marked for the review sheet. |
| **Spec/status drift** (specs §5) | Durable content lands in `docs/` in the same PR. On sprint close, doc 16's status flips to as-built **citing the migration/router that proves it**; the OC-06 report lands under `docs/ticketing_system/ui/`. |
| **Migration ownership** (three-stream rule) | All DDL is ticketing-stream Alembic, safety-headed, real `downgrade()`, chained linearly on the live head — coordinated with hardening HR-03 (see [`../PROGRESS.md`](../PROGRESS.md) head table). |

## Model selection (per workstream)

Pick by **difficulty and blast radius, not diff size** (same rubric as the hardening sprint). This sprint is **all-Opus, high reasoning effort** — here is why each is not a Sonnet task:

| Ticket(s) | Model / effort | Why |
|---|---|---|
| OC-06 (UX eval) | **Opus**, high | Holistic cross-tab UX judgment for low-IT-literacy government admins, plus a persona/permission audit that doubles as a security check. Analytical reasoning, not prose — Opus, not Fable. |
| OC-01 / OC-02 (tree + matrix) | **Opus**, high | New admin endpoints on a PII system + CSV import + matrix validation. The review's #2 finding was exactly ungated endpoints; getting the country-tier gating and all-or-nothing import right is correctness-critical. |
| OC-03 (positions + invite) | **Opus**, high | **Generates the enforcement truth** (`user_roles`/`officer_scopes`) from descriptive positions. A wrong scope row is a real access-control defect. Supervisor resolver has subtle precedence rules. |
| OC-04 (behaviors + SEAH) | **Opus**, high | Three reporting-line features that can each leak SEAH case existence — the highest-consequence class in the review. Inline SEAH predicates + leak tests demand care. |
| OC-05 (portal) | **Opus**, high | The invite pre-fill/matrix UI must stay correct against the permission model and not regress a shared god-file. The **only** Sonnet-eligible slice is the pure presentational tree/table rendering **if** split from the pre-fill logic. |

**Haiku:** none. **Fable:** none — the sole prose surface (Nepali `display_name_ne` labels) is translator-gated, and inventing government/SEAH-adjacent Nepali copy is a risk to contain, not a task to delegate.

## Common rules (all agents)

1. Read `CLAUDE.md` (git workflow, schema ownership, service-boundary care), [`../README.md`](../README.md) (esp. the parallel-safety seams with the hardening sprint), your ticket spec(s), and **doc 16** before touching anything. Spec/doc line numbers are July-2026 snapshots — re-locate with grep first.
2. Branch off `dev/organisation` (the active sprint branch, off `integration/seah-claude`). Never commit to `main`.
3. Tests (incl. authz matrix + SEAH-leak cases) are acceptance criteria — ship them with the code. CI must be green before `done`.
4. Smallest diff that satisfies the spec. Adjacent findings → [`../PROGRESS.md`](../PROGRESS.md) Deviations, not your diff.
5. Migrations: ticketing stream only, safety header, real `downgrade()`, chained on the live head — **record the revision + `down_revision` in the PROGRESS head table** and coordinate with HR-03.
6. **Update [`../PROGRESS.md`](../PROGRESS.md) at every commit** (status, checklist ticks, deviations, and the migration-head table) — the standing rule at the top of this file; a commit that changes sprint state without a PROGRESS update is incomplete. Execute your spec's manual verification and record results.
7. Commit messages: imperative, ticket ID first (e.g. `OC-03: pre-fill officer role and scope from selected position`).
