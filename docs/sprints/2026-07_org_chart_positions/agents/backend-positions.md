# Agent runbook — OC-03 + OC-04: Officer positions, invite pre-fill, chart behaviors & SEAH

**Branch:** `orgchart/oc-03-04-positions` off `integration/seah-claude` · **Model:** Opus (high effort — generates the enforcement truth + SEAH leak-proofing) · **Specs:** [`../02-officer-positions-and-invite-spec.md`](../02-officer-positions-and-invite-spec.md), [`../03-chart-behaviors-and-seah-spec.md`](../03-chart-behaviors-and-seah-spec.md) · Read [`README.md`](README.md) common rules first. Needs OC-01/02 tables. Do OC-03 fully before OC-04.

⚠️ **Two of these behaviors can leak SEAH case existence through reporting lines — the highest-consequence finding class in the July 2026 review. Write the SEAH-leak tests first and watch them matter.**

## Mission

Add `officer_positions`, wire officer invite so picking a position **pre-fills** role/org/scope (generating the enforcement rows through the *existing* helpers), add the supervisor resolver, then implement the four chart-driven behaviors — with SEAH suppression proven, not assumed.

## OC-03 steps

1. Read the invite seam end to end: `ticketing/api/routers/users.py:1249-1317` and the helpers it calls — `upsert_user_role_row` (`services/officer_admin.py:145`, `UserRole` at :163) and `create_scope_row` (`officer_admin.py:97`, `OfficerScope` at :103), plus `validate_jurisdiction` (:37). These stay the **only** writers of enforcement rows.
2. Migration (chained after OC-02) + model `ticketing/models/officer_position.py` per spec §1. Head table in PROGRESS.
3. Invite pre-fill per spec §2: when the request carries `{organization_id, position_type_id}`, pre-fill role (matrix `default_role_key`), org (position org), scope (org territory) — **request overrides always win** — then save through the existing helpers **and** insert the `officer_positions` row. Never write `user_roles`/`officer_scopes` directly. Editing a type's default does not re-sync holders; transfers end the old row (`is_active=false`) without silent re-scope.
4. `/users/{id}/positions` (GET/POST/DELETE) and the `/users/{id}/supervisor` resolver per spec §3 as a **pure shared function** `resolve_supervisor(...)` (override → derived same/parent unit → `null`); OC-04 imports it.
5. `tests/ticketing/test_officer_positions.py` — assert the helpers are the writer (no direct inserts), override, dual-hat, no-resync, transfer, resolver precedence + tie-break, **authz matrix** (project_admin own-scope only), jurisdiction still enforced. Manual: invite-by-position gives correct role/scope; resolver returns override then derived.

## OC-04 steps

1. **Rebase on HR-04** before wiring the escalation-notify hook (attach to the post-hardening notification seam, not `run_sla_check`'s internals). Record the base commit in PROGRESS. Note: you touch `ticketing/engine/workflow_engine.py::auto_assign_officer` (:622-662) and the notify path — **different files from HR-04's `escalation.py`**, so no code collision.
2. §5.1 display: expose active position(s) on officer/assignee/timeline read models (position title + org unit).
3. §5.3 supervisor visibility: add reports' tickets to the Watching query, bounded by `visibility_mode`, with the **SEAH predicate inline** (`WHERE NOT is_seah` unless the viewer holds a SEAH role) — same query, not a post-filter. Reuse the queue-query construction from `docs/ticketing_system/15_ticket_queue_search_and_filters.md`.
4. §5.4 ranking: in `auto_assign_officer`'s `min(candidates, ...)` (:662), rank office-territory-covering candidates first, then least-loaded. Preference within the filtered set — do not touch `_scope_candidates` or the province fallback.
5. §5.5 escalation-notify: notify the resolved supervisor (reusing `resolve_supervisor`), **suppressed on SEAH tickets unless the supervisor independently holds a SEAH role**. Notification side effect only — never changes assignment/target/visibility; emit after the escalation commits.
6. `tests/ticketing/test_chart_behaviors.py` — **write the two SEAH-leak tests first**: non-SEAH supervisor sees zero of a subordinate's SEAH tickets and receives zero SEAH escalation notices; SEAH-holding supervisor sees/receives them. Plus visibility depths, ranking preference/fallback, notify fallback to `supervisor_role`, and an assertion that target+assignee are unchanged by all of it.

## Constraints

- No reporting-line feature makes an access-control or routing decision; escalation target, assignment filter, and SEAH visibility (doc 11 §9) are unchanged.
- SEAH predicates always inline in the query/guard.
- One supervisor resolver (OC-03's) — no duplication. No schema changes in OC-04.

## Done means

OC-03 + OC-04 checklists ticked in [`../PROGRESS.md`](../PROGRESS.md); both test files green **including both SEAH-leak tests**; enforcement rows written only via the existing helpers; rebased on HR-04 (base commit recorded); manual invite-by-position and SEAH-no-leak walk-throughs recorded.
