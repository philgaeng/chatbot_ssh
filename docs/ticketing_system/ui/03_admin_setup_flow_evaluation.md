# OC-06 — Admin-setup UX/UI evaluation (org → officers → workflow → projects)

**Status:** Published July 2026 · OC-06 deliverable · Evaluates the **as-built** admin Settings surface (pre-OC-01..05).
**Last updated:** 2026-07-10 · ⚠ backfilled from git 2026-09-04; not re-verified against the code
> **Note (2026-07 rename):** this eval probed the pre-rename system, so it names `country_admin` in its persona/permission records. That tier has since been **retired → `org_admin`** (subtree-scoped) — see [doc 11 §2](../11_roles_and_permissions.md). Those references are left as the factual record of what was tested; read `country_admin` as today's `org_admin`.
**Method:** Code-grounded (every finding carries `file:line`) + **live runtime probing** of the running dev stack (bypass API :5002 was down by misconfiguration; probed the healthy auth build :5003 with header-injected personas via `GET /users/me/admin-context`, and the seeded DB on :5433). No browser screenshots were taken — runtime API/DB probing was substituted, which yields stronger, more actionable evidence for the permission and orphaned-state questions than screenshots would. Where a claim was checked live it is marked **[live]**.
**Scope:** the four setup journeys as one flow — Organizations, Officers, Workflows & roles, Projects & packages — across `channels/ticketing-ui/app/settings/page.tsx` (main tabs `org_officers`, `workflows_roles`, `projects`, `platform`).
**Audience premise (doc 16 §5.2):** primary users are Government-of-Nepal civil servants with **low IT literacy**.

> Devil's-advocate house style: real friction ranked by user impact; strengths stated first so the criticism is credible.

---

## 0. What actually exists today (baseline, verified)

- Orgs are **flat** — `ticketing.organizations` has only 7 columns, none of the OC-01 tree fields (`parent_organization_id`, `unit_type`, `territory_*`, `display_name_ne`). **[live]** Only **ADB** and **DOR** seeded. Confirms this evaluation measures the true pre-sprint baseline.
- **15 roles** (3 admin: super/country/project; 12 operational), catalog in `ticketing.roles`. Legacy `local_admin` is still seeded as an operational role. **[live]**
- **Personas** seeded and probed **[live]**: `super_admin` (bypass default), `country-admin@grm.local` (standard/NP), `country-admin-seah@grm.local` (seah/NP), `project-admin@grm.local` (KL_ROAD).

### Live permission matrix (`GET /users/me/admin-context`, one call per persona) **[live]**

| Persona | platform settings | manage_structure | create_project | tracks |
|---|:--:|:--:|:--:|---|
| super_admin | ✅ | ✅ | ✅ | standard + seah |
| country_admin (standard) | ❌ | ✅ | ✅ | standard |
| country_admin (**seah**) | ❌ | **✅** | ✅ | seah |
| project_admin | ❌ | ❌ | ❌ | standard (KL_ROAD) |

---

## 1. Journey map (4-in-1 flow, inter-tab jumps marked)

The setup admin's real path runs left→right, but the **seams** (dashed arrows) are where a low-IT-literacy user gets stranded — every dashed arrow is a "I finished this, now what?" or a hard mid-task prerequisite in *another* tab.

