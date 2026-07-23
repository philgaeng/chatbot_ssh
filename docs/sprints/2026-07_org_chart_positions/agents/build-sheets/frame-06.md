# Build sheet — Frame 06 · Position types — edit & review holders

> RB-0 build sheet. Grounds wireframe Frame 06 in the NOW-REAL position-types API. Input to RB-2/3/4.
> **Data owner:** OC-02 (position_types + matrix + `owner_organization_id`). Re-sync path shared with OC-03 transfer-refresh (D3).
> **Real router:** `ticketing/api/routers/position_types.py`, mounted at prefix `/api/v1` (`ticketing/api/main.py:119`).

---

## 1. Visual ref

- **Wireframe:** `settings-wireframes.html` Frame 06 (line 992, `#f6`).
- **Atlas:** `settings-state-atlas.html` Surface 07 "Organisation — position types" (line 661) — Loading / Empty("Add the DoR set") / **Review holders (after edit)** / Bilingual. Atlas 00 applies.
- **Layout (3–5 lines):** Secondary panel under `Organisation` (sub-nav `Position types`, a set-once ~20–50-row catalog). The editor card shows fields in a 2-col grid: Title (EN), Title (Nepali), **Used at** (allowed unit types, multi), **Default role for this position** (the matrix), **This position's supervisor sees** (`visibility_mode`), **Grievance type** (`workflow_track`). Below it, an **amber "Heads up"** card appears when the default role changed: "12 officers currently hold SDE. Their role was **not** changed. [Review 12 holders →] [Leave them as they are]". Review opens a table (Officer · Current role · New default · Re-sync checkbox), overrides flagged, "Re-sync selected" runs the same `user_roles`/`officer_scopes` path, all-or-nothing per batch.

---

## 2. Component subtree (DESIGN §3, `components/settings/org/`)

```
OrganisationTab.tsx            [extract]  sub-nav shell (shared with Frame 02)
  └ PositionTypesPanel.tsx     [fold+new] the secondary panel: catalog list + matrix editor. ex-OC-05 PositionTypesTab
      ├ PositionTypeEditor.tsx [new]      display_name(_ne), allowed_unit_types, default_role_key,
      │                                   reports_to(_position_key/_locus), visibility_mode, workflow_track
      └ ReviewHoldersModal.tsx [new]      opt-in re-sync of N holders (D3); SHARED with transfer-refresh
                                          (OfficerManageModal, Frame 11)
shared/Bilingual.tsx           [new]      title EN / देवनागरी, EN fallback (D4)
shared/SeverityBadge.tsx       [new]      "Heads up" / "Warning" text + dot (F11) — the amber drift card
shared/ErrorNotice.tsx         [new]      friendly errors (F11)
shared/RoleLabel.tsx           [new]      role slug → catalog display_name for "Default role" + holder rows (F11)
```

**No current god-file source** — position types is a net-new surface (there is no `PositionTypesTab` inline in `page.tsx`). The re-sync writers already exist server-side (`ticketing/services/officer_admin.py` `upsert_user_role_row` / `create_scope_row`), so `ReviewHoldersModal` binds to those via a **new** endpoint (see §4 GAP).

---

## 3. Governing interaction rules (DESIGN §4.4, D3, doc 16 §3.2/§4)

- **`position_key` is immutable** after create (mirrors `roles.role_key`) — the editor must not offer to change it; `PATCH` ignores it (`position_types.py:74`).
- **Editing `default_role_key` never silently re-syncs holders** (doc 16 §4). The server `PATCH` has **no side effect** by design (`position_types.py:264-267`). The UI is responsible for making the drift **visible and fixable**: after a save that changed `default_role_key`, render the amber "Heads up" card and the opt-in `ReviewHoldersModal`.
- **One re-sync surface, shared with transfer-refresh (D3).** "Re-sync selected" must route through the **same** `user_roles`/`officer_scopes` refresh the officer-transfer flow uses (`OfficerManageModal`, doc 16 §3.3/§4) — do not build a second path. **Per-holder opt-in; all-or-nothing per batch.** Overrides (a holder whose current role differs from the *old* matrix default too) are flagged (`override` badge) so a deliberate exception isn't clobbered — default that checkbox **off**.
- **Matrix validation (server, 422).** `default_role_key` must exist in the role catalog **and** be track-compatible: a `both`-track position needs a role scoped `Both`/None; else the role's track must match (`position_types.py:49-57,104-134`). `allowed_unit_types` values must be in `UNIT_TYPES`. `reports_to_position_key` must exist and not equal self. `owner_organization_id` must exist. Surface each 422 via `ErrorNotice`.
- **Org-scoped catalog owning-level (§4.4).** Each row/item carries `owner_organization_id`; the list is already scoped server-side (`apply_catalog_scope`, `position_types.py:168`). Any picker that *lists* position types (invite pre-fill, Frame 03) must show the **owning level** ("System · DoR-wide · Jhapa district") and list only in-scope items. In this frame the editor **sets/inherits** `owner_organization_id` (defaulted by `catalog_owner_for` when omitted, `position_types.py:195`).
- **Delete guard.** `DELETE` returns 409 while the type is referenced by another position (`reports_count`) or held by any officer (`holders_count`) — `position_types.py:297-318`. Surface as a friendly stop, never a raw 409.

---

## 4. Concrete endpoints (all `/api/v1`, real)

