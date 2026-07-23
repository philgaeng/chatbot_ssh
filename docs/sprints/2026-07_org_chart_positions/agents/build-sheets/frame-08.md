# Build sheet — Frame 08 · Roles & permissions

> RB-0 deliverable. Grounds wireframe Frame 08 + atlas Surface 08 in the NOW-REAL API.
> Spec: DESIGN §4.4 (archetype→"acts as" + grouped permissions + usage + org-scoped catalog). IA: Workflows & roles ▸ Roles. Data owner: roles model (existing); **SH-7** owning-level chips; **SH-5** delete guard.

---

## 1. Visual ref

- **Wireframe:** `settings-wireframes.html` Frame 08 (lines 1157–1240). **Atlas:** `settings-state-atlas.html` Surface 08 (lines 698–729).
- **Layout:** Leads with a **concept diagram** ("How a role fits together"): `Position type —default role→ Role —bound to→ Workflow step` and `Officer —holds→ Role —grants→ Permissions`. Below, a two-pane master/detail: left = **Role catalog** list (row = label + **owning-level chip** "System · everywhere" / "Custom · DoR & below" / "Custom · Jhapa district & below" + usage "N steps · M officers", amber ⚠ when held-but-unbound) + `New role`. Right = **Role editor**: name + System/Custom + track chips; **"Its job in a step"** dropdown reusing the exact cast vocabulary (Handles it / Oversees / Kept informed / Can view; GRC panel & SEAH handler are "Handles it" specialisations); a **grouped plain-language permission picker** (Cases: View / Acknowledge / Add notes / Escalate / **Add · reassign officers** / Resolve · GRC: Convene / Decide · SEAH: Access · Reports: View / export); a "Default area" info note (invite-time only, not editable here); "Used by" line.
- **States (atlas 08):** _loading_ (skeleton; usage counts compute as rows land); _empty custom_ ("No custom roles — TOR starter set already here"); _delete-blocked_ (ErrorNotice "Can't delete … used on 1 step, held by 3 officers"); _system-role locked_ (permission checkboxes read-only, scopebox "set by a super admin").

---

## 2. Component subtree (DESIGN §3, `components/settings/workflows/`)

```
RoleCatalog                   [extract]  ← page.tsx RolesTab (400) — list + usage + track filter + New
  RoleEditor                  [extract]  ← page.tsx RoleEditModal (143) + RoleCreateModal (294)
    "acts as" preset          [refactor] archetype→"acts as" (F20); shared vocab with StepCast (Frame 04)
    grouped permission picker  [new]     Cases / GRC / SEAH / Reports plain-language groups
  RoleLabel                   [new/shared] slug → catalog display_name (F11)
  SeverityBadge               [new/shared] "⚠ held but unbound" / usage severity text+dot
  shared/Bilingual            [new]      EN / देवनागरी role label (see GAP)
```

**Replaces (god-file):** `RolesTab` (page.tsx:400–~540), `RoleCreateModal` (294), `RoleEditModal` (143), `ORG_ROLE_COLORS` map (280) and `workflowBadge` purple literal (436). The concept diagram + org-scoped chips + grouped permission picker are net-new (no god-file equivalent).

---

## 3. Governing interaction rules