```
  ┌──────────────────────────┐        ┌──────────────────────────┐
  │  TAB: Organizations      │        │  TAB: Workflows & roles  │
  │  (org_officers ▸ orgs)   │        │  (workflows_roles)       │
  │                          │        │                          │
  │  create org ─▶ EDIT org  │        │  create role  ┐          │
  │     │           (Projects│        │  create workflow ─▶ steps│
  │     │            panel is│        │        step → assign ROLE│◀─┐
  │     ▼            READ-ONLY)       │        (role_key + track  │  │ role_key must
  │  org exists, but NO      │        │         must match)      │  │ already exist
  │  project/role here ......│........│.........................▲│  │ & be right track
  └───────────│──────────────┘   S1   └──────────│───────────────┘  │
              │  S2: to give the org a role you must LEAVE           │
              │      and author it on the PROJECT side              │
              ▼                                                     │
  ┌──────────────────────────┐        ┌──────────────────────────┐ │
  │  TAB: Projects & packages│        │  TAB: Officers           │ │
  │  (projects)              │        │  (org_officers ▸ officers)│ │
  │                          │        │                          │ │
  │  create project (inactive)        │  + Invite officer        │ │
  │     ▼                    │        │     ├─ pick ROLE (full  ─┼─┘ unfiltered
  │  Project actors:         │        │     │   catalog, by slug)│   catalog
  │   add ORG + role ◀───────┼── S3 ──┤     ├─ pick PROJECT      │
  │   (inline "+ new org" ok)│  org   │     ├─ pick ORG ........ │
  │   per-row "+ add officer"┼── S4 ──┼─────┘   (must be PRE-LINKED
  │     ▼                    │ invite │          to project — else
  │  Staffing table          │  new   │          dead-end banner) ◀── S5
  │     ▼                    │        └──────────────────────────┘
  │  GO-LIVE panel (top):    │
  │   A3 block? C1 block? ───┼── S6: "Fix" jumps scroll within tab; checklist
  │   else warn/info         │        goes STALE after most edits (must Refresh)
  │     ▼                    │
  │  Activate (header link)  │
  └──────────────────────────┘
```

**Seams (numbered):**
- **S1** — *Workflows ↔ Officers:* a workflow step binds a bare `role_key`; that role must exist in the Roles sub-tab **and** an officer must hold it in the Officers tab. Three sibling surfaces, no cross-link. `page.tsx:1579` (step shows raw slug), `page.tsx:4674-4695`.
- **S2** — *Organizations → Projects:* the org editor's Projects panel is **read-only**; you cannot give an org a project role from the Organizations journey at all. `page.tsx:2320-2337`.
- **S3** — *Projects needs Organizations:* staffing a project requires orgs to exist. **Guided** (inline "+ New organization" auto-links). `ProjectActorAddRow.tsx:104-153`.
- **S4** — *Projects needs Officers:* **guided** (inline "Invite new"). `ProjectOfficerModal.tsx:91-116`.
- **S5** — *Officers needs Projects:* to invite from the Officers tab, the officer's org must have been **pre-linked to the project in the Projects tab** — otherwise a mid-flow dead-end banner. `OfficerJurisdictionForm.tsx:570-574`. And `project_admin` can't invite here at all → redirected to Projects. `OfficersTab.tsx:239-250`.
- **S6** — *within Projects:* the go-live checklist sits at the top, "Fix" scrolls to sections, but the checklist **does not refresh** after adding an org/location/package/officer. `page.tsx:3072,3441`.

**Read the flow as a loop, not a line:** the two "guided" seams (S3/S4) are good; the three ungated seams (S1/S2/S5) are where the target user stalls.

---

## 2. Strengths (so the criticism is credible)

- **Guided inline creation on the project staffing row.** "+ New organization" auto-links the org to the project (`ProjectActorAddRow.tsx:84-100`); "Invite new" creates the officer inline by email (`ProjectOfficerModal.tsx:91-116`). This is the one place the flow collapses a cross-journey dependency into one action.
- **Go-live messages are plain-language and actionable** — e.g. "Assign an organization to role 'implementing_agency'" (`project_go_live.py:249`), "Add L1 … for packages: …" (`project_go_live.py:361`), each with a "Fix" jump (`ProjectGoLivePanel.tsx:109-117`).
- **Role delete guard is correct and cross-domain** — blocks 409 when a role is bound to a step **or** held by officers, returning counts (`users.py:80-99,274-283`). **[live-adjacent]** (guard logic verified in code).
- **Manage-officer scope edits are staged** as draft rows applied only on Save — good local reversibility (`OfficerScopeTable.tsx:373-395`).
- **Proactive coverage warnings** — "No officer scoped for {org} on this project" per uncovered actor (`ProjectStaffingSection.tsx:278-291`).
- **The permission model is coherent at the helper layer** (`admin_access.py`) — the matrix in §0 is internally consistent; the problem (F3) is that routes don't all *use* it.

