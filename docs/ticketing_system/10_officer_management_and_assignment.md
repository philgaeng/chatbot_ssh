# Officer management and ticket assignment

**Status:** Locked (2026-05-15)  
**Related:** [02_ticketing_domain_and_settings.md](02_ticketing_domain_and_settings.md), [04_ticketing_schema.md](04_ticketing_schema.md), [Escalation_rules.md](Escalation_rules.md), `CLAUDE.md` (roles + workflows)

---

## 1. Goal

Enable admins to **invite, edit, and remove** officers from Settings → Officers, and to scope each officer to **organization**, **project**, **package**, and/or **location** so tickets are **always assigned to operational officers** (not IT admins) via auto-assign and controlled manual reassignment.

---

## 2. Locked product decisions (summary)

**Identity and admin UX**

- **Invite** and **Edit** require jurisdiction before the officer is usable: admin must set **at least one of** project, package, or location (not org-only). Prefer enforcing this **at invite time** (single modal) rather than a separate “pending scope” lifecycle.
- **Manage** (roster row) opens one modal for the **whole officer** (all roles and scopes, Keycloak on auth stack). There is **no expandable row** on the roster — scope view/edit happens only in that modal. **Remove** on the roster row deletes the officer entirely (all `user_roles`, all `officer_scopes`, Keycloak disable on auth stack). **Per-role** and **per-scope** delete buttons live **inside** the modal when multiple rows exist.
- **Demo stack** (`:3001`): persist changes in ticketing DB only. **Auth stack** (`:3002`): also **sync Keycloak** user attributes on edit.

**Scope semantics**

- An officer scoped to a **project** inherits **all packages** under that project (default; no need to list every package).
- An officer scoped to a **package** covers that package’s linked locations. **Locations are children of packages** in routing terms: if package P covers location ABBA, a complaint at ABBA **without project info** still routes to officers scoped to P (or to a project scope that includes P via inheritance).
- **Location** on a scope may be broad (e.g. whole country) but must be **explicitly selected** — not implied by org alone.
- **`includes_children`**: location at level N covers descendant locations (e.g. province → districts), consistent with existing `officer_scopes.includes_children`.

**Onboarding status (Keycloak)** remains **Invited / Active** (password webhook). That is **separate** from jurisdiction: an officer can be Keycloak-active but not assignable until invite/edit includes project, package, or location.

**Ticket context from chatbot**

- Intake always provides **package** (QR) **or** **location** (e.g. province/district) so routing can run.
- **Workflow selection** and **assignment** both follow the same priority:
  1. **Package** (if `package_id` present)
  2. Else **project + location** (if project known)
  3. Else **location only**

**Assignment engine**

- At each workflow step, candidates must match the step’s **`assigned_role_key`** and **scope** (see matching rules below).
- When **`ticket.package_id` is set**, only officers whose scope covers that package — or a **parent project** that inherits all its packages — are candidates. **Yes.**
- Among candidates, pick the officer with the **fewest open (non-resolved) tickets** (load balancing). Two packages in the same location do **not** imply exclusive officers; wrong assignee is corrected by **L1 escalating to manager** for reassignment.
- **Every ticket must have an assignee** on create (first step is **L1** — decision **A**). Target assignees are **operational officers** in scope, not IT admins acting as default owners. Admins configure the roster; they are not the fallback assignee pool.
- If **no officer matches** scope at L1 (misconfiguration), treat as an **operations error**: surface a clear **admin-visible** queue/state indicator and block “happy path” only as a last resort — ops must fix scopes (no silent assign to `super_admin` for day-to-day work).
- **Auto-assign on escalation** to L2/L3: **same rules** (step role + scope + least-loaded).
- **Manual reassign** dropdown: **same eligibility pool** as auto-assign (`get_teammates` / scope + current step role) for v1.

**SEAH**

- SEAH tickets (`is_seah=true`): visible and assignable only to SEAH roles plus `super_admin` / `adb_hq_exec` (read/oversight as today).

**Audit (v1 best practice)**

- Log officer lifecycle in **`ticketing.ticket_events`** or a dedicated **`ticketing.admin_audit_log`** table (recommended): `actor_user_id`, `action` (`officer.invite` | `officer.update` | `officer.disable` | `scope.add` | `scope.remove` | `role.add` | `role.remove`), `target_user_id`, JSON `before`/`after` snapshot, `timestamp`. No PII beyond `user_id`/email already in roster. UI: optional “recent changes” on Settings → Officers post-v1.

---

## 3. Current implementation (baseline)

### 3.1 Two data layers