| Method + path | Payload | Response / notes |
|---|---|---|
| `GET /position-types` | query: `workflow_track?` (this track + `both`), `owner_organization_id?` | `PositionTypeResponse[]`, org-scope-filtered. Auth only. `position_types.py:154`. |
| `POST /position-types` | `PositionTypeCreate` (below) | 201 `PositionTypeResponse`. Gated `MANAGE_ORG_STRUCTURE`. 409 dup key; 422 matrix. `position_types.py:172`. |
| `PATCH /position-types/{id}` | `PositionTypeUpdate` (position_key omitted/immutable) | `PositionTypeResponse`. Gated. **No holder re-sync** on `default_role_key` change. `position_types.py:225`. |
| `DELETE /position-types/{id}` | — | 204, or 409 `{message, reports_count, holders_count}`. Gated. `position_types.py:281`. |
| `GET /roles?kind=operational&workflow_track=` | — | `GrmRole[]` — the **Default role** picker source; `listRoles(...)` exists (`lib/api.ts:754`). Filter to the position's track. |

**`PositionTypeCreate` / `...Response` fields** (`position_types.py:60-101`): `position_key, display_name, display_name_ne?, allowed_unit_types[], reports_to_position_key?, reports_to_locus? (same_unit|parent_unit), default_role_key, visibility_mode (none|direct_reports|subtree)="none", workflow_track (standard|seah|both)="standard", owner_organization_id?` (+ `position_type_id, created_at, updated_at` on response).

**Holder listing (real, per-user only):** `GET /users/{user_id}/positions` (`officer_positions.py:86`) returns one officer's positions — **not** a per-position-type roster.

### `[GAP]` — endpoints this frame needs that do NOT exist
- **`[GAP] GET /position-types/{id}/holders`** — the Review-holders table needs a **roster of officers holding this position type, each with their current role vs the new default**. No such endpoint exists. Today the only holder signal is `holders_count` returned **inside a DELETE 409** (`position_types.py:305-316`) — an integer, no list, and only on delete. RB needs a new listing endpoint (owner: OC-02/OC-03).
- **`[GAP]` holder-count on the catalog list.** Frame 06 / atlas Surface 07 implies "Used by N officers" per row and the usage guard ("held but bound to no step warns"). `GET /position-types` returns **no count**. Needs an aggregate (count of active `officer_positions` per `position_type_id`).
- **`[GAP]` batch re-sync endpoint** ("Re-sync selected", all-or-nothing per batch). The writers exist (`officer_admin.upsert_user_role_row` / `create_scope_row`) but there is **no HTTP surface** that reconciles a set of holders to the new `default_role_key`. This is the D3 shared transfer-refresh path — must be exposed as one endpoint used by both `ReviewHoldersModal` and `OfficerManageModal` (owner: OC-03).
- **`[GAP]` `lib/api.ts` wrappers.** There are **no** typed wrappers for `/position-types` (CRUD) or `/users/{id}/positions` in `lib/api.ts` (grep confirms none). RB-4 must add them.

---

## 5. Tokens / labels contract (DESIGN §7.C, §7.E)

- **Labels, never slugs.** Field labels are already plain in the wireframe: "Default role for this position" (not `default_role_key`), "Used at" (not `allowed_unit_types`), "This position's supervisor sees" → render `visibility_mode` as prose ("Their direct reports' cases" / "None" / "The whole subtree"), "Grievance type" → `workflow_track` as "Standard (not SEAH)" / "SEAH" / "Both". `reports_to_locus` → "same office" / "parent office". Resolve via `lib/labels.ts`. Role values via `RoleLabel` (slug → catalog `display_name`).
- **`<Bilingual>`** on the position title; absent `display_name_ne` → "Nepali name needed" chip (never fabricated).
- **Severity text beside color.** The drift card is amber but carries a **"Heads up"** text badge (`SeverityBadge`), not color-only. Holder rows flag `override` as a text badge.
- **Colors via `design-tokens.ts`**; no banned hues, no emoji; Lucide via `@/lib/icons`; `text-gray-600` floor.
- **Friendly errors** via `formatUserFacingError` + `ErrorNotice` for the 409 delete guard and 422 matrix failures.

---

## 6. Data owner

| Path | Ticket |
|---|---|
| position_types CRUD + matrix + `owner_organization_id` + org-scope filter | **OC-02** |
| Holder roster + batch re-sync (transfer-refresh path) | **OC-03** (shared) — currently **`[GAP]`** |
| Org-scoped catalog owning-level in pickers | **SH-7** |
| Role catalog for the Default-role picker | roles model (existing, `users.py`) |

---

## 7. Open gaps / risks for RB-2/3/4

1. **The whole "Review holders" half of this frame is un-backed.** Roster listing, per-row current-vs-new role, and batch re-sync are all `[GAP]`. RB-2 cannot build `ReviewHoldersModal` against the real API until OC-02/OC-03 add (a) a holders-roster endpoint and (b) the shared re-sync endpoint. **This is the top cross-frame blocker.** Flag to the ticket owner before RB-3.
2. **"Add the DoR set" empty-state CTA** (atlas Surface 07) implies a **seed-a-starter-set** action — no such endpoint exists. Either wire it to a seed route or downgrade copy to "contact your administrator" (§7.C rule against dev copy). Confirm intent.
3. **Re-sync semantics of overrides.** The wireframe shows an overridden holder (S. Karki, PD/PIU Focal) defaulted **off**. Confirm the definition of "override" the roster endpoint returns (current role ≠ prior default) so the client can pre-check correctly.
4. **`default_role_key` picker track filter.** The picker must list only roles valid for the position's `workflow_track` (single-sourced `lib/trackFilter.ts`), matching the server's `_role_ok_for_position_track` — otherwise the user picks a role the server 422s.
5. **Next.js 16 caveat** (`channels/ticketing-ui/AGENTS.md`) — read `node_modules/next/dist/docs/` before writing components.
</content>