---

## 3. Scored findings (evidence + owner)

Severity: **blocker** = prevents a real setup task, corrupts enforcement data, or is a hard security hole · **major** = significant friction / high-likelihood error / permission gap · **minor** = polish / hygiene. Owner: **OC-0x** = closes as part of that ticket · **new-ticket** = backend/authz/data fix out of this sprint · **backlog** = deferred.

| ID | Journey | Sev | Finding | Evidence (`file:line`) | Recommendation | Owner |
|---|---|---|---|---|---|---|
| F1 | Org | **blocker** | A Devanagari org **name is un-creatable from the UI**: the client ID preview is ASCII-only, returns `""`, and the Create button hard-locks. The **server, however, accepts it** and mints a Devanagari-charactered id `NP_सव` **[live]** — a client/server mismatch, not a clean rejection. | `orgId.ts:3` (ASCII regex), `OrgCreateModal.tsx:108,119`; server POST → 201 `{"organization_id":"NP_सव"}` **[live]** | Allow manual `organization_id` entry; make client derivation Unicode-aware or accept server derivation; decide an explicit ASCII-only ID policy and enforce it *both* sides. | new-ticket (+OC-01/05 org UI) |
| F2 | Workflows | **blocker** | **Step→role binding has zero server-side referential/track validation.** `assigned_role_key` is a plain string written verbatim; publish only rejects *empty* roles. New steps auto-seed a Standard slug regardless of track; inline role-create defaults to `standard` even inside a SEAH workflow. Result: wrong-track / non-existent role bindings persist silently → misrouted or zero-ticket workflows. This is the **enforcement truth positions will feed**. | `schemas/workflow.py:36-61`; `workflows.py:472-491,509-535`; publish gate `workflows.py:336-342`; new-step default `page.tsx:1466-1468`; inline default `page.tsx:855`; orphan-preserve `page.tsx:802-804,868-870` | Validate `assigned_role_key` (and supervisor/informed/observer) exist and match the workflow track on write; publish must reject unknown/wrong-track roles, not just empty. | new-ticket |
| F3 | All | major | **Blanket `require_admin` gate.** Org CRUD, project structural mutation, and officer invite all gate on `is_any_admin` (any admin tier incl. legacy `local_admin`). The fine-grained gates (`MANAGE_PROJECT`, `INVITE_OFFICERS`, `can_manage_structure`) are **defined but not wired**; UI gating (`canManageStructure`) is threaded but **never read**. **[live]** `project_admin` (KL_ROAD only) created a **global** org (201) but was correctly 403'd from creating a project. | `admin_access.py:264-271,328-338`; org `locations.py:273/314/342`; invite `users.py:1252`; dead UI prop `page.tsx:2674,2751,3010`; **[live]** POST org→201, POST project→403 | Wire the scoped gates to the routes; make UI gating defense-in-depth. OC-01/OC-03 must **not** inherit the blanket gate. | new-ticket (+OC-01/03) |
| F4 | All (org-chart) | major | **`can_manage_structure` is track-blind** → the SEAH country admin gets standard-track structure rights. **[live]** Doc 16 §7 says org-tree/CSV editing is `country_admin` **standard** only. The gate OC-01 will hang org-tree on does not enforce that. | `admin_access.py:219-223`; **[live]** seah admin `can_manage_structure=True` | OC-01 adds an explicit standard-track check for org-tree/CSV import; fix `can_manage_structure` to honor track. | OC-01 (+new-ticket) |
| F5 | Officers | major | **Inviting one officer = 6–7 disjoint decisions**, dominated by picking a role from the **full unfiltered catalog** (admin must know the `role_key`↔job mapping) and knowing which org sits on the project. This is precisely the friction the position picker targets. | role select `OfficerModals.tsx:135-146`; catalog fetch `page.tsx:4571`; decision chain `OfficerJurisdictionForm.tsx:518-585` | OC-05 position pre-fill, slotted **before** the role/scope fields at `OfficerModals.tsx:135-146`, rendered as a *result* not another form (see §7). | OC-05 |
| F6 | Officers | major | **Invite path never validates org existence or org↔project jurisdiction**; `OfficerScope.organization_id` has **no FK**; a role with no workflow binding is accepted; a multi-location invite fires N calls with **no rollback** on partial failure → orphan/partial scopes. | `officer_admin.py:64-88` (no ProjectOrganization/org check); `officer_scope.py:41` (no FK); loop `OfficerModals.tsx:86-112` | Add org-existence + org↔project checks to `validate_jurisdiction`; wrap invite scopes in one transaction. **OC-03 routes through these helpers — it must add the checks or it inherits the bug.** | new-ticket (+OC-03) |
| F7 | Org | major | **Deleting an org silently cascade-orphans its `ProjectOrganization` links** (no guard) while the **package** link *is* guarded — inconsistent. Inactivating a live-linked org is unguarded too. | delete guards `locations.py:334-400` (no ProjectOrganization count) vs package guard `:388-397`; cascade FK `project.py:135-138`; PATCH inactivate `locations.py:324-325` | Add a `ProjectOrganization` count to the delete guard (409); warn on inactivating a live actor. | new-ticket |
| F8 | Org | major | **Org→project/role authoring is impossible from the Organizations journey** — the editor's Projects panel is read-only; the role shown is a derived rollup. All authoring lives on the project side (S2). | read-only panel `page.tsx:2320-2337`; rollup `orgRoster.ts:10-46` | Either make the org editor's project links editable, or (better, §7) fold org management into a single tree surface and drop the split. | OC-05 note / backlog |
| F9 | Projects | major | **Go-live checklist goes stale.** It only re-fetches on activate-toggle and messaging-save; adding an org, location, package, or officer does not refresh it — the checklist silently lies until the admin clicks Refresh. | `page.tsx:3072,3441` (only bump points); adds at `3134,3166` don't refresh | Bump `goLiveKey` after every structural mutation, or poll. | OC-05 / backlog |
| F10 | Projects / Workflows | major | **Developer instructions shown to civil servants.** Empty states say "Run DB migration to seed construction_road" and "Run Alembic migrations and seed (`mock_tickets --reset`) …". Un-actionable for the target user. | `ProjectTypesTab.tsx:69`; `page.tsx:479-484` | Replace with either a real seed action button (admin-triggerable) or plain-language "contact your administrator" copy. | new-ticket / OC-05 |
| F11 | Projects / All | major | **Raw JSON API errors surfaced verbatim** (e.g. `API 409 …: {"detail":{"message":"Role is in use",…}}`), and go-live blocking-vs-warning is conveyed by **color/dot only, no text label** — fails low-literacy and color-blind users. A human-readable formatter exists but is unused. | raw error `page.tsx:428,486-488`, `lib/api.ts:227-232`; unused formatter `lib/user-messages.ts`; dots `ProjectGoLivePanel.tsx:14-19,104` | Route all admin errors through `formatUserFacingError`; add "Blocking/Warning" text labels beside dots. | OC-05 / new-ticket |
| F12 | Workflows | major | **UI invites actions it will always reject.** `project_admin` is granted the `workflows_roles` tab with fully-enabled Publish/Archive/Add-step and role Edit/Remove buttons, but every write 403s (`can_mutate_workflow` excludes project_admin). | tab grant `page.tsx:4550-4552`; unconditional buttons `page.tsx:1524-1545,521-534`; backend `admin_access.py:345-349` | Gate the buttons on the same predicate the server uses (disable + explain), or hide the tab for project_admin. | OC-05 |
| F13 | All (Workflows worst) | major | **God-file structural risk.** `page.tsx` is **4,723 lines / 154 `useState` / 24 `useEffect`**; the workflows-&-roles journey alone is **~1,766 lines inline** (StepForm 245, WorkflowEditor 281, WorkflowsTab 249). Track-filter logic is **re-implemented in 4 places** and diverges. **[live]** (`wc`, `grep`). | `page.tsx` (4723 lines); inline fns `page.tsx:400,1910,4165`; dup track filter `page.tsx:414-418`, `1978-1982`, `users.py:142-147`, `admin_access.py:341-349` | OC-05 must add only new `components/settings/*` (its rule). File a backlog ticket to extract WorkflowsTab/RolesTab (post-HR-06). | OC-05 (comply) + backlog |
| F14 | All | major | **Zero i18n scaffolding.** No i18n package, no locale dirs, `lang="en"` hardcoded; every label/help/error is an English literal. `display_name_ne` (org-chart) would be the **first** bilingual data in a portal with no rendering seam. **[live]** (package.json, dir scan). | no i18n dep/dirs; `app/layout.tsx:29`; strings throughout all four packs | OC-05: render `display_name_ne` bilingually where present, English fallback, **never fabricate**. File an i18n-infra backlog ticket for the admin surface. | OC-05 (render) + backlog (infra) |
| F15 | Workflows | major | **Role delete guard ignores the tier fields.** It counts only `assigned_role_key` usage; a role used **only** as supervisor/informed/observer on a step can be deleted, orphaning those references. | guard `users.py:80-100`; tiers written `workflows.py:481-483` | Extend `_role_usage_counts` to count supervisor/informed/observer. | new-ticket |
| F16 | Org | major | **`GET /organizations` has no auth gate at all** — the org registry is readable by any authenticated caller regardless of admin status. | `locations.py:253-258` | Add an admin/read gate consistent with the other org endpoints. | new-ticket |
| F17 | Projects | major | **"Activated but tickets-blocked" is a reachable, confusing end-state.** `can_activate` (A3 only) and `can_accept_tickets` (C1 only) are independent flags, so a project can show "Can activate" yet "Tickets blocked" — two terse verdicts with no single "here's what's blocking you." | `project_go_live.py:524-525`; verdict chips `ProjectGoLivePanel.tsx:80-86` | Add a one-line "single next blocker" summary; make the two verdicts read as one journey. | OC-05 / backlog |
| F18 | Org | minor | **No country validation; duplicate names silently allowed.** Org create/update never validates `country_code` against `countries` (project create does); a duplicate name "ADB" silently becomes `ADB_2`. **[live]** | `locations.py:298,322`; **[live]** POST "ADB"→201 `ADB_2`; contrast `locations.py:757-758` | Validate country; warn on duplicate name. | new-ticket |
| F19 | Org | minor | **Promised org ID ≠ actual.** The modal shows "Will be created as: <id>" but never sends it; the server re-derives independently, so the id the user was promised can differ. | preview `OrgCreateModal.tsx:105`; not sent `:36-40`; server derive `locations.py:287-294` | Send the previewed id, or drop the promise. | OC-05 / backlog |
| F20 | Workflows | minor | **"Permissions" promised, not delivered.** Tabs are labelled "roles & permissions" but there is no permission-editing UI; permissions are chosen implicitly via an unexplained "Archetype" dropdown. | labels `page.tsx:274,4676`; archetype `page.tsx:364-370`→`users.py:174-176` | Explain the archetype ("this decides what the role can do"), or relabel the tab. | backlog |
| F21 | Officers | minor | **Role silently defaults to the first catalog entry; invite fires an irreversible Keycloak email with no confirm.** An inattentive admin sends the wrong-role invite with no confirmation step. | default `OfficerModals.tsx:52`; email `users.py:1282-1283` | No pre-selected role (force a choice); add a confirm step before the email. | OC-05 |
| F22 | Projects | minor | **Go-live permissiveness (by design, but undocumented):** activate with no packages, missing required actors, or unstaffed L2 (all `warn`, not `block`); attach an **inactive** org to satisfy a block. | `project_go_live.py:285,261-273,381-399,154-156`; attach `locations.py:1074` | Document the warn/block policy in-product; consider blocking on inactive-org actor. | backlog |
| F23 | Projects | minor | **Empty Staffing has no CTA and a foot-gun.** "+ Add officer" is disabled at zero actors and, when enabled, silently targets `projectActors[0]`; the empty table offers no path back to "add an actor first." | `ProjectStaffingSection.tsx:303-318,332` | Add a CTA linking to the actor row; make the officer's actor an explicit choice. | OC-05 |
| F24 | All | minor | **Design-system violations** — `page.tsx` imports `design-tokens` 0×; `ORG_ROLE_COLORS` (with eliminated `purple/indigo/orange/teal`) is **duplicated** in `OrganizationsTab.tsx` and `page.tsx`; `accent-purple-500`, `emerald-*`, `yellow-*` scattered. A direct trap for OC-05's "match the design system." | `OrganizationsTab.tsx:23-33`; `page.tsx:280-290,436,753,940`; `OfficerJurisdictionForm.tsx:472`; `OfficerScopeTable.tsx:466` | OC-05 uses `lib/design-tokens.ts` and does **not** copy `ORG_ROLE_COLORS`; backlog to centralize an org-role token map. | OC-05 + backlog |
| F25 | Org | minor | **`default_language` exists in DB + API but no UI** can set or view it (defaults `"ne"`). Dead Nepali-first data. | `organization.py:38`; absent from types `api.ts:1581-1588` | Surface it, or drop it from the create schema. | backlog |