| Layer | Table | Purpose |
| ----- | ----- | ------- |
| **Role membership** | `ticketing.user_roles` | Roster; role + org (+ optional location on row). |
| **Jurisdiction** | `ticketing.officer_scopes` | Auto-assign + reassign eligibility. |

Keycloak: identity + JWT claims. Ticketing DB: routing.

### 3.2 Gaps vs locked decisions

| Feature | Status |
| ------- | ------ |
| Invite with required project / package / location + scope row | ❌ |
| Edit / Delete officer on roster | ❌ |
| `auto_assign_officer` uses `ticket.package_id` when set | ❌ |
| Package-first workflow/assign resolution (§2 cascade) | ❌ partial |
| Location-without-project routes via package coverage | ❌ verify |
| Admin audit log for officer changes | ❌ |
| Keycloak sync on edit (auth stack) | ❌ |

### 3.3 APIs (existing)

| Endpoint | Purpose |
| -------- | ------- |
| `GET /api/v1/users/roster` | Admin roster |
| `POST /api/v1/users/invite` | Keycloak + `user_roles` (extend for scope) |
| `GET/POST/DELETE /api/v1/users/{id}/roles` | Role rows |
| `GET/POST/DELETE /api/v1/users/{id}/scopes` | Scope rows |
| `PATCH/DELETE /api/v1/roles/{role_id}` | Role catalog edit / remove (blocked if in use) |
| `DELETE /api/v1/workflows/{id}` | Remove workflow (blocked if tickets reference it; use archive for published) |
| `DELETE /api/v1/organizations/{id}` | Remove org (blocked if tickets, officers, assignments, or packages reference it) |
| `DELETE /api/v1/projects/{id}` | Remove project (blocked if tickets reference it; cascades packages/links) |
| `POST /api/v1/tickets` | Create + `auto_assign_officer` |

### 3.4 Auto-assign today (`workflow_engine.py`)

Uses step `assigned_role_key` + ticket `organization_id`, `location_code`, `project_code`; package via `PackageLocation` and scope `package_id`. **Does not yet** pass `ticket.package_id` into matching. Escalation reuses `auto_assign_officer`.

---

## 4. Scope and matching rules (normative)

### 4.1 Invite / edit validation

| Rule | Requirement |
| ---- | ------------- |
| Minimum jurisdiction | At least **one** of: `project_id`, `package_id`, `location_code` (explicit). |
| Organization | Required on every scope/role row. |
| Org-only scope | **Not allowed** for assignable officers. |

On **invite**, the modal must collect role + org + (**project** and/or **package** and/or **location**) and create matching `user_roles` + `officer_scopes` in one transaction.

### 4.2 Inheritance

| Admin selects | Officer covers |
| ------------- | -------------- |
| **Project** (no package) | All packages under project; tickets with any of those packages or locations linked to those packages per §4.3. |
| **Package** | That package; all `PackageLocation` rows for the package. |
| **Location** (+ optional `includes_children`) | That location and descendants; non-package scopes use existing rules A/B in `_scope_candidates`. |

### 4.3 Location without project on the ticket

When the chatbot submits **location only** (no `project_code` / `project_id`):

1. Resolve packages whose **package_locations** include that location (or ancestor/descendant per `includes_children` policy).
2. Treat as **package-first** assignment among officers scoped to those packages or parent projects.

### 4.4 Candidate selection for a ticket

Given ticket `T` and workflow step role `R`:

1. Resolve effective **package_id** (on ticket, or derived per §4.3).
2. Build candidate set = officers with scope matching `(R, T.organization_id, T.location_code, T.project_code, effective package)` per engine rules, including project inheritance and package location coverage.
3. If `T.package_id` set: **restrict** to scopes covering that package or parent project (locked).
4. Choose **min open ticket count** among candidates.
5. If empty at L1 create: **no assignee** + admin-visible flag (misconfiguration); do not assign to admin roles by default.

### 4.5 Multiple roles per person

One user may have multiple `user_roles`. At step N, only officers with the step’s **`assigned_role_key`** are considered (workflows are designed so one role applies per step).

---

## 5. UI specification

### 5.1 Officers roster (simple table)

Designed for admins with mixed IT literacy (e.g. provincial safeguards focal persons): **one screen, one path to edit**, no nested expand rows.

| Action | Behaviour |
| ------ | --------- |
| **+ Invite officer** | Modal: email, role, org, **required** jurisdiction (project and/or package and/or location), include-sub-locations when location set. Creates Keycloak (auth) + `user_roles` + `officer_scopes`. |
| **Manage** (row) | Opens the officer modal: same fields as invite, list of existing roles/scopes with per-row remove, staged adds, single **Save changes**. Keycloak sync on auth stack. |
| **Remove** (row) | Confirm, then remove all roles/scopes; disable Keycloak user; audit log. |

