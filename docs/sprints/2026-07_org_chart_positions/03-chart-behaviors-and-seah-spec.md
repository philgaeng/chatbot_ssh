# OC-04 — Chart-driven behaviors + SEAH leak-proofing

> Workstream: backend-positions (part 2) · Branch `orgchart/oc-03-04-positions` · After OC-03.
> Feature source: [`docs/ticketing_system/16_org_chart_and_positions.md`](../../ticketing_system/16_org_chart_and_positions.md) §5 (behaviors) and **§6 (SEAH rules)**. Re-locate line numbers first.
> **Security-critical.** Three of these four behaviors surface tickets or notifications *through reporting lines*. Each is a potential SEAH-existence leak — the class the July 2026 review flagged as door-sized holes in the SEAH wall. SEAH-leak tests are acceptance criteria, written **before** the feature.

---

## Invariant that governs this whole ticket

> **Escalation still targets the next workflow step's role pool. The reporting line never redirects escalation** (doc 16 §5). The chart drives *display, visibility, ranking preference, and a courtesy notification* — never the access-control or routing decisions, which stay in `user_roles`/`officer_scopes` and the workflow engine.

And the SEAH overlay (doc 16 §6): the chart is shared for **directory** purposes (SEAH officers may hold positions), but **no reporting-line feature may reveal that a SEAH ticket exists** to anyone who wouldn't already see it under [`11_roles_and_permissions.md`](../../ticketing_system/11_roles_and_permissions.md) §9.

## 5.1 Display & directory (low risk)

Show `position title + org unit` (e.g. "SDE, Jhapa Division Office") instead of the raw role key on: officer roster, ticket assignee chips, timeline events, reports. Backend: expose the officer's active position(s) on the relevant read models (officer read, ticket assignee read, timeline event actor). No new access decision. Reports column swap is OC-05/reports.

## 5.3 Supervisor visibility (query layer — **SEAH-sensitive**)

An officer's **Watching** tab additionally includes tickets assigned to their reports, depth per the position type's `visibility_mode` (`none | direct_reports | subtree`).

- Compute the report set from `officer_positions` (people whose resolved supervisor is this officer), bounded by `visibility_mode`.
- **SEAH leak-proof:** the added tickets are filtered `WHERE NOT is_seah` **unless the viewer independently holds a SEAH role** (doc 16 §6). This filter lives in the same query, not in a post-filter that could be bypassed by another caller.
- Senior positions default to `direct_reports`/`none` to avoid a firehose (doc 16 §5.3); broad oversight stays the job of observer roles, not reporting lines.
- Reuse the existing Watching/queue query construction (`docs/ticketing_system/15_ticket_queue_search_and_filters.md`); add the reports clause as an `OR` branch that carries the same SEAH predicate as the rest of the query.

## 5.4 Prefer-own-office assignment (ranking tweak — low risk)

In `auto_assign_officer` (`ticketing/engine/workflow_engine.py:622-662`, the `min(candidates, ...)` at :662): among scope-matched candidates, **rank first** the officers whose org-unit territory covers the ticket location (`territory_location_code` matches, honoring `territory_includes_children`), **then** least-loaded. A *preference within the already-filtered candidate set*, never a filter — the province fallback ([07 §4.4](../../ticketing_system/07_officer_management_and_assignment.md)) still applies. Do not change `_scope_candidates` (the filter); only the ordering key.

## 5.5 Supervisor advised on escalation (notification only — **SEAH-sensitive**)

When a ticket escalates off officer X's step, notify X's resolved supervisor (in-app; channel matrix per [12 §9](../../ticketing_system/12_workflows_configuration.md)). This reuses the existing `supervisor_role` tier: the resolved reporting-line person is a **person-specific resolver for that tier**, with `supervisor_role` as fallback (OC-03's resolver returning `null`).

- **SEAH leak-proof:** on a SEAH ticket, this notification is **suppressed unless the supervisor independently holds a SEAH role** (doc 16 §6). The suppression is unconditional and tested — a non-SEAH supervisor of a SEAH officer must receive **nothing** that reveals the escalation.
- This is a notification side effect only. It must **not** change who the ticket is assigned to, the escalation target, or any visibility. Hook it where escalation already emits notifications (do not re-open the HR-04-hardened `run_sla_check` transaction structure — emit the notify after the escalation commits, same as existing notifications).

## Interaction with the hardening sprint

OC-04 touches `ticketing/engine/workflow_engine.py::auto_assign_officer` and the escalation **notification** path — **not** `ticketing/engine/escalation.py::run_sla_check`, which HR-04 hardens. Different files; no code collision. But: **rebase on HR-04 before wiring the escalation-notify hook** so you attach to the post-HR-04 notification seam, not the pre-hardening one. Record the base commit in PROGRESS.

## Constraints

- No reporting-line feature makes an access-control or routing decision. Escalation target, assignment filter, and SEAH ticket visibility per doc 11 §9 are **unchanged**.
- Every SEAH-sensitive query/notification carries the SEAH predicate **inline** (same query / same guard), never as a separable post-filter.
- Reuse OC-03's `resolve_supervisor` — do not write a second supervisor resolver.
- No schema changes here (uses OC-01..03 tables); if you find you need one, stop and note it — it belongs in an earlier ticket's migration.

## Tests (acceptance) — SEAH cases are mandatory, write them first

`tests/ticketing/test_chart_behaviors.py`:
- [ ] **Visibility, non-SEAH:** supervisor with `direct_reports` sees a report's standard ticket in Watching; with `subtree` sees deeper; with `none` sees none.
- [ ] **Visibility, SEAH leak-proof:** a non-SEAH supervisor of a SEAH officer sees **zero** of that officer's SEAH tickets in Watching; a supervisor who independently holds a SEAH role does see them. (This is the headline test.)
- [ ] **Assignment ranking:** among two scope-matched candidates, the one whose office territory covers the ticket location is chosen; when neither covers, least-loaded wins (fallback intact); ranking never *excludes* a candidate the old filter included.
- [ ] **Escalation notify, non-SEAH:** escalating off X's step notifies X's resolved supervisor once; falls back to `supervisor_role` pool when the resolver returns `null`.
- [ ] **Escalation notify, SEAH suppression:** escalating a SEAH ticket off a SEAH officer whose supervisor is non-SEAH ⇒ supervisor receives **nothing**; a SEAH-holding supervisor ⇒ receives it. Assert no leak via notification payload contents either.
- [ ] Escalation target and assignment are unchanged by all of the above (assert the ticket's step/assignee are identical with and without the notify feature).

## Manual verification
- [ ] On the seeded DB with a SEAH scenario: confirm a standard supervisor's Watching tab and notifications show **no trace** of a subordinate's SEAH case; confirm a standard case's supervisor is notified on escalation.
- [ ] Confirm a ticket near a specific division office is preferentially assigned to that office's officer when scope-eligible.

## Done means
OC-04 checklist ticked in [`PROGRESS.md`](PROGRESS.md); `test_chart_behaviors.py` green **including both SEAH-leak tests**; rebased on HR-04; manual SEAH no-leak walk-through recorded.