**Counts:** 2 blocker · 15 major · 8 minor. **Owners:** OC-01 ×1, OC-03 ×1, OC-05 ×10 (some shared), new-ticket ×9, backlog ×8.

---

## 4. Top-5 friction points for a low-IT-literacy admin (ranked, with fixes)

1. **Inviting an officer is a 7-decision puzzle, not a task (F5, F6).** The admin must translate a real job into a `role_key` from an unfiltered catalog, know which org sits on the project, and have pre-linked that org in another tab first. **Fix:** the OC-05 position picker — tree node → position → role/org/scope pre-filled — *if* it's rendered as a one-line result (§7), not a fourth form.
2. **A Nepali-named org can't be created (F1).** The exact target user types a valid name in their own script and the Create button locks. **Fix:** manual-id fallback + Unicode-aware derivation; decide the ID-charset policy explicitly.
3. **The seams between tabs strand the user (S1/S2/S5, F8).** "I linked the org — why can't I give it a role here?" (read-only panel); "I made the workflow — why doesn't it show on the project?" (forgot to publish); "I'm inviting an officer — why is the org list empty?" (not pre-linked). **Fix:** guided next-step affordances at each seam ("This org has no project role yet → add one" as an action, not a read-out); surface publish state; carry the org-link prerequisite into the invite flow.
4. **The UI speaks developer, not Nepali civil-servant (F10, F11, F20; slugs).** "Run Alembic migrations", raw `API 409 {...json...}`, `site_safeguards_focal_person` shown instead of a label, colour-only severity. **Fix:** friendly error formatting (the formatter already exists, unused), human role labels everywhere, text severity labels, no migration instructions in end-user empty states.
5. **Silent wrong-track / orphan bindings the admin can't tell are broken (F2, F3).** A step bound to a non-existent or wrong-track role publishes cleanly; a role created inside a SEAH workflow silently won't appear. **Fix:** server-side referential + track validation on step save/publish, and a visible "this role isn't listed because its track is Standard" explanation.

