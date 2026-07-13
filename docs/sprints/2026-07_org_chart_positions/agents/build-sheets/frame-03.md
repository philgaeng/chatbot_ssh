# Build sheet — Frame 03 · Officers — invite-as-result

> RB-0 deliverable. Grounds wireframe Frame 03 + atlas Surface 03 in the NOW-REAL backend.
> Governs: DESIGN §4.1 (invite-as-result), §3 `officers/` subtree, §7.C (labels), D2.
> Surface (IA §2.1): **Settings ▸ Organisation ▸ Officers ▸ Invite officer** (also reached from Projects ▸ Staffing, Frame 05 — same component).
> Data owner: **OC-03** (position→role/scope pre-fill + resolver) · invite validation **SH-3**.

---

## 1. Visual ref

- **Wireframe:** `settings-wireframes.html` §`#f3` (lines 725–786). Pins 8–12.
- **Atlas:** `settings-state-atlas.html` §`#s3` (lines 410–469) — loading / error(no default role) / prerequisite(S5) / confirm / partial-invite-guard.
- **Layout & states (the make-or-break):** Three always-visible inputs — **Office** (tree picker), **Position** (filtered by the office's `unit_type`), **Email** — then a human-readable **outcome card** ("This will create: SDE, Jhapa Division Office → acts as Site Safeguards Focal Person *(from position: SDE)* → covers Jhapa district *(from office territory)* → on KL Road project"). Role/org/scope are pre-filled and **hidden behind a collapsed "▸ Adjust role, area, or project"** disclosure. An **override badge** appears on a line only when Adjust changes a matrix default. Two variants: (a) office-not-on-project → inline "Link it and continue" warn bar (kills seam S5); (b) Adjust-open → override badge + "overridden by you" provenance. States: skeleton card while resolving; `ErrorNotice` when the position has no default role ("choose a role manually — Adjust"); a one-line **confirm** before the irreversible Keycloak email; all-or-nothing partial-invite guard for multi-scope.

---

## 2. Component subtree (DESIGN §3 `officers/`)

```
InviteOfficer.tsx            [refactor]  orchestrator/state machine — rebuild of the invite path in
   │                                     OfficerModals.tsx `InviteOfficerModal` (lines 42–165). Today a
   │                                     role-first FORM; must become office→position→outcome card (D2/F5/F21).
   ├─ (inputs)  Office picker  [new]     tree/combobox over GET /organizations?tree=true (see §4). Filters
   │                                     Position options by the office's `unit_type`.
   ├─ (inputs)  Position picker [new]    over GET /position-types; option list constrained to positions whose
   │                                     `allowed_unit_types` includes the office's `unit_type` (pin 9).
   ├─ InviteOutcomeCard.tsx    [new]     the "This will create …" card (D2 — the whole point).
   │    ├─ ProvenanceHint.tsx  [new]     "from position: SDE" / "from office territory" (shared/, §3).
   │    └─ OverrideBadge.tsx   [new]     renders ONLY when Adjust changes a matrix default (D2).
   ├─ InviteAdjustDisclosure.tsx [refactor] role/org/scope editable behind "Adjust"; extracted from
   │                                     OfficerJurisdictionForm.tsx (OfficerJurisdictionFields, lines 414–666).
   ├─ (S5 branch) LinkOrgToProject inline action  [new]  "Link it and continue" (POST project↔org, §4).
   └─ ConfirmInvite step       [new]     one-sentence summary before Send (atlas Surface 03 "Confirm" tile).

shared/  Bilingual.tsx        [keep]     EXISTS at components/shared/Bilingual.tsx — use for office/position names.
         RoleLabel.tsx        [new]      slug → catalog display_name for "acts as {role}".
         ErrorNotice.tsx      [new]      wraps lib/user-messages.ts `formatUserFacingError` (user-messages.ts:145).
```

**Existing → reuse/replace map:** `OfficerModals.tsx::InviteOfficerModal` (role dropdown + `OfficerJurisdictionFields` + direct `inviteOfficer()`), `OfficerJurisdictionForm.tsx` (`useOfficerJurisdictionState` / `OfficerJurisdictionFields`, project-first field order, the S5 dead-end banner at **lines 570–574**), and `ProjectOfficerModal.tsx` (the Projects-side invite, lines 18–237, `lockOrganization`/`lockProject`) all become the Adjust-disclosure internals + the S5 fix. The jurisdiction state hook is worth keeping as the Adjust engine; the *outer* form is replaced by the office→position→card machine.

---

## 3. Governing interaction rules (§4.1)

1. **Position is the choice, role is a result (F21).** No role is pre-selected. The outcome card renders **only after** (office + position) are both chosen; until then "Send invite" is disabled.
2. **Resolve the outcome** from the position matrix + office territory: `role ← position_type.default_role_key`; `organisation ← chosen tree node`; `scope ← office.territory_location_code (+ territory_includes_children)`; `project ← project(s) the office is linked to`. This mirrors the server pre-fill in `officer_positions.py:135–144` — **the client shows what the server will compute**, it does not re-derive access.
3. **Provenance on every value** (`ProvenanceHint`): "from position", "from office territory". Admin trusts the card without opening Adjust (pin 10).
4. **Adjust (collapsed):** opens role/org/scope as editable fields. Changing a value *away from the matrix default* stamps `OverrideBadge` on that line and flips provenance to "overridden by you". This is the **only** place the badge shows (pin 12; doc 16 §4).
5. **S5 branch (kill the dead-end):** if the office is not linked to the resolved project, do **not** show the old empty-picker banner (`OfficerJurisdictionForm.tsx:570–574`). Show "Jhapa Division Office isn't on KL Road yet. **[Link it and continue]**" → one click links org↔project inline, then the card completes (pin 11, atlas Surface 03 tile 3).
6. **Confirm before the irreversible Keycloak email (F21):** a one-sentence summary step ("Send invite to r.thapa@dor.gov.np? → as SDE, Jhapa Division Office · Site Safeguards Focal · Jhapa — this emails a set-password link, it can't be un-sent") precedes Send (atlas Surface 03 tile 4).
7. **Multi-scope = all-or-nothing (SH-3 / O10):** if the invite spans several locations the card lists all scopes and the UI must present **one combined result, never N partial rows**. Today `InviteOfficerModal` does invite-then-loop-`addScope` (OfficerModals.tsx:86–105) — this is **not** transactional and can leave partial scopes on failure. See §5.
8. **Dual-hat collision (email already an officer):** the identity call (`POST /users/invite`) provisions Keycloak and **409s if the user already exists** (surfaced today as "`{email} already exists.`", OfficerModals.tsx:109). But `POST /users/{id}/positions` is **additive** — it mints another position/role/scope for an existing officer without touching Keycloak (officer_positions.py:104–175, docstring lines 14–16). So the flow must branch: **new email → invite (Keycloak) path; existing officer → "add a position" path** (assign-position, no email). RB-4 owns this routing decision.

---

## 4. Concrete endpoints

All under `/api/v1`. Method · path · payload → response (source file:line).

| # | Endpoint | Payload | Returns | Source |
|---|---|---|---|---|
| Office picker | `GET /organizations?tree=true&root_id={id}&active_only=false` | query | `OrganizationResponse[]` incl. `parent_organization_id`, `org_category`, `unit_type`, `territory_location_code`, `territory_includes_children`, `display_name_ne`, `email`, `address` | `locations.py:335–363`; resp model `locations.py:243–262` |
| Position picker | `GET /position-types?workflow_track={t}&owner_organization_id={o}` | query | `PositionTypeResponse[]` incl. `position_key`, `display_name`, `display_name_ne`, `allowed_unit_types`, `default_role_key`, `reports_to_position_key`, `visibility_mode`, `workflow_track`, `owner_organization_id` | `position_types.py:154–169`, model `86–101` |
| Role label | `GET /roles?kind=operational&workflow_track={t}` | query | `RoleResponse[]` (`role_key`, `display_name`, `workflow_scope`, `permissions`, `steps_count`, `officers_count`) | `users.py:142–160` |
| **Assign position** (existing officer / add-a-position) | `POST /users/{user_id}/positions` | `PositionAssignRequest` = `{position_type_id, organization_id, role_key?, location_code?, includes_children?, project_id?, project_code?, package_id?, reports_to_user_id?}` | `OfficerPositionResponse` (201) | `officer_positions.py:104–175` |
| Invite (new officer + Keycloak) | `POST /users/invite` | `OfficerInviteRequest` = `{email, role_key, organization_id, location_code?, project_id?, project_code?, package_id?, includes_children?, temp_password?}` | `OfficerInviteResponse{ok,email,message}` (201); **409 if Keycloak user exists** | `users.py:1326–1400` |
| Invite preflight (SMTP/Keycloak readiness) | `GET /users/invite/preflight` | — | `KeycloakInvitePreflightResponse{configured, keycloak_reachable, smtp_configured, missing_smtp_fields, email_action_supported, message}` | `users.py:1313–1323` |
| Add extra scope (multi-location today) | `POST /users/{user_id}/scopes` | `ScopeCreate` | `ScopeResponse` (201); 409 on cross-org / dup | `users.py:990–1084` |
| **S5 link org↔project** | `POST /projects/{project_id}/organizations/{organization_id}` | path | link row | `locations.py` header lines 21–23 (verify body shape in RB-2) |

**Frontend wrapper status (`channels/ticketing-ui/lib/api.ts`):**
- Present: `inviteOfficer` (2348), `resendOfficerInvite` (2355), `addScope` (2236), `listOrganizations` (1736), `getOrgRoles` (1923), `listProjects`, `listPackages`.
- **`[GAP]` MISSING wrappers — RB-4 must add:**
  - `assignOfficerPosition(userId, PositionAssignRequest)` → `POST /users/{id}/positions` — **the core of this frame, no wrapper exists.**
  - `listPositionTypes(track?, owner?)` → `GET /position-types`.
  - `invitePreflight()` → `GET /users/invite/preflight`.
  - `linkProjectOrganization(projectId, orgId)` → `POST /projects/{id}/organizations/{orgId}` (verify one doesn't already exist under another name).
- **`[GAP]` `OrganizationItem` type is incomplete** (api.ts:1581–1588): only `organization_id, name, country_code, is_active, created_at, updated_at`. The backend already returns `parent_organization_id / org_category / unit_type / territory_location_code / territory_includes_children / display_name_ne / email / address` — the office picker **cannot** filter positions by `unit_type` or show territory provenance until these fields are added to the type and `listOrganizations` passes `tree=true`.
- **`[GAP]` no transactional multi-scope invite endpoint.** SH-3 spec says multi-location invite is one server transaction; today the client fans out `inviteOfficer` + N×`addScope` (OfficerModals.tsx:86–105), which is not atomic. Either a server-side batch invite is added (SH-3) or the UI must present the partial-failure guard (atlas tile 5) honestly. Data owner: **SH-3**.

---

## 5. Tokens / labels contract (§7.C)

- **Labels, never slugs.** "acts as **Site Safeguards Focal Person**" via `RoleLabel` (resolve `role_key`→`RoleResponse.display_name`); position via `display_name`, office via `name`. No `role_key`, `unit_type`, or `default_role_key` string ever renders (today `OfficerJurisdictionForm.tsx:456,578` print raw `location_code`/`org_id` in `font-mono` and `DEFAULT_ROUTING_ORG_ROLE.replace(/_/g," ")` — **do not carry these over**).
- **Bilingual:** wrap office + position names in `components/shared/Bilingual.tsx` (`display_name` / `display_name_ne`, `name` / — ). EN fallback when `_ne` absent; **never fabricate** (D4). The wireframe shows "Jhapa Division Office / झापा…".
- **Friendly errors:** every failed mutation (invite 409, no-default-role 422, S5, partial-scope) routes through `ErrorNotice` → `formatUserFacingError` (`lib/user-messages.ts:145`). No raw `API 409 {…}`. Replace the ad-hoc `msg.includes("409")` string check (OfficerModals.tsx:109) with the shared formatter.
- **Colors via `lib/design-tokens.ts`** (`primary`/`danger`/`warning`/`success`, exports at design-tokens.ts:56–95). **No banned hues / no emoji.** The current invite modal uses raw `bg-blue-600`, `text-amber-600`, and even `accent-purple-500` (OfficerJurisdictionForm.tsx:472 — **banned purple**, must go). Override badge = `warning`; provenance = `text` muted; confirm = `primary`.

---

## 6. Open gaps / risks for RB-2/3/4

1. **[GAP · api.ts]** No `assignOfficerPosition` / `listPositionTypes` / `invitePreflight` wrappers; `OrganizationItem` lacks tree fields. Blocks the whole office→position→card flow until added. (Owner: RB-4 + OC-03/OC-01 shapes already exist server-side.)
2. **[GAP · SH-3]** Multi-location invite is not transactional on the current client path; either add a batch invite endpoint or surface the all-or-nothing guard truthfully.
3. **Dual-hat routing decision (RB-4):** the flow must choose invite (Keycloak, 409 on existing) vs assign-position (additive) based on whether the email is already an officer. There is no single endpoint that does both — client orchestration required. `list_officer_roster` / `GET /users/{id}/positions` can detect an existing officer before choosing the path.
4. **Position→office `unit_type` filter is client-side only.** `GET /position-types` has no `unit_type` query param; the client must filter by `allowed_unit_types` ⊇ office `unit_type`. Correct per pin 9, but depends on gap #1 (org `unit_type` field).
5. **No-default-role path:** `officer_positions.py:136` sets `role_key = body.role_key or pt.default_role_key`; if both are null the role catalog lookup 404s (`officer_positions.py:157–159`). The UI must catch that and show the atlas "choose a role manually — Adjust" state, not a raw 404.
6. **Confirm step & provenance are net-new UX** with no backend dependency — pure RB-3 build, low risk.