**No row expansion.** Do not use a ▶ triangle or inline scope sub-table on the roster. All scope changes go through **Manage**.

**Roster columns (v1):** Name · Email · Role · **Area covered** (aggregated project / package / location codes from `officer_scopes`) · Status (**Invited** / **Active**) · Actions (**Manage**, **Remove**).

**Area not set:** If an officer has no project, package, or location on any scope, show **No area set** in the Area covered column (amber row highlight). They will not receive auto-assigned tickets until **Manage** adds jurisdiction.

**Filters (above table):** Search, role, project, package, location — for local admins who manage one project at a time.

**Post-v1 (optional):** “Advanced roster” with extra columns (org UUID, scope count) for power users; not required for demo.

### 5.2 Other Settings tabs — Remove actions

| Tab | Row action | API behaviour |
| --- | ---------- | ------------- |
| **Roles & Permissions** | **Remove** | `DELETE /roles/{role_id}` — blocked if any `user_roles`, `officer_scopes`, or workflow steps use the role |
| **Workflows** | **Archive** (published) / **Remove** (draft, archived, admin template) | Published → `POST …/archive`; else `DELETE /workflows/{id}` — blocked if tickets use the workflow. Built-in templates: no Remove (Clone only). |
| **Organizations** | **Remove** | `DELETE /organizations/{id}` — blocked if tickets, officer roles/scopes, workflow assignments, or contractor packages reference the org |
| **Projects** | **Remove** | `DELETE /projects/{id}` — blocked if tickets reference the project; otherwise deletes packages and project links |

All Remove actions use a confirmation dialog and show the API error message when blocked (409).

### 5.3 Stacks

| Stack | URL | Officer changes |
| ----- | --- | ----------------- |
| Demo | `http://localhost:3001` | DB only |
| Auth | `http://localhost:3002` | DB + Keycloak attributes |

---

## 6. Engineering checklist

- [x] **UI:** Invite/Manage modals with required jurisdiction; Manage/Remove on roster (no row expand); per-role/scope delete in modal
- [ ] **API:** Extend `POST /users/invite`; add `PATCH` officer (or role+scope batch); validate §4.1
- [ ] **Engine:** `auto_assign_officer(..., package_id=...)`; package-first derivation §4.3–4.4; location-without-project via package locations
- [ ] **Engine:** Escalation path unchanged interface, same candidate rules
- [ ] **UI:** Reassign dropdown uses same pool as `get_teammates` (confirm in code)
- [ ] **Queue:** Unassigned / misconfiguration indicator for admins (no default admin assignee)
- [ ] **Audit:** `admin_audit_log` (or ticket_events) for §2 audit list
- [ ] **Auth:** Keycloak attribute sync on edit (`grm_roles`, `organization_id`, etc.)
- [ ] **Docs:** Link from `05_ticketing_impl_plan.md`; supersede conflicting text in §4 proposed defaults elsewhere

---

## 7. Superseded proposals

The following early defaults are **replaced** by §2:

| Old | Replaced by |
| --- | ----------- |
| P1 single scope optional on invite | Invite **must** include jurisdiction (≥1 of project/package/location); may add more scopes later in Edit |
| P5 unassigned OK for ops | Unassigned only as **error state**; every ticket should get an operational L1 assignee when roster is correct |
| Pending scope row (org-only) | **Removed** — enforce at invite instead |

---

## 8. Sign-off

| Role | Name | Date | Notes |
| ---- | ---- | ---- | ----- |
| Product | (answered in §2) | 2026-05-15 | Locked via chat |
| Engineering | | | |

---

## Appendix A — Original Q&A (archived)

<details>
<summary>Click to expand raw answers used to derive §2</summary>

**§5.1** — Chatbot provides package (QR) or location; ticket always assigned. **§5.1 package_id in engine:** YES.

**§5.2** — Step role only; multiple roles OK. SEAH visibility confirmed.

**§5.3** — Enforce project/package/location at **invite** (not pending org-only rows). Project → all packages. Location hierarchy via levels / includes_children.

**§5.4** — Edit all; row delete = full officer; modal deletes per role/scope.

**§5.5** — (A) L1 on create; escalate for reassignment; auto-assign on escalation yes; reassign same pool.

**§5.6** — Demo DB only; auth Keycloak sync OK.

**§5.7** — Package → project+location → location; locations tied to packages; least-loaded among candidates; not one-officer-per-package.

**§5.8** — Audit: see §2 (admin_audit_log recommended).

**§5.5 assignee** — Every ticket to operational officers; admins are IT, not default assignees.

</details>