---

## 5. Orphaned-state catalogue (and whether OC-01..05 closes it)

| # | Invalid end-state the UI permits today | Evidence | Closed by the org-chart sprint? |
|---|---|---|---|
| O1 | Org with no country / a **non-existent** country code | `locations.py:298,322` | **No** — OC-01 adds tree/territory, not country validation → **new-ticket** |
| O2 | Two orgs with the same name (`ADB`, `ADB_2`) **[live]** | server derive `locations.py:287-294` | **No** → new-ticket |
| O3 | Deleting an org **cascade-orphans** its project-actor link | `locations.py:334-400` vs FK `project.py:135-138` | **No** — OC-01 adds a subtree delete guard but not this → **new-ticket** |
| O4 | Officer scope whose **org isn't on the project / doesn't exist** (no FK) | `officer_admin.py:64-88`; `officer_scope.py:41` | **Only if OC-03 adds the check** — it reuses the unvalidated helpers → **OC-03 acceptance** |
| O5 | Officer holding a role **bound to no workflow** (zero-ticket officer) | `officer_admin.py:84-88` | **No** — position→role matrix can still point at an unbound role → **new-ticket** |
| O6 | Workflow step bound to a **non-existent / wrong-track** role | `workflows.py:472-535`; publish `:336-342` | **No** (F2) → **new-ticket**; OC-02 *does* validate a position type's `default_role_key`, closing the *position* side only |
| O7 | Role deletable while used **only** as supervisor/informed/observer | `users.py:80-100` | **No** → new-ticket |
| O8 | Project **activated but cannot accept tickets** | `project_go_live.py:524-525` | **No** → backlog (clarity) |
| O9 | **Inactive** org used to satisfy a go-live actor block | `locations.py:1074`; `project_go_live.py:154-156` | **No** → backlog |
| O10 | Partial officer scopes after a multi-location invite fails mid-loop | `OfficerModals.tsx:86-112` | **No** → new-ticket (transaction) |

