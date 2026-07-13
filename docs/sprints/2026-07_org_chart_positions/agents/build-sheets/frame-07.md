# Build sheet — Frame 07 · Platform — Admin access

> RB-0 build sheet. Grounds wireframe Frame 07 + atlas Surface 06 in the real API.
> Sources: DESIGN §2.5 (4-tier ladder + actor types + attenuated delegation), §3.1 row 07, §7.F5 (lifecycle), §7.C (plain-language scope prose); wireframes Frame 07 (lines 1050-1151); atlas Surface 06 (lines 586-657). Data owner: **SH-7**.

## 1. Visual ref
- **Wireframe Frame 07** + **Atlas Surface 06**. `Settings ▸ Platform ▸ Admin access` (super_admin; org_admin sees its own subtree).
- Top-down: **"Your admin scope"** tree (your node + subtree + shared orgs, each chip-tagged: "your node" / "subtree · N offices" / "shared with you") with a plain-language scope note → **"Admin holders in your scope"** table (Person / Admin role / Responsible for / Grievances-track) → **"Appoint an admin below you"** form (email · admin role · responsible-for node · track) → variants: **project_admin read-only** (appoint/share disabled + explained), **Revoke & bootstrap** (revoke rows + "re-homes N created orgs" note + super-admin bootstrap line).
- **States (atlas Surface 06):** Your scope (row-gating) · Appoint an admin · "Can't grant more than you have" (attenuation) · Share an organisation (whitelist) · project_admin read-only (disabled, not 403-on-click) · Loading (scope resolves from `/users/me/admin-context` first).

## 2. Component subtree (DESIGN §3, platform/)
```
platform/
  PlatformTab.tsx            [extract]  sub-nav: Locations · Quarterly reports · Project types · Admin access
    AdminAccessPanel.tsx     [extract]  from page.tsx AdminAccessTab (~551); gains "appoint org_admin at this node" (attenuated) + "whitelist a subtree"; renders subtree-scoped (§2.5)
  lib/adminScope.ts          [new]      client scope-reach test (subtree ∪ owned ∪ whitelisted, + track) for row-gating (§2.5)
  shared/ErrorNotice.tsx  Bilingual.tsx  RoleLabel.tsx  [new]
```
- **Maps to existing:** `app/settings/page.tsx:551 AdminAccessTab`. **CRITICAL STALENESS:** it uses the **retired `country_admin`** tier (`page.tsx:556 useState<"country_admin"|"project_admin">`), while the backend `AdminScopeCreate.role_key` pattern is `^(org_admin|project_admin|officer_admin)$` (`schemas/user.py:70`). RB-3 must **rename to `org_admin`** and add the `officer_admin` tier + the subtree-scope UI.