- **Role fields (`ticketing.roles`, `models/user.py:57-76`):** `display_name` + `role_key` (slug), `workflow_scope` (**track**: Standard/SEAH/Both), `jurisdiction_mode` (invite-time area default — field/country/global), `permissions` (JSON capability list), `role_kind` (operational/admin), `role_origin` (system vs custom), `owner_organization_id` (NULL = global).
- **"acts as" preset, not raw strings (§4.4, F20):** replaces the "Archetype" dropdown (`RoleCreateModal` archetype select, `page.tsx:364-371`). `GET /roles/archetypes` provides preset `{key,label}`; picking one pre-fills `permissions` server-side (`permissions_for_archetype`, `users.py:186-188`). Then the grouped picker fine-tunes. Use the **same words as the step cast**.
- **Dangerous caps hidden:** `users:invite`, `settings:write`, `projects:manage` never appear on operational roles (server `validate_operational_permissions`, `users.py:189,261`). Admin `role_kind` roles editable by super_admin only (`users.py:226`).
- **Org-scoped catalog (SH-7, §4.4):** list filtered to `owner IS NULL OR owner ∈ admin subtree` (`apply_catalog_scope`, `users.py:155`). Owning-level chip = System/global vs "DoR & below" vs "Jhapa district & below" — see §6 GAP (chip data not in response). Author's scope stamped on create via `catalog_owner_for` (`users.py:203`).
- **Usage guard rails + delete guard (SH-5):** each row shows "Used on N steps · M officers" (`steps_count`/`officers_count` in RoleResponse); held-but-unbound (officers>0, steps=0) warns; **delete blocked** while referenced — `DELETE /roles/{id}` returns **409** with `{message, steps_count, officers_count}` (`users.py:288-297`). SH-5 counts *all four* cast tiers (`_role_usage_counts`, `users.py:85-113`), so a role used only as supervisor/informed/observer is also protected.
- **Who manages (§4.4, §2.5):** super_admin authors global; org_admin (own track) authors scoped; project_admin/officer_admin *consume* only. System-role permissions super_admin-only (`users.py:229`). Create gated by `require_settings_write(CREATE_OPERATIONAL_ROLE, track=)` (`users.py:175`).
- **Two knobs not conflated:** `jurisdiction_mode` is the invite-time default only; actual per-officer area lives in `officer_scopes` — surface as an info note, never edited here (wireframe blue infobar, line 1225).

---

## 4. Concrete endpoints (real — `ticketing/api/routers/users.py`; wrappers `lib/api.ts`)

| Action | Method + path | Payload | Response | Wrapper |
|---|---|---|---|---|
| List roles | `GET /api/v1/roles?kind=operational\|admin&workflow_track=standard\|seah` | — | `GrmRole[]` (SH-7 scoped; incl. `steps_count`, `officers_count`) | `listRoles` (754) |
| List "acts as" presets | `GET /api/v1/roles/archetypes` | — | `{key,label}[]` | `listRoleArchetypes` (770) |
| Create role | `POST /api/v1/roles` | `{display_name, role_key?, workflow_scope, jurisdiction_mode?, archetype?, permissions?, description?}` | `GrmRole` (201); **422** reserved/invalid key; **409** dup key | `createRole` (774) |
| Update role | `PATCH /api/v1/roles/{id}` | `{display_name?, description?, workflow_scope?, jurisdiction_mode?, permissions?}` | `GrmRole`; **403** system-perm/track-gated | `updateRole` (853) — see GAP |
| Delete role | `DELETE /api/v1/roles/{id}` | — | 204; **409 SH-5** `{message, steps_count, officers_count}` when in use; **403** system role | `deleteRole` (868) |

`GrmRole` (`lib/api.ts:737-752`): `role_id, role_key, display_name, description, workflow_scope, jurisdiction_mode, permissions, role_kind?, role_origin?, steps_count?, officers_count?, created_at, updated_at`. **No `owner_organization_id`, no `display_name_ne`.**

`RoleCreate`/`RoleUpdate` schemas (`ticketing/api/schemas/user.py:30-45`): both accept `permissions: list[str] | None` and `RoleCreate` accepts `archetype` (default `field_actor`).

---

## 5. Tokens / labels contract