**New orphan states the org-chart feature itself could introduce** (guard in OC design): a position type pointing at a deleted role (OC-02 validates on write — closed); an `officer_positions` row whose `default_role_key` was edited without re-syncing holders (intended per doc 16 §4 — must be a **visible** "review holders" prompt, not silent drift, per OC-05 item 2).

---

## 6. Nepali / i18n readiness (admin surface)

**The admin surface has zero i18n scaffolding. [live]** No i18n package in `channels/ticketing-ui/package.json`, no `locales/`, `messages/`, or `[locale]` directory, and `app/layout.tsx:29` hardcodes `lang="en"`. Every label, placeholder, help string, and error across all four journeys is an inline English literal; the only translation logic in the app is for *location display names* (`page.tsx:2456-2457`), not UI chrome.

Concretely for the org-chart sprint:
- `display_name_ne` (OC-01/OC-02) would be the **first bilingual data field in a portal that has no way to render bilingually**. OC-05 must render it inline where present (e.g. "SDE / वरिष्ठ डिभिजनल इन्जिनियर") with an English fallback, and **never fabricate** Nepali — that is a translator-gated column.
- The Devanagari-name blocker (F1) shows the surface is not merely un-translated but **actively hostile to Devanagari input** in at least one create path.
- **Recommendation:** file a standalone "admin-surface i18n scaffolding" backlog ticket. It is out of OC-05's scope to retrofit i18n across 4,723 lines, but OC-05 should (a) render `_ne` when present, and (b) not add new hardcoded English that a later i18n pass must unpick — put new strings where a future extractor can find them.