## 3. Governing interaction rules (§2.5 admin ladder)
- **Four-tier strict-subset ladder:** `super_admin` (platform; creates institutional roots) ⊃ `org_admin` (an org node **+ its whole subtree, any depth**; authors catalog for its track; creates contractors; appoints lower admins) ⊃ `project_admin` (one project + track; contractors + staffing) ⊃ `officer_admin` (invite/modify/revoke officers only). Render tier names, never role keys, on screen ("Organisation admin" / "Project admin" / "Officer admin", §7.E).
- **Row-scoped to reach (SH-7):** every list shows ONLY orgs in the admin's reach — subtree ∪ orgs it created ∪ subtrees shared with it, matching track. An org_admin **can't see** (not just can't edit) outside scope. Server-enforced (`can_admin_org`, `is_org_admin`, `is_project_admin` in `users.py`); client `adminScope.ts` mirrors as defense-in-depth.
- **Attenuated appointment (§2.5):** appoint at/below your node, in your track, **never exceeding your own capabilities**. `create_admin_scope` enforces: org_admin appointment requires `organization_id` in your subtree (`users.py:397-416`); country-wide org_admin is **super_admin only** (`403` at `:406-410`); project_admin requires `project_id` + matching-track org_admin/super (`:417-429`); officer_admin requires org/project + matching appointer (`:430-462`).
- **Actor-type gating:** creating a **new institutional root** (government / local_government / donor) is **super_admin only**; **third_party** (contractors) are delegable to org_admin/project_admin. (This is org-create gating, adjacent to Frame 02/05 — the Admin-access form notes it, per pin 27.)
- **project_admin read-only boundary (F12):** appoint/whitelist buttons render **disabled + explained** ("Appointing admins is above your tier"), never enabled-then-403.
- **Lifecycle (§7.F5):** **Revoke** appointments/whitelists (confirm); **Bootstrap** — super_admin appoints the first org_admin at a ministry root (empty-admin base case); **Orphan-on-removal** — when an org_admin is removed, orgs it created re-home to the nearest enclosing scope.

## 4. Concrete endpoints (real routers / lib/api.ts)
| Purpose | Method + path | Payload → Response | Wrapper |
|---|---|---|---|
| My scope/tier (gate the whole surface) | `GET /api/v1/users/me/admin-context` | → `AdminContextResponse{is_super_admin,is_org_admin,is_project_admin,admin_workflow_tracks[],admin_project_ids[],admin_country_codes[],can_manage_structure,admin_scopes[]}` (`users.py:319-327`, schema `schemas/user.py:101-111`) | `getAdminContext()` `api.ts:820` |
| List admin holders (scoped) | `GET /api/v1/admin-scopes` | → `list[AdminScopeResponse]` (super sees all; else own — `users.py:361-376`) | `listAdminScopes()` `api.ts:824` |
| Appoint an admin | `POST /api/v1/admin-scopes` | `AdminScopeCreate{user_id, role_key∈org_admin\|project_admin\|officer_admin, country_code?, project_id?, organization_id?, package_id?, workflow_track?\|workflow_tracks[]}` → `AdminScopeResponse` (attenuation → 403/422) (`users.py:379-545`, schema `schemas/user.py:68-98`) | `createAdminScope(payload)` `api.ts:828` — **update `role_key` union to the 4-tier keys** |
| Revoke admin | `DELETE /api/v1/admin-scopes/{admin_scope_id}` | → 204 (creator or super only — `users.py:596-616`) | `deleteAdminScope(id)` `api.ts:843` |
| Resend setup email | `POST /api/v1/admin-scopes/{admin_scope_id}/send-invite` | → `AdminScopeResponse` (`users.py:548-593`) | `sendAdminScopeInvite(id)` `api.ts:847` |
| Org subtree for scope tree render | `GET /api/v1/organizations?root_id={node}&tree=true` | → `list[OrganizationResponse]` ordered parents-before-children (`locations.py:335-364`) | `listOrganizations` `api.ts:1736` (no root_id/tree params yet — extend) |

### `[GAP]`:
- **No "share an organisation" / whitelist-a-subtree endpoint.** DESIGN §2.5 scope reach (c) ("subtrees shared with it") and the wireframe "Share an organisation" action (pin 28) have **no backend route** — `AdminScope` has no share/whitelist concept exposed. The share UI is unwireable. **Flag to SH-7 owner.**
- **No orphan-re-home on revoke.** `delete_admin_scope` (`users.py:601-616`) just deletes the scope + re-syncs Keycloak roles — it does **not** re-home orgs the admin created (§7.F5 promise). The "re-homes 3 created orgs" note (pin 52) has no backend behavior. **Flag to SH-7 owner.**
- **`AdminScopeResponse` carries no org display name / subtree counts** — the "subtree · 23 offices" chips need a separate `listOrganizations(root_id=...)` count, or a scope-summary field added.
- **Existing `AdminAccessTab` uses retired `country_admin`** (`page.tsx:556`) — must migrate to `org_admin`; the `createAdminScope` wrapper's `role_key` type must be widened.

## 5. Tokens / labels contract
- **Tier names not role keys:** "Organisation admin" / "Project admin" / "Officer admin" via a label map (never `org_admin`). Track shown as "Standard grievances" / "SEAH", not `standard`/`seah` (§7.C).
- **Scope prose, not set-notation:** render "You manage the Department of Roads and every office beneath it, plus organisations you added or that were shared with you." — **no `∪` / `descendant_org_ids` / "attenuated"** on screen (§7.C).
- **Disabled-with-reason** for project_admin (F12) — not a live-then-403 button.
- **Friendly errors** — 403/422 from `create_admin_scope` via `ErrorNotice` + `formatUserFacingError` (`user-messages.ts:145`).
- **Bilingual** org node names (`<Bilingual>`); admin-role chips use `primary`/gray tokens, no banned hues, no emoji.

## 6. Data owner (backend tickets)
- **SH-7** — 4 role keys, scope reach (a/b/c) + track, `org_category` + root-creation gating, attenuated delegation. Supersedes SH-1 flat gate. Endpoints live in `ticketing/api/routers/users.py`.

## 7. Open gaps / risks for RB-2/3/4
1. **Whitelist/share endpoint missing** — the entire "Share an organisation" column is a `[GAP]`; either backend adds it or the UI drops it for v1.
2. **Orphan-re-home on revoke unimplemented** — surface the note only if backend honors it, else it misrepresents behavior.
3. **`country_admin` → `org_admin` migration** must land in the same PR as the wrapper type change, or appointments 422 on the retired key.
4. **Subtree counts / org names** for the scope tree need extra calls or a new scope-summary payload.
5. **Client `adminScope.ts` is defense-in-depth only** — never the sole gate; the server is authoritative (row-gating in `list_admin_scopes` is coarse: it returns own-vs-all, not a true subtree filter — verify SH-7 tightens it).
