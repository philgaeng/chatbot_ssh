# Devil's-advocate build review — consolidated findings

> Output of the 5-agent adversarial pass ([`DEVILS-ADVOCATE-BUILD-REVIEW.md`](DEVILS-ADVOCATE-BUILD-REVIEW.md)) against `dev/organisation @ 64ec7ee0`, 2026-07-13. De-duplicated + severity-ranked. **Reviewers filed; they did not fix.** This is the remediation backlog.

## Scorecard (vs. the design-phase bar 84 / 74)

| Axis | As-built | Owner reviewer |
|---|---|---|
| Data-integrity (migrations) | **~92%** ✓ | BE-2 |
| Completeness | **~70%** ↓ | BE-2 / FE-3 |
| Fidelity & correctness | **~65%** ↓ | FE-1 70 · FE-2 78 · BE-1 62 |
| Ease of use | **~65%** ↓ | FE-1 71 · FE-2 73 · FE-3 57 |
| **Security** | **55%** ↓↓ | BE-1 |

**Headline:** migrations are clean and the backend data plane is real (as-built docs *not* overstated); but **security is the floor** (a live SEAH leak), the **friendly-error + plain-language contract was only applied to the ~30% that was decomposed**, one **flagship surface (Frame 01) was silently cut**, and my **donor guardrail has a real bypass**.

---

## BLOCKERS

**B1 — SEAH leak: notification endpoints are not SEAH-filtered.** `GET /users/me/badge` + `/users/me/notifications` (`users.py:1753-1815`) return `grievance_id`+`grievance_summary` with no `is_seah`/`can_see_seah` gate. Reachable event-planting: `@mention`/`@all` (`tickets.py:1354-1378`) and `convene_grc` (`escalation.py:449-467`, notifies all GRC members — standard roles — unsuppressed). **BE-1 reproduced live**: a non-SEAH officer's bell returned a SEAH case's existence + summary. *(pre-existing infra + this-sprint SEAH claim.)*
**Fix:** add `Ticket.is_seah == False unless can_see_seah` to both endpoints; SEAH-suppress recipients in the mention loop + `convene_grc`. Combine with **B2**.

**B2 — SEAH cast suppression is narrower than its docstring.** `_apply_step_tier_roles` (`escalation.py:169-214`): `_seah_suppressed` fires only for `DONOR_ROLES` and the **supervisor tier is not suppressed at all** → a non-donor non-SEAH role (e.g. `adb_national_project_director`, `grc_chair`) in a SEAH step gets a `TicketViewer` row. No *active* leak today (read gates hold) but it goes live combined with B1's `@all`. *(my code — doc-13.)*
**Fix:** on a SEAH ticket, **whitelist `SEAH_ROLES`** (not a donor-only blacklist), across informed **and** observer **and** supervisor tiers.

---

## MAJOR (correctness · authz · core UX contract)