---

## 7. Verdict — does the org-chart feature actually help?

**Yes — it targets the single biggest friction (officer setup) and is worth building — but its payoff is contingent on two things this evaluation makes concrete.**

The premise (doc 16 §5.2) is that a position picker makes officer setup "one comprehensible action." The evidence backs the premise: inviting one officer today is **6–7 disjoint decisions** (F5), and the two hardest — mapping a real job to a `role_key` from an unfiltered catalog, and knowing which org sits on the project (which must have been pre-linked elsewhere) — are exactly what a tree-node → position → pre-filled-role/org/scope choice collapses. The pre-fill slots cleanly at `OfficerModals.tsx:135-146`. So the feature is aimed at the right target.

**Two caveats that decide whether it delivers or just adds a tab:**

1. **It only helps if OC-05 renders the pre-fill as a *result*, not a fourth form.** If picking a position drops four pre-filled-but-visible editable fields in front of a low-IT user, we've re-introduced the complexity we're removing. The win is: show the human-readable outcome ("SDE, Jhapa Division Office → acts as Site Safeguards Focal, covers Jhapa district") and hide role/scope behind an "Adjust" disclosure with the override badge. And the two **new** tabs (OrgTree, PositionTypes) land on a surface the devil's-advocate scored at 48% and inside a 4,723-line god-file (F13) — the tree should **replace** the flat org list rather than sit beside it, and position-types (a set-once catalog) shouldn't get top-tab weight.

