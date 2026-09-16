# Phase 5 remainder — GRC per-step flag + archetype/`/roles`-CRUD removal

> Logged per the repo deferral rule. **The enforcement-critical part of Phase 5 — the
> track-derived SEAH re-key (§3.1) — is DONE and green** (`services/seah_visibility.py`,
> `CurrentUser.seah_track_member`, escalation whitelist re-key; `test_seah_track_visibility.py`).
> What remains is a re-model of *working* functionality + cleanup that is coupled to invariant
> tests and must be done with joint test updates, not rushed.

## 1. GRC convene/decide → per-step capability flag (retire `grc_committee` archetype)

**Why deferred:** GRC works today via the role model (`get_grc_member_user_ids` on
`{grc_chair, grc_member}`). Moving convene to a `step.is_grc` gate touches three test files
that each convene on a different step, plus the seed, so it needs a coordinated change.

**Exact plan / sites:**
- Add `WorkflowStep.is_grc` (Boolean, default False) — migration in the ticketing stream; add to
  `WorkflowStepCreate/Update/Response` + the step-editor Advanced toggle (mirror
  `actor_can_reassign`, shipped in Phase 4).
- Flag the seeded GRC step: migration `UPDATE ... SET is_grc = true WHERE step_key = 'LEVEL_3_GRC'`
  (and any SEAH GRC step); update `workflows.py` DEFAULT_TEMPLATES so cloned workflows carry it.
- Gate `GRC_CONVENE` on `step.is_grc` **inside** `grc_convene` (`engine/ticket_actions.py:536`)
  — after the existing assignment gate, so the non-assignee-403 path in
  `test_authz_matrix_extended` is unchanged; add a "not a GRC step" 422 for an assignee on a
  non-GRC step.
- `get_grc_member_user_ids` (`engine/workflow_engine.py:217`) → derive members from the GRC
  step's cast (Participant/Observer holders) rather than the `{grc_chair, grc_member}` role set;
  keep the SEAH-leak guard (`user_can_see_seah`, `escalation.py:417`).
- `summary.py` findings gate (`api/routers/tickets/summary.py:29`) keys on `grc_chair` — re-key
  to the GRC-step cast.
- Tests to update jointly: `test_escalation_engine.py:437-488` (convene on flagged L3),
  `test_seah_leak_notifications.py` (member notify), `test_authz_matrix_extended.py` (GRC_CONVENE),
  `test_ticket_actions_unit.py` (convene).

## 2. Remove the archetype apparatus + user-facing `/roles` CRUD

**Why deferred (and why it is safe to defer):** Phase 1 established that **no request-time gate
reads `roles.permissions`** — the archetype/permission apparatus is already dead weight at
runtime (`followups/tier-permissions-reconciliation.md`). Removing it is cleanup, not
enforcement. It is coupled to the **invariant** `test_authz_matrix_extended` (custom-role-delete
authz) and to `test_roles_crud`, so the endpoints must go **with** those test rewrites in one
change — which is exactly why Phase 3 kept the backend `/roles` CRUD live (it removed only the
Roles *tab*).

**Exact plan / sites:**
- Remove `POST/PATCH/DELETE /roles` handlers (`api/routers/users.py:188,238,298`) and the
  `GET /roles/archetypes` endpoint (`users.py:154`). Keep `GET /roles` (still consumed by
  Invite / staffing pickers).
- Delete `ticketing/constants/role_archetypes.py` (`ARCHETYPE_PERMISSIONS`, `ARCHETYPE_LABELS`,
  `permissions_for_archetype`, `validate_operational_permissions`, `ADMIN_ONLY_PERMISSIONS`)
  once nothing imports it; drop `Role.archetype` writes.
- Retire the `grc_committee` archetype with the GRC flag (item 1).
- Regenerate `tests/ticketing/route_snapshot.txt` (routes removed).
- Rewrite `test_roles_crud.py` (catalogue-create → tiers), `test_role_archetypes.py` (delete),
  `test_authz_matrix_extended.py` Part 2 (drop custom-role create/delete authz), and
  `test_role_delete_guard.py` to the tier model. Keep the admin-plane role delete (admin roles)
  intact.
- `stop writing new per-role permissions` (§7 Phase 1) completes here — `create_role`/`update_role`
  are removed, so `roles.permissions` is written only by the seed for legacy readability.

## 3. Performance verification (§6 / §3.6) — no work needed

The Supervisor-tab hot path is **already** backed by a write-time projection: `escalation.py`
`_apply_step_tier_roles` materializes **supervisor**-tier rows into `ticket_viewers` on ticket
creation and every escalation (the same pattern the spec names for informed/observer). So the
Supervisor queue reads a maintained projection table, not a live tier-derivation query — the §6
concern is satisfied by existing infrastructure. No MV, no `tier` column, nothing to build. (The
one per-request query I *did* add — `seah_track_role_keys` in `enrich_user` — is a small indexed
read over the SEAH workflow's steps; measured full-suite time is unchanged at ~57s.)

## TODO
See `docs/TODO.md` → "Cast-model follow-ups".
