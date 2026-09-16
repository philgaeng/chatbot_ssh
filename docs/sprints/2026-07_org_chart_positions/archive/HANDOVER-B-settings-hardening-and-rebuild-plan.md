# Handover B — Settings hardening & rebuild plan

> **⚠ ARCHIVED (design phase) — superseded by [../agents/BUILD-HANDOVER.md](../agents/BUILD-HANDOVER.md)** (the build entry point). Kept for history; the plan is carried forward there.

> **Owner:** engineering track (implementing agents) · **Companion to** [Handover A](HANDOVER-A-settings-ux-redesign-brief.md) (the UX brief).
> **Grounded by:** [`docs/ticketing_system/ui/03_admin_setup_flow_evaluation.md`](../../../ticketing_system/ui/03_admin_setup_flow_evaluation.md) (OC-06) — every ticket below cites an OC-06 finding + `file:line` evidence.
> **Rule of the road:** read Handover A's §0 mandate. This plan has two parts with a hard boundary — **Part 1 starts now; Part 2 waits on the UX brief.**

---

## 0. The pivot (what changed, and why this doc exists)

OC-06 found the admin Settings surface has two entangled problems: a **UX** problem (48% score, six inter-tab seams) and a **structural/correctness** problem (4,723-line god-file, unwired authz gates, unvalidated bindings). The sprint's original plan (README §Parallel-safety, OC-05 spec) tried to add the org-chart UI as **bolt-on components with a ~5-line `page.tsx` diff** — a deliberate workaround to avoid touching the god-file.

We are now choosing to **fix it properly**: full UX redesign ([Handover A](HANDOVER-A-settings-ux-redesign-brief.md)) + a real rebuild. This changes the sprint shape:

- **OC-01..04 (org-chart backend)** → proceed unchanged. They're data-model + API work the redesign consumes; UX-independent.
- **OC-05 (org-chart UI)** → **paused and folded into the rebuild** (Part 2, RB-4). Building it as a god-file patch is throw-away work now.
- **New backend-hardening tickets** (this doc, Part 1) → the OC-06 findings that are true regardless of the UI. Start immediately.

## 1. What runs when (the gating diagram)

```
   START NOW (parallel, UX-independent)              GATED ON Handover A (UX brief locked)
   ────────────────────────────────────              ──────────────────────────────────────
   Part 1 · Backend hardening                          Part 2 · Frontend rebuild
     SH-1  authz gates wired                             RB-2  god-file demolition + component tree
     SH-2  workflow step→role validation                 RB-3  rebuild the four flows per wireframes
     SH-3  invite org/jurisdiction validation  ─┐        RB-4  org-chart surfaces (former OC-05)
     SH-4  org lifecycle guards                  │        (design-token contract applied throughout)
     SH-5  role delete guard tiers               │
     SH-6  org-id charset policy                 │      CAN START EARLY (infra, framework-decision only)
                                                 │        RB-1  i18n scaffolding
   OC-01..04 · org-chart backend  ───────────────┘
     (SH-1/SH-3 are also OC-01/OC-03 acceptance gates)
```

**Signal to start Part 2:** Handover A deliverable 3 (the new component tree) is finalized. Until then, Part 2 has no target shape to build toward — don't start.

---

## 2. Part 1 — Backend hardening (start now)

Each is its own ticket, branch off `integration/seah-claude` (README convention), **tests in the same commit** (authz matrix / validation tests as acceptance, not follow-ups). These are security/correctness fixes on a government PII system — treat them at the same scrutiny bar as the org-chart endpoints (README §"Why this sprint carries extra scrutiny").