2. **Positions *feed* the enforcement truth through the same unvalidated plumbing, so the feature inherits today's rot unless the sprint closes it.** A position generates `user_roles` + `officer_scopes` via the very helpers that never check org existence or org↔project jurisdiction (F6/O4) — so **OC-03 must add those checks or it will mint orphan scopes at scale**. A position→role matrix can still point at a role bound to no workflow step (O5), and step→role bindings themselves have no validation (F2/O6) — so a perfectly-set-up position can still route to nothing. And the authz gate the whole thing hangs on (`can_manage_structure`) is track-blind and blanket (F3/F4) — OC-01 must tighten it, not inherit it.

**Two of the top-5 frictions are *not* addressed by the org-chart feature at all** — the Devanagari-name blocker (F1) and the developer-jargon/raw-error/slug surface (F10/F11) — and need their own tickets regardless.

**Bottom line:** build it, but treat OC-05's invite UX as the make-or-break deliverable (result-not-form + IA that doesn't grow the god-file), require OC-03/OC-01 to close the validation/authz gaps rather than pass them through, and spin the non-org-chart blockers (F1 input, F2 workflow validation, F3 authz wiring, F10/F11 copy) into their own tickets so they don't hide behind "the org-chart shipped."

---

## 8. Feed-forward — how this changes the rest of the sprint

- **OC-05 acceptance items added:** F5 (position pre-fill as a *result*, §7), F8/IA (tree replaces flat list; position-types not a top tab), F9 (refresh go-live), F11 (friendly errors + severity text), F12 (gate project_admin buttons), F13 (comply with god-file rule), F14 (render `_ne`), F21 (no default role + confirm), F23 (staffing CTA), F24 (design tokens, no `ORG_ROLE_COLORS` copy).
- **OC-01 acceptance item:** F4 — org-tree/CSV edits gated at `country_admin` **standard** track, not blanket `can_manage_structure`.
- **OC-03 acceptance item:** F6/O4 — the position-fed invite must validate org existence + org↔project jurisdiction (don't inherit the unvalidated helper path).
- **New backlog/security tickets filed:** F1 (org ID charset + manual entry), F2 (workflow step referential/track validation), F3 (wire scoped gates; make UI gating defense-in-depth), F7 (org delete/inactivate guards), F10 (end-user empty-state copy), F15 (role delete guard tiers), F16 (`GET /organizations` auth), F17 (activated-but-blocked clarity), F18 (country/duplicate validation), i18n-scaffolding (F14).
- **Doc fix:** OC-05's spec header ("Grounded by the OC-06 UX evaluation") currently links to the OC-06 *ticket*, not its findings — repoint it to **this** file.

> **Cross-reference:** the OC-05 design forks (IA of the two new tabs; invite pre-fill as result-not-form; the actionable shape of the "review holders" prompt; Nepali render-now-vs-defer) are captured in the sprint review discussion and should be resolved before OC-05 implementation begins, per OC-06 §5.