- **Labels not slugs (F11):** `RoleLabel` renders `display_name`; the `role_key` slug shown only as a muted "was …" hint (atlas 08 bilingual/was pattern). RoleCreateModal's mono-slug input (`page.tsx:350-352`) becomes auto-derived + de-emphasised.
- **Colors via `design-tokens.ts`:** kill `workflowBadge` purple ("Both" → `bg-purple-100`, `page.tsx:436`) and `ORG_ROLE_COLORS` banned hues. Track chip = blue Standard / red SEAH / neutral Both. Usage warning via `SeverityBadge` text+dot, not amber-only. No emoji (replace ⚠/✓/☐ glyphs with Lucide via `@/lib/icons`).
- **Friendly errors:** 409 delete-in-use → `ErrorNotice` "Can't delete '{role}'. It's used on N step(s) and held by M officer(s). Unbind it first." (from the structured 409 body, not raw JSON). 409 dup key + 422 reserved key likewise via `formatUserFacingError`.
- **Empty-state copy (F10):** replace the current developer copy "Run Alembic migrations and seed (`mock_tickets --reset`) so `ticketing.constants.grm_role_catalog` is applied" (`page.tsx:479-483`) with the atlas copy "The TOR starter set is already here — add a custom role only if a job needs different permissions."
- **`<Bilingual>`** on role labels where `_ne` present — blocked by GAP #3 below.
- **Track glossed** "Standard grievances / SEAH"; "acts as" glossed inline (§7.C).

---

## 6. Data owner + open gaps / risks

**Owners:** roles model = existing `ticketing.roles` (`models/user.py`). Owning-level chips = **SH-7** (`owner_organization_id` + `apply_catalog_scope`/`catalog_owner_for`). Delete guard = **SH-5** (`_role_usage_counts`, all four tiers). "acts as" presets + permission validation = `ticketing/constants/role_archetypes.py`.

**GAPs / risks for RB-2/3/4:**
1. **`[GAP]` Owning-level chip has no response field.** The model carries `owner_organization_id` (`user.py:76`) but **`RoleResponse` omits it** (`_role_to_response`, `users.py:116-132`; `GrmRole` type has no owner). The wireframe's "System · everywhere / Custom · DoR & below / Custom · Jhapa district & below" chip **cannot render** without (a) adding `owner_organization_id` (+ a resolved org display label / "& below" derivation) to `RoleResponse`, and (b) an org-name lookup. Backend ticket: extend RoleResponse under SH-7.
2. **`[GAP]` `updateRole` wrapper omits `permissions`.** Backend `PATCH /roles/{id}` accepts `permissions` (`RoleUpdate.permissions`, `schemas/user.py:45`; applied `users.py:259-264`), but the typed wrapper `updateRole` (`lib/api.ts:853-866`) only sends name/description/scope/jurisdiction. The grouped permission picker's "save" needs the wrapper extended to pass `permissions: string[]`. Pure client fix, no backend change.
3. **`[GAP]` No permission-catalog endpoint.** The grouped picker (Cases/GRC/SEAH/Reports options) has no server source of truth for the option set + labels — `validate_operational_permissions` validates but doesn't enumerate. RB must either hardcode the grouped capability list client-side (in `lib/labels.ts`, kept in sync with `role_archetypes.py`) or add a `GET /roles/permissions-catalog` endpoint. Recommend the endpoint to avoid drift.
4. **`[GAP]` Role bilingual (`_ne`).** No `display_name_ne` on `ticketing.roles` (same gap as Frame 04). `<Bilingual>` degrades to EN-only until a column + response field ship.
5. **Risk — "acts as" is create-only today.** `archetype` is a `RoleCreate` field (`schemas/user.py:35`) but not `RoleUpdate`; picking a new preset on an existing role re-derives permissions client-side then PATCHes `permissions`. Confirm this matches product intent (preset is a starting point, not a stored attribute).
6. **Risk — track semantics.** `workflow_scope` values are `"Standard"|"SEAH"|"Both"` (capitalised, `users.py:243`), while the track filter param is lowercase `standard|seah` — the mapping must live once in `lib/trackFilter.ts` to avoid the existing 4-way drift (`page.tsx:414-418`).
