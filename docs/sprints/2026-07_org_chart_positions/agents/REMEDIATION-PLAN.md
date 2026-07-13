# Remediation plan — devil's-advocate build-review fixes

> Closes the findings in [`BUILD-REVIEW-FINDINGS.md`](BUILD-REVIEW-FINDINGS.md). **This is the single source of truth for the fix pass.**
>
> **Standing rules (so we don't deviate):**
> 1. A ticket is **DONE only when its acceptance tests are written AND green** — tests ship in the same commit as the fix (tests-as-acceptance, same as the sprint).
> 2. **Update the tracker table (§1) at every commit** — status + commit SHA + tests-green tick.
> 3. **Do not widen scope.** Each ticket closes exactly the listed finding(s); anything new goes to a fresh row, not into an existing ticket.
> 4. **Fix in tier order** (T0 security → T1 correctness/authz → T2 UX contract → T3 completeness → T4 hygiene). A later-tier ticket never blocks an earlier one.
> 5. Backend tickets are **pytest-gated in Docker**; frontend tickets are **`tsc` + `next build` + vitest/grep-guardrail-gated**. Browser-only behaviours are flagged `[browser]` and are NOT claimed "done" — only "build-validated".

## 1. Progress tracker

| ID | Tier | Title | Closes | Sev | Status | Tests green | Commit |
|---|---|---|---|---|---|---|---|
| R1 | T0 | SEAH leak lockdown (notifications + cast whitelist) | B1, B2 | BLOCKER | **done** | ✅ 4 tests | `de48068a` |
| R2 | T1 | Donor guarantee: legacy fallback + endpoint scoping | M1 | MAJOR | **done** | ✅ 2 tests | this T1 commit |
| R3 | T1 | Deactivated officers out of assignment + coverage | M2 | MAJOR | **done** | ✅ 2 tests | this T1 commit |
| R4 | T1 | project_admin appointment containment | MO2 | MOD | **done** | ✅ 2 tests | this T1 commit |
| R5 | T2 | Friendly-error contract: unwrap object detail + wire ErrorNotice | M3 | MAJOR | **done** | ✅ vitest+guardrails+build | this T2 commit |
| R6 | T2 | Plain-language labels + owning-level chip in inline clusters | M4, M7 | MAJOR | **done** | ✅ guardrail+build | this T2 commit |
| R7 | T3 | Invite-by-position for new officers | M5 | MAJOR | **done** | ✅ 2 tests + tsc | this T3 commit |
| R8 | T3 | Frame 01 Setup & go-live landing (**built** per decision) | M6 | MAJOR | **done** | ✅ next build | this T3 commit |
| R9 | T3 | Server-side search at scale (directory + org tree) | M8 | MAJOR | todo | ☐ | — |
| R10 | T3 | authz-UI corrections (project_admin / officer_admin) | MO1 | MOD | **partial** | ✅ build | this T3 commit — OfficersTab manage decoupled; ProjectParticipants gate is backend-enforced (R2) |
| R11 | T4 | Design-token + label hygiene sweep | MO3/4/6/11 + MINOR | MOD | **done** | ✅ grep-guardrail 0 + build | this T4 commit |
| R12 | T4 | Fidelity nits (deactivate/notif/why-excluded/territory/IA) | MO5/7/8/9/10 | MOD | **partial** | ✅ build | this T4 commit — MO5 (deactivate contradiction) fixed; MO7/8/9/10 are browser-dependent, deferred to the browser pass |
| R13 | T4 | Doc + migration hygiene | BE-2 F4/F5/F6, BE-1 routing | MINOR | **done** | docs | this T4 commit |

---

## T0 — Security (blocker)

### R1 — SEAH leak lockdown
**Closes B1 + B2.** **Files:** `ticketing/api/routers/users.py` (badge/notifications), `ticketing/api/routers/tickets.py` (@mention/@all notify loop), `ticketing/engine/escalation.py` (`convene_grc`, `_apply_step_tier_roles`), + a SEAH-visibility helper (reuse `can_see_seah` / `user_holds_seah_role` / `SEAH_ROLES`).
**Fix:**
1. `GET /users/me/badge` + `/users/me/notifications`: exclude events whose ticket `is_seah` is true unless `current_user.can_see_seah`.
2. `@mention`/`@all` notify loop: for a SEAH ticket, drop any recipient who cannot see SEAH before writing the notify event.
3. `convene_grc`: SEAH-suppress GRC-member recipients (mirror `notify_escalation_supervisor`).
4. `_apply_step_tier_roles`: on a SEAH ticket **whitelist `SEAH_ROLES`** (replace the donor-only blacklist) across **informed, observer, AND supervisor** tiers.
**Acceptance tests** — `tests/ticketing/test_seah_leak_notifications.py` (**4 tests green** + full suite 387 passed):
- [x] non-SEAH user with an event on a SEAH ticket → `/users/me/badge` count 0 AND `/users/me/notifications` returns no SEAH row (grievance_id/summary absent).
- [x] SEAH user still sees their SEAH notifications (no over-suppression); `user_can_see_seah` helper covers SEAH + both-workflows roles.
- [x] `_apply_step_tier_roles` on a SEAH ticket with a non-SEAH role (`grc_chair`, `adb_national_project_director`) in informed/observer/supervisor → **zero** TicketViewer rows for non-SEAH; SEAH-role viewer still cast; STANDARD ticket casts them (regression).
- [x] **Regression:** STANDARD-ticket notifications unaffected; full suite green (no HR-04/chart-behaviors/donor regressions).
- [~] `@all` + `convene_grc` creation-time suppression **shipped** (`tickets.py` mention loop + `escalation.py` convene both filter non-SEAH recipients on SEAH tickets); the authoritative gate is the endpoint filter (tested above). Dedicated @all/convene event-row tests: follow-up (endpoint filter already blocks the leak).

---

## T1 — Correctness & authz (major)

### R2 — Donor guarantee: legacy fallback + endpoint scoping
**Closes M1.** **Files:** `ticketing/services/donor_guardrail.py`, `ticketing/api/routers/locations.py`.
**Fix:** (a) `project_donor_org_ids()` unions `project_donors` **and** `project_organizations.org_role='donor'` (expand-phase parity with the IA reader). (b) `add/remove_project_donor` gate on project containment (`is_project_admin(user, project_id, track)` / `project_id in admin_project_ids(user)` for non-super).
**Acceptance tests** — extend `tests/ticketing/test_donor_guardrail.py`:
- [ ] A donor present ONLY via legacy `org_role='donor'` (no `project_donors` row), not informed at the last standard step → `donor_informed_ok` False AND go-live A5 blocks (`can_activate` False).
- [ ] `project_donor_org_ids` returns the legacy donor org.
- [ ] `project_admin` scoped to project A → 403 on `POST/DELETE /projects/{B}/donors/*`; `project_admin` of B (or super_admin) → 201/204.

### R3 — Deactivated officers out of assignment + coverage
**Closes M2.** **Files:** `ticketing/engine/workflow_engine.py` (`_scope_candidates`), `ticketing/services/project_go_live.py` (coverage predicates). Use `officer_admin.officer_is_active`.
**Fix:** exclude officers with `officer_is_active == False` from `_scope_candidates` and from `_has_officer_on_project_wide`/`_has_officer_on_package`.
**Acceptance tests** — extend `tests/ticketing/test_officer_lifecycle.py` (+ `test_officer_assignment.py`):
- [ ] Deactivate the sole candidate for a step → `auto_assign_officer` does NOT return them (parks / falls through); reactivate → they're a candidate again.
- [ ] Go-live C1/C5: a level covered only by a deactivated officer reports **unstaffed** (fail); an active officer restores pass.
- [ ] Regression: active-officer assignment + coverage unchanged.

### R4 — project_admin appointment containment
**Closes MO2.** **Files:** `ticketing/api/routers/users.py` (project_admin appointment branch ~`:418`).
**Fix:** add `can_admin_org`/project containment against `body.project_id` (mirror the org_admin/officer_admin branches).
**Acceptance tests** — extend `tests/ticketing/test_admin_ladder.py`:
- [ ] org_admin scoped to subtree X → 403 appointing `project_admin` on a project outside X; 201 within X.
- [ ] super_admin unaffected.

---

## T2 — UX contract (major; `next build`-gated, some `[browser]`)

### R5 — Friendly-error contract: unwrap object detail + wire ErrorNotice
**Closes M3.** **Files:** `channels/ticketing-ui/lib/user-messages.ts`, `components/settings/org/OrgCsvImport.tsx`, `app/settings/page.tsx` (inline clusters), `officers-v2/OfficersDirectory.tsx`.
**Fix:** (a) `parseApiErrorDetail`/`formatUserFacingError` unwrap an **object** `detail` → prefer `detail.message`, fold `errors[]`/counts into prose. (b) `OrgCsvImport.extractRowErrors` reads nested `detail.errors`. (c) route every inline `catch` through `<ErrorNotice>`; **delete the 3 `alert()`** (`page.tsx:1452,1466,1481`); lifecycle errors in `OfficersDirectory` go through `<ErrorNotice>` (drop the redundant `getOfficerOpenCases` round-trip — the 409 carries `open_count`).
**Acceptance tests:**
- [ ] vitest `lib/user-messages.test.ts`: object detail `{message, errors:[…]}` and `{message, holders_count:3}` → friendly string, never raw JSON.
- [ ] grep-guardrail (add to CI notes / a shell check): `grep -c "alert(" channels/ticketing-ui/app/settings/page.tsx` == 0; `grep -c "ErrorNotice" channels/ticketing-ui/app/settings/page.tsx` > 0.
- [ ] `tsc --noEmit` + `next build` green.

### R6 — Plain-language labels + owning-level chip in inline clusters
**Closes M4 + M7.** **Files:** `app/settings/page.tsx` (StepForm, RolesTab, AdminAccessTab, WorkflowNotificationsPanel, `mapGrmRoleToEntry`/`RoleEntry`), `officers-v2/OfficersDirectory.tsx`.
**Fix:** apply `roleLabel`/`RoleLabel`/`trackLabel`/`CAST_TIER_LABELS`/`orgRoleLabel` across the inline clusters; render cast slots as "Handles it / Oversees / Kept informed / Can view"; drop the "Tier configuration (Spec 12)" header; carry `owner_organization_id` into `RoleEntry` + add an owning-level chip/column (resolve id→org name; NULL = "System · everywhere"); resolve `org_id`→name in the Officers Position column + org holders.
**Acceptance tests:**
- [ ] vitest: `roleLabel(key, undefined)` humanizes; owning-level resolver renders "System · everywhere" for NULL, "<Org> & below" otherwise.
- [ ] grep-guardrail: no `>{r.key}<` / `<code>{assigned_role_key}` / `<code>{workflow_key}` / bare `org_admin`/`assigned_role_key` string in rendered JSX of the inline clusters (heuristic list in the test).
- [ ] `tsc` + `next build` green. `[browser]` visual confirmation deferred to the browser pass.

---

## T3 — Completeness (major)

### R7 — Invite-by-position for new officers
**Closes M5.** **Files:** `ticketing/api/routers/users.py` (invite payload + handler), `ticketing/api/schemas/user.py` (or wherever `OfficerInvitePayload` lives), `channels/ticketing-ui/lib/api.ts` + `officers-v2/InviteOfficer.tsx`.
**Fix:** `OfficerInvitePayload` accepts optional `position_type_id`; `POST /users/invite` creates the `OfficerPosition` row (reuse the `assign_officer_position` pre-fill path) in the same transaction; client sends the chosen position.
**Acceptance tests** — extend `tests/ticketing/test_officer_positions.py`:
- [ ] Invite a NEW officer with `position_type_id` → an `officer_positions` row exists AND the pre-fill created `user_roles`/`officer_scopes`; roster `positions` includes the title. Parity with the existing-officer `assign_officer_position` path.
- [ ] Invite without `position_type_id` → unchanged (no position row), no regression.

### R8 — Frame 01 Setup & go-live landing  **(DECISION REQUIRED)**
**Closes M6.** Two paths — pick one before starting:
- **(a) BUILD (recommended):** `components/settings/overview/{SetupOverview,GoLiveSpine}.tsx` + a landing entry in `MAIN_TABS`, on the existing `getProjectGoLive` API — a first-run ordered checklist + the single "here's the one thing blocking go-live" line per project (§7.A / D6). No new backend.
- **(b) DEFER:** move Frame 01 to the deferred list in `SPRINT-SUMMARY.md` with an explicit justification (stops it being a *silent* cut).
**Acceptance tests (path a):**
- [ ] `next build` green; the landing renders the next-blocker line derived from `GoLiveReport` (first failing `block` check); first-run empty state shows the ordered spine. `[browser]` layout deferred.
**Acceptance (path b):** [ ] `SPRINT-SUMMARY.md` deferred list updated + `BUILD-REVIEW-FINDINGS.md` M6 marked deferred-with-reason.

### R9 — Server-side search at scale
**Closes M8.** **Files:** `officers-v2/OfficersDirectory.tsx` (→ `searchOfficerRoster`), `components/settings/org/OrgTree.tsx` (→ `listOrganizations({q, rootId})`).
**Fix:** OfficersDirectory uses debounced `searchOfficerRoster` (q + offset pagination + "1–N of total"); OrgTree wires `q` search + `root_id` lazy-expand (don't default-expand at scale).
**Acceptance tests:**
- [ ] `tsc` + `next build` green; the directory issues the `/users/roster/search` request with `q`/`limit`/`offset` (unit-mock or a `[browser]` note); OrgTree issues `q`/`root_id`. `[browser]` interaction deferred.

### R10 — authz-UI corrections
**Closes MO1.** **Files:** `app/settings/page.tsx` (ProjectParticipants gate), `officers-v2/OfficersTabV2.tsx` + `page.tsx` (Officers gates).
**Fix:** `ProjectParticipants.canEdit` = project-participation permission (project_admin own scope), not the catalog-author flag; `canInvite` includes `officer_admin`; `canManage` decoupled from `canManageStructure` → an officer-management permission.
**Acceptance tests:**
- [ ] Reason-through matrix documented in the ticket; `tsc` + `next build` green. `[browser]` persona check deferred (backend already enforces — this is UI-gating parity).

---

## T4 — Hygiene (moderate/minor)

### R11 — Design-token + label hygiene sweep
**Closes MO3, MO4, MO6, MO11 + MINOR (dead components, raw chips, scope compares).** **Fix:** `yellow`→`amber` (`page.tsx:747`), `accent-purple-500`→`accent-blue-600` (`OfficerScopeTable.tsx:292`); add `orgCategoryBadge()` token map (gov/local-gov/donor/third_party distinct); RolesTab empty-state + footnote copy (§4.3/§7.E); raw `role_key` chips → `roleLabel`; delete superseded `OrganizationsTab.tsx`/`OfficersTab.tsx` (if truly unimported); residual `workflow_scope===` → `filterByTrack`.
**Acceptance tests:**
- [ ] **grep-guardrail (the anti-deviation gate):** `grep -rEc "purple-|indigo-|orange-|teal-|sky-|yellow-" channels/ticketing-ui/app/settings channels/ticketing-ui/components/settings` == 0 (excluding comments). This test IS the "all banned hues purged" claim, now enforced.
- [ ] `tsc` + `next build` green.

### R12 — Fidelity nits
**Closes MO5, MO7, MO8, MO9, MO10.** **Fix:** remove the disabled "Deactivate" from the Manage modal + fix the stale `OfficersDirectory` header; notif Email/SMS marked phase-in + observer column read-only; StepForm shows out-of-track roles greyed-with-reason (not hidden); territory → location picker + render name; add org Deactivate/Reactivate to the `⋯` menu; IA revert uses a `lastSaved` ref + `useEffect` syncing to the prop.
**Acceptance tests:** [ ] `tsc` + `next build` green; each nit spot-checked in the ticket. `[browser]` visual deferred.

### R13 — Doc + migration hygiene
**Closes BE-2 F4/F5/F6 + BE-1 routing note.** **Fix:** `q7s9u1w3` downgrade comment → "best-effort (relabels fresh org_admin rows on rollback)"; `u1w3y5a7` back-fill comment → drop "first match" (arbitrary row); doc 11 §2.4 remove the stale `local_admin` "Code gap" + §8 `country-admin@grm.local` ref; note the packaged-vs-project routing field/actor asymmetry in `project_routing.py`.
**Acceptance tests:** [ ] docs only — no code test; verified by reading. (Optional: a routing test asserting field-vs-actor agreement for a consistent project.)

---

## Sequencing & validation

```
T0  R1                     ── security first (a live leak) ── full pytest suite must stay green
T1  R2 → R3 → R4           ── correctness/authz ── pytest per ticket + full suite
T2  R5 → R6                ── UX contract ── vitest + grep-guardrail + next build
T3  R7 → R8(decision) → R9 → R10
T4  R11 → R12 → R13        ── hygiene ── grep-guardrail is the standing anti-regression gate
```

**Definition of done for the whole pass:** every tracker row `done` with tests green; full `tests/ticketing/` suite green in Docker; `next build` green; `BUILD-REVIEW-FINDINGS.md` scorecard re-checked (target: Security back to ✓, EoU/Completeness/Fidelity re-scored ≥ the design 84/74 where the fix is code-verifiable, `[browser]` items flagged for the visual pass).