### SH-1 — Wire the scoped authz gates (OC-06 F3, F4)
- **Finding:** org CRUD, project structural mutation, and officer invite all gate on the **blanket** `is_any_admin` (any admin tier incl. legacy `local_admin`). The fine-grained gates exist but aren't wired; UI gating is cosmetic. `can_manage_structure` is **track-blind** (SEAH admin gets standard-track structure rights). **[live-verified]** a `project_admin` created a *global* org (201) but was 403'd from creating a project.
- **Evidence:** `ticketing/services/admin_access.py:219-223` (track-blind), `:264-271` (`is_any_admin`), `:328-338` (unwired gates); org routes `ticketing/api/routers/locations.py:273/314/342`; invite `ticketing/api/routers/users.py:1252`; dead UI prop `channels/ticketing-ui/app/settings/page.tsx:2674,2751,3010`.
- **Fix:** apply `require_settings_write(...)` / `MANAGE_PROJECT` to the routes; gate org CRUD on a standard-track-only structure check; add per-scope checks (a `project_admin` may not mutate global orgs it doesn't own).
- **Acceptance:** authz matrix × persona for org/project/invite routes; `project_admin` cannot create a global org; a SEAH-track admin cannot edit the standard-track org tree. **This is the gate OC-01 (org-tree edit = standard track) and OC-03 (invite) build on — land it first or in lockstep.**
- **As-built (org CRUD slice done):** a **dedicated** `SettingsAction.MANAGE_ORG_STRUCTURE` + `can_manage_org_structure()` (super OR a **standard-track** org admin) now gates `POST/PATCH/DELETE /organizations` (`ticketing/api/routers/locations.py`). **Refinement of F4:** the pre-existing `can_manage_structure` / `MANAGE_STRUCTURE` is intentionally *track-agnostic* — it gates **project** structure, where a SEAH-track admin legitimately manages SEAH projects (test: `test_admin_access.py::test_require_structure_ok_for_seah_*`). F4 conflated the two; the fix is a *separate* org-structure action, **not** mutating the shared project-structure gate. Tests: `tests/ticketing/test_org_authz.py` (CI unit matrix + integration route tests). **Still open under SH-1 (SH-1b):** per-scope enforcement on project-structural link/package/actor-role routes (`locations.py:1069,1112,…`) — project_admin own-scope checks. **This is where the [design §2.4](../DESIGN-settings-redesign.md) "project_admin may create a contractor" decision lands:** a project_admin creates + links an independent participant org via the **project-scoped actor path** (not the country-gated `MANAGE_ORG_STRUCTURE` global `/organizations` route), authorized by **project ownership + the track-agnostic project-structure gate**, and running the SH-4 dedup check. Editing the shared reporting tree stays standard-track only.
- **⤷ Superseded by SH-7 (hierarchical admin scope):** the flat gate is generalized to org-subtree scope ([design §2.5](../DESIGN-settings-redesign.md)). The org-CRUD slice already built stands as "reporting-tree edit = standard track"; SH-7 generalizes *who qualifies* to "an `org_admin` whose scope reaches this node," and it absorbs SH-1b. Needs OC-01's descendant helper.

### SH-2 — Workflow step→role referential + track validation (OC-06 F2)
- **Finding:** `assigned_role_key` (and supervisor/informed/observer) are plain strings written verbatim; nothing checks the role **exists** or matches the workflow **track**; publish only rejects *empty* roles. Wrong-track/non-existent bindings persist silently → misrouted or zero-ticket workflows. This corrupts the **enforcement truth positions will feed**.
- **Evidence:** `ticketing/api/schemas/workflow.py:36-61`; `ticketing/api/routers/workflows.py:472-491,509-535` (verbatim write), `:336-342` (publish empty-only); UI seeds a Standard slug on every new step `channels/ticketing-ui/app/settings/page.tsx:1466-1468`.
- **Fix:** validate all four role references on step write and on publish — must resolve to an existing role whose `workflow_scope` matches the workflow track; reject otherwise.
- **Acceptance:** cannot save or publish a step bound to a non-existent or wrong-track role; regression test.

### SH-3 — Invite path org/jurisdiction validation + atomic scopes (OC-06 F6 / O4) — **also OC-03 acceptance**
- **Finding:** the invite path never validates the org **exists** or is **linked to the project**; `OfficerScope.organization_id` has **no FK**; a multi-location invite fires N calls with **no rollback** on partial failure. Orphan/partial scopes result.
- **Evidence:** `ticketing/services/officer_admin.py:64-88` (no org / `ProjectOrganization` check); `ticketing/models/officer_scope.py:41` (no FK); `channels/ticketing-ui/components/settings/OfficerModals.tsx:86-112` (loop, no rollback).
- **Fix:** in `validate_jurisdiction`, assert the org exists and (for non-country roles) is linked to the selected project; wrap invite scope creation in one transaction.
- **Acceptance:** invite with an org not on the project → rejected; multi-scope invite is all-or-nothing. **OC-03's position-fed invite reuses these helpers — it inherits this bug unless SH-3 lands. Do not ship OC-03 without it.**

### SH-4 — Org lifecycle guards (OC-06 F7, F16, F18)
- **Findings:** (a) deleting an org **cascade-orphans** its `ProjectOrganization` links (no guard) while the *package* link is guarded — inconsistent; (b) `GET /organizations` has **no auth gate**; (c) no country validation on create/update, and duplicate names silently become `ADB_2` **[live-verified]**.
- **Evidence:** `ticketing/api/routers/locations.py:334-400` (delete guards, missing `ProjectOrganization`) vs FK cascade `ticketing/models/project.py:135-138`; `:324-325` (unguarded inactivate); `:253-258` (no auth on GET); `:298,322` (no country validation).
- **Fix:** add a `ProjectOrganization` count to the delete guard (409); warn/block inactivating a live actor; auth-gate the list endpoint; validate `country_code`. **Upgrade duplicate handling to a fuzzy candidate finder** ([design §2.4](../DESIGN-settings-redesign.md); client seam `lib/orgDedup.ts`): on create — via **either** the country org route **or** the project_admin participant-create path (SH-1b) — return likely-duplicate candidates matched on **distinctive name tokens** (stoplist of generic words: corporation/company/organization/contractor/construction/pvt/ltd/jv/…), **corporate email domain** (free providers gmail/yahoo/hotmail/outlook/… ignored), and **address**. Surface as a **soft flag** ("Use existing / Create anyway") — **not** a hard block, and **not** the old silent `ADB_2` rename.
- **Acceptance:** cannot silently orphan a project's actor org; list endpoint requires admin; bogus country rejected; a near-duplicate create returns candidate matches (stable endpoint contract for the client flag) and the admin can still proceed ("Create anyway"). Tests cover the name-token stoplist and the free-vs-corporate email cases.

### SH-5 — Role delete guard: count tier fields (OC-06 F15)
- **Finding:** the delete guard counts only `assigned_role_key` usage; a role used **only** as supervisor/informed/observer can be deleted, orphaning those references.
- **Evidence:** `ticketing/api/routers/users.py:80-100`; tiers written at `ticketing/api/routers/workflows.py:481-483`.
- **Fix:** extend `_role_usage_counts` to include supervisor/informed/observer references.
- **Acceptance:** a role referenced only in a tier field cannot be deleted (409).

### SH-6 — Org-id charset policy (server side of OC-06 F1)
- **Finding:** the server accepts a Devanagari org name and mints a **Devanagari-charactered id** (`NP_सव`) **[live-verified]**, while the explicit-id path sanitizes to `[A-Z0-9_]` — inconsistent. (The client-side lock that blocks the create button is a **Part 2 / RB-4** fix.)
- **Evidence:** derived path `ticketing/api/routers/locations.py:287-294`; explicit-id sanitize `:282`; client ASCII regex `channels/ticketing-ui/lib/orgId.ts:3`.
- **Fix:** decide an explicit id-charset policy (recommend ASCII-only ids, Nepali carried in `display_name_ne`) and enforce it consistently on both the derived and explicit paths.
- **Acceptance:** id derivation is deterministic and charset-consistent server-side; documented for the client fix.

### SH-7 — Hierarchical admin scope (org-subtree delegation) — supersedes SH-1's flat gate, absorbs SH-1b
- **Decision:** [design §2.5](../DESIGN-settings-redesign.md) + **[doc 11 §2](../../../ticketing_system/11_roles_and_permissions.md) updated** — a **4-tier strict-subset ladder**: **super_admin / org_admin (subtree, *any depth*; authors the catalog) / project_admin (contractors + staffing, no catalog) / officer_admin (invite officers only)**. Plus **`org_category` actor types** (government / local_government / donor / third_party): a new *institutional* root is **super-only**, third_party (contractors) delegable. Driven by scale (DoR ≈ 5,000) + federalism; resolves the design-review admin-model blocker.
- **Fix:** (1) the **4 role keys** `super_admin` / `org_admin` / `project_admin` / `officer_admin` (the org tier replaces the old flat country tier; `officer_admin` is new), with **catalog authoring = super + org_admin only**. (2) A **scope-reach test** — an admin's authority covers a target org iff it is (a) in `descendant_org_ids(scope_node)`, (b) an org the admin **created**, or (c) a **shared** subtree — **and** matches `workflow_track`; build on **OC-01's `descendant_org_ids` CTE + cycle guard**. (3) **`org_category`** (`government`/`local_government`/`donor`/`third_party`) on orgs, inherited from root, with **new-institutional-root creation gated to `super_admin`**; `third_party` creatable by `org_admin`/`project_admin` in scope. (4) **Attenuated delegation** (appoint at/below node, same track, ≤ own capabilities). (5) **Org-scoped catalog** — add **`owner_organization_id`** (nullable = global) to `ticketing.roles` / `workflow_definitions` / `position_types`; set to the author's scope node on create; filter every catalog read (step binder, invite picker, role/position lists) to `owner IS NULL OR target ∈ descendant_org_ids(owner) ∪ {owner}`. Extend `GET /users/me/admin-context` to return tier + reach.
- **Supersedes / absorbs:** SH-1's flat `MANAGE_ORG_STRUCTURE` country gate (org-tree edit becomes "target in my scope reach, standard track") and the open **SH-1b** own-scope work (project_admin participant-create + link falls out of the same reach test). SH-1's other slices (project/invite gates, track-blindness fix) stand.
- **Acceptance:** authz matrix × persona × **tree position** — an org_admin acts inside its subtree/owned/whitelisted orgs and is 403'd outside; attenuation holds (no privilege escalation via sub-delegation); **SEAH-leak tests** (admin scope never surfaces SEAH case existence, doc 16 §6); cycle-guard test on the descendant CTE; **org-scoped-catalog filter test** — a catalog item owned at node N is listable/usable only at N ∪ descendants (invisible in a sibling/ancestor), a global item everywhere (doc 11 §11 item 3d).
- **Sequencing:** needs OC-01's tree + descendant helper — land OC-01 first (or in lockstep). This is where doc 11's revision (super/org_admin/project_admin) becomes as-built.

> **Not new tickets — proceed as planned:** OC-01, OC-02, OC-03, OC-04 (the org-chart *backend*) are UX-independent and consume none of Handover A. Run them per their existing specs, with SH-1/SH-3/F4 wired in as their authz/validation acceptance gates.

---

## 3. Part 2 — Frontend rebuild (gated on Handover A)

Do not start RB-2..RB-4 until Handover A's component tree is locked. RB-1 (i18n) can start earlier as infra.

### RB-1 — i18n scaffolding (OC-06 F14) — *can start early*
- **Finding:** zero i18n scaffolding — no package, no locale dirs, `lang="en"` hardcoded; every string is an English literal.
- **Evidence:** OC-06 §6; `channels/ticketing-ui/app/layout.tsx:29`.
- **Work:** choose an i18n approach compatible with **this** Next.js 16 build (read `node_modules/next/dist/docs/` per `channels/ticketing-ui/AGENTS.md` — it is **not** the Next.js you know); establish locale files, an EN/NE key structure with **English fallback**, and a `display_name_ne` render helper. **Never fabricate Nepali** — wire the seam, leave translation to the translator sheet.
- **Note:** framework choice is UX-independent (can start now); string extraction lands with RB-2/RB-3 as the rebuild replaces the literals.

### RB-2 — God-file demolition + component tree (OC-06 F13, F24)
- **Finding:** `page.tsx` is 4,723 lines / 154 `useState` / 24 `useEffect`; `WorkflowsTab`/`RolesTab`/`AdminAccessTab` are inline; track-filter logic is duplicated in 4 places; `design-tokens.ts` is imported 0×; `ORG_ROLE_COLORS` (with banned hues) is duplicated across files.
- **Evidence:** OC-06 §3 F13/F24; inline fns `channels/ticketing-ui/app/settings/page.tsx:400,1910,4165`; dup color map `OrganizationsTab.tsx:23-33` + `page.tsx:280-290`.
- **Work:** decompose `page.tsx` into the component tree Handover A defines (its deliverable 3). Enforce the **design-token contract**: all color via `lib/design-tokens.ts`, no `ORG_ROLE_COLORS` copies, no banned hues. Centralize the track-filter logic in one shared helper.
- **Coordination:** this collides with **hardening HR-06** (which moves hooks in `page.tsx`). Since we're demolishing the file, coordinate: either land after HR-06 and absorb its change, or agree HR-06 is subsumed by the rebuild. Record the decision in [PROGRESS.md](../PROGRESS.md).

### RB-3 — Rebuild the four flows per Handover A wireframes
- Organizations (tree replaces flat list), Officers (invite-as-result), Workflows & roles (guided step→role binding with valid-only picker), Projects & go-live. Absorbs the UX findings: F8 (org→project authoring becomes an action), F9 (live-refresh go-live), F11 (friendly errors + text severity via the unused `lib/user-messages.ts` formatter), F12 (gate `project_admin` buttons on the server predicate), F17 (single "next blocker" summary), F21 (no default role + confirm), F23 (staffing CTA), plus the client-side of F1 (manual org-id entry / Unicode-aware derivation).

### RB-4 — Org-chart surfaces (folds former OC-05)
- Tree editor + territory + CSV import; position-type catalog (secondary panel, not a top tab, per Handover A D1/D3); **invite pre-fill rendered as a result** (Handover A D2) — outcome card + "Adjust" disclosure + override badge; display surfaces (position title on roster/chips/timeline/reports with role-label fallback); typed `lib/api.ts` wrappers for every OC-0x endpoint (keep `apiFetch`'s signature stable). Consumes OC-01..04's endpoints; renders `display_name_ne` bilingually where present (Handover A D4). The "review holders" prompt follows Handover A D3 (actionable, not bare notice).

### Open build items (from the Handover-C review — spec'd, not yet built)
Five items the design review (DESIGN-REVIEW rounds 2–4) surfaced as **build-time**, each spec'd in [Handover C](HANDOVER-C-admin-model-finalize-and-cleanup.md) §3. Fold into the ticket noted:

| Item | Fold into | Spec |
|---|---|---|
| **Admin audit-log UI** — GET endpoint + read surface over the existing `log_admin_audit()` events ("who appointed/revoked/authored what, when") | **RB-4** (new surface) + a small API ticket | governance-critical on a PII system |
| **Dual-hat invite collision** — invite where the email is already an officer → "add a position" vs Keycloak 409 | **RB-4 + OC-03** | doc 16 §3.3 (multiple active positions) |
| **Workflow level-delete in-flight guard** — "⋯ remove a level" must guard tickets parked at that level (reassign/block) | **RB-3** | mirrors org-delete / officer-deactivate guards |
| **CSV import schema** — columns/headers/format for `POST /organizations/import` (parent-by-key, `unit_type`, `org_category`, territory, `_ne`, encoding) | **OC-01** | the bulk load path has no schema yet |
| **Project country-validation** — validate `country_code` vs the `countries` table + org↔project country consistency | **SH-4 / B1** | recent SH-4a/SH-6 work adjacent |

---

## 4. Coordination seams

- **Migration heads:** SH tickets that touch schema (SH-3's FK on `officer_scope.organization_id`, if added) and OC-01..03 revisions must **serialize on the live `alembic heads`** (README §Parallel-safety; coordinate with hardening HR-03). Ticketing stream only, safety header, real `downgrade()`.
- **HR-06 vs RB-2:** the god-file demolition subsumes or must absorb HR-06's hooks move — decide and record before RB-2 starts.
- **Branches:** per README — hardening on `orgchart/…` branches off `integration/seah-claude`; never touch `main`.
- **Re-scope note:** update [README.md](../README.md) (OC-05 row) and [PROGRESS.md](../PROGRESS.md) to reflect OC-05 → folded into RB-4, and add the SH-1..SH-6 tickets to the tracker.

## 5. Definition of done (this plan)

- [ ] SH-1..SH-6 shipped with authz/validation tests; OC-01..04 backend green (SH-1/SH-3/F4 wired as their acceptance gates).
- [ ] RB-1 i18n seam in place (no fabricated Nepali).
- [ ] `page.tsx` decomposed to the Handover A component tree; design-token contract enforced; no banned hues; track-filter logic single-sourced.
- [ ] The four flows + org-chart surfaces rebuilt per Handover A wireframes; OC-06 UX findings closed or explicitly deferred with a note.
- [ ] OC-05 formally retired/folded; README + PROGRESS updated; doc 16 status flipped to as-built where the backend proves it.