**M1 — Donor guarantee bypassable (half-migration + authz).** *(my code — doc-13.)*
- (a) `project_donor_org_ids()` reads **only** `project_donors`, no `org_role='donor'` fallback (`donor_guardrail.py:80-88`) — asymmetric with `implementing_agency_org_id()` which *does* fall back. The legacy path `POST /projects/{id}/organizations {org_role:'donor'}` is still live → a donor added that way never hits `project_donors`/`apply_donor_informed_defaults` → **go-live A5 passes vacuously → project activates with a donor uninformed on final escalation.** (BE-2 F1 = BE-1 #6.)
- (b) `add/remove_project_donor` (`locations.py:1762,1794`) gate on `MANAGE_PROJECT` but never check the path `project_id` is the caller's → **any `project_admin` mutates any project's donors** + triggers `apply_donor_informed_defaults` on a possibly-shared step. **BE-1 reproduced.** (BE-1 #2.)
**Fix:** give `project_donor_org_ids` the `org_role='donor'` fallback (or reject `'donor'` in `validate_org_role_for_project`); scope the donor endpoints to `admin_project_ids(user)`.

**M2 — Deactivated officers stay in the auto-assign pool + count as go-live coverage.** `_scope_candidates`/`auto_assign_officer` (`workflow_engine.py:429+`) and `_has_officer_on_project_wide` (`project_go_live.py:113+`) never filter `officer_is_active`; `enrich_user` only guards *request-time*, not the *system* assignment path. **BE-1 reproduced**: a deactivated officer was auto-assigned; C1/C5 report a level "staffed" on deactivated-only officers. *(this sprint — Frame-11.)*
**Fix:** exclude `officer_is_active == False` from `_scope_candidates` + the go-live coverage predicates.

**M3 — Friendly-error contract broken (the redesign's centerpiece).**
- (a) `parseApiErrorDetail`/`extractRowErrors` handle a `detail` that's string/array but **not an object** → CSV-import 422 + position-type delete 409 raw-dump `{"detail":{…}}` to the user (FE-1 #1/#2). **One-seam fix** in `lib/user-messages.ts`.
- (b) `ErrorNotice`/`formatUserFacingError` are wired in **zero** inline clusters (`grep` = 0 in `page.tsx`) — 35 raw `e.message` sites + 3 raw `alert()`; officer-lifecycle errors render raw `API 500 …` in a **blue** box (FE-3 #1, FE-2 #3).
**Fix:** unwrap object `detail` at the seam; route every inline `catch` through `<ErrorNotice>`; delete the 3 `alert()`s.

**M4 — Plain-language contract not applied to the inline clusters.** `CAST_TIER_LABELS`/`RoleLabel`/`trackLabel`/`orgRoleLabel`/`<Bilingual>` = **0 uses in `page.tsx`** (FE-3 #2). Raw slugs render across StepForm/RolesTab/AdminAccessTab/NotifPanel (`org_admin`, `assigned_role_key`, `workflow_key`, tier nouns) + the Officers Position column shows `DOR_JHA` (FE-2 #7) + org holders show raw `user_id` (FE-1 #8). Falsifies the §7.C "labels not slugs everywhere" claim.
**Fix:** apply the `lib/labels.ts` helpers + `RoleLabel` across the inline clusters.

**M5 — New-officer invite drops the position intent.** `POST /users/invite` + `OfficerInvitePayload` carry no `position_type_id`; only the *existing-officer* path creates an `officer_positions` row (`officer_positions.py:165`). A freshly-invited "SDE, Jhapa" shows "No position" in the directory — the whole premise of invite-by-position. (FE-2 #1.)
**Fix:** accept `position_type_id` on `/users/invite` and create the `OfficerPosition` in the same txn.

**M6 — Frame 01 "Setup & go-live landing" silently cut.** `SetupOverview`/`GoLiveSpine` don't exist; no landing entry in `MAIN_TABS`. It's an explicit RB-3 deliverable + half the §0 thesis (D6 fork) + has a build sheet — yet neither built **nor** in the deferred list. The old `ProjectGoLivePanel` (raw color dots, no single-next-blocker) remains. (BE-2 F2.) *(this sprint — RB-3.)*
**Fix:** build `SetupOverview`+`GoLiveSpine` on the existing go-live API, **or** honestly move it to the deferred list.

**M7 — §4.4 owning-level chip absent + cast verb-phrases not applied.** `owner_organization_id` (API returns it) is **dropped in `mapGrmRoleToEntry`** → Frame 08 can't show "System / DoR-wide / Jhapa" (FE-3 #3). StepForm/NotifPanel label the 4 slots "Assigned/Supervisor/Informed/Observer" not "Handles it/Oversees/Kept informed/Can view" (§7.E), + a "Tier configuration (Spec 12)" header (FE-3 #4).
**Fix:** carry `owner_organization_id` into `RoleEntry` + add the chip; render slots via `CAST_TIER_LABELS`.

**M8 — Directory + tree search is client-side at ~5,000-staff scale.** `searchOfficerRoster`→`/users/roster/search` and org `q`/`root_id` lazy-load all **exist but have zero callers** (FE-2 #2, FE-1 #4). §7.F3 said this "must be real."
**Fix:** wire server-side search/pagination for the directory + org tree.

---

## MODERATE

- **MO1 — authz-UI over-restriction:** `project_admin` can't edit participants (`canEdit = super||org` only) and `officer_admin` is locked out of the Officers surface entirely — both stricter than spec + backend (FE-2 #5/#6).
- **MO2 — authz (backend):** `org_admin` can appoint `project_admin` on an **unrelated** project — `users.py:418` checks the tier predicate with no subtree/project containment (the org_admin/officer_admin branches *do* contain) (BE-1 #5).
- **MO3 — two reachable banned hues** falsify "all purged": `bg-yellow-100` (`page.tsx:747` statusBadge draft) + `accent-purple-500` (`OfficerScopeTable.tsx:292`, reachable via staffing) (FE-3 #5).
- **MO4 — `org_category` chip colored off the retired actor-role map** → government == contractor == gray (FE-1 #3).
- **MO5 — two contradictory Deactivate controls** (working row-menu vs disabled "backend pending" Manage-modal) + stale file header (FE-2 #4).
- **MO6 — RolesTab empty state prints "run Alembic migrations and seed …"** instead of the §4.3 "No roles yet · [Create a role]" (FE-3 #6).
- **MO7 — notifications:** Email/SMS not marked phase-in (proto is in-app-only); observer column toggleable though §4.5 says silent (FE-3 #8).
- **MO8 — Frame 04 "why-excluded" not built** — wrong-track roles are hidden, not greyed-with-reason (§4.3) (BE-2 F3, FE-3 #9).
- **MO9 — territory shown/entered as a raw location code** ("Covers NP-P1-JHA") not a name (FE-1 #5); no Deactivate in the org `⋯` menu though the backend supports it (FE-1 #6).
- **MO10 — IA revert-on-error uses the stale mount-time prop** → dropdown snaps to the original agency, not the persisted one (FE-2 #8).
- **MO11 — RolesTab footnote stale:** "Country admins … archetype templates" (retired `country_admin` + renamed "acts as") (FE-3 #7).

## MINOR
Forest-grouping subtitle mislabels local_government (FE-1 #7) · raw `user_id`/`position_key` slug on Position-types (FE-1 #8/#9) · double sub-nav (FE-1 #10) · multi-scope invite card absent (FE-2 #9) · missing loading states / `ne={null}` / raw color literals (FE-2 #10/#11, FE-3) · raw `role_key` chips + `<code>` slugs (FE-3 #10) · dead superseded components still carry banned hues (FE-3 #11) · residual inline `workflow_scope===` compares vs `filterByTrack` (FE-3 #12) · `q7s9u1w3` downgrade not a faithful inverse (best-effort) (BE-2 F4) · `u1w3y5a7` back-fill "first match" comment inaccurate (BE-2 F5) · doc 11 §2.4 stale `local_admin` "code gap" + `country-admin@grm.local` seed ref (BE-2 F6) · routing field-vs-actor asymmetry across packaged/unpackaged tickets (BE-1 #6).

## Deferred-list verdict (BE-2 + FE-3)

| Item | Verdict |
|---|---|
| Contract migration (drop legacy actor-role tables) | **JUSTIFIED** — but fix **M1** before contracting |
| Org merge | **JUSTIFIED** |
| RB-2 Workflows/Platform extraction still inline | **PARTIALLY — understated:** extraction defer is fine, but M3/M4/M7 (ErrorNotice, labels, owning-level, verb-phrases) are cheap, extraction-independent, and should have shipped |
| **Frame 01 Setup & go-live landing** | **SHOULD-HAVE-BEEN-IN-SCOPE — see M6** (undisclosed silent cut) |
| Transactional multi-scope invite | JUSTIFIED (proto) — track |
| Notification write-gating server enforcement | JUSTIFIED (proto) |
| Share-subtree / orphan-re-home | JUSTIFIED |
| Server-side directory search | JUSTIFIED (demo) — but see **M8** at scale |

## Verified-GOOD (attacked, held)
`country_admin` removal is clean (only historical migration DDL). Primary SEAH read gates (list/detail/viewers/files) airtight. `notify_escalation_supervisor` correctly SEAH-suppressed. Go-live block logic sound (A3/A5/C5). Routing None → clean 422. `enrich_user` strips roles at request-time. All 6 migrations: single linear head, real downgrades, no PII, no cross-schema FK, idempotent back-fills; delete-guard ≡ delete-impact.
