# Build sheet — Frame 11 · Officers — directory & lifecycle at scale

> RB-0 deliverable. Grounds wireframe Frame 11 + atlas Surface 11 in the NOW-REAL backend.
> Governs: DESIGN §7.F1 (officer lifecycle), §7.F3 (scale), §3 `officers/` subtree, §5.1 (position-title display).
> Surface (IA §2.1): **Settings ▸ Organisation ▸ Officers** (directory) + Manage modal.
> Data owner: **OC-03** (transfer / dual-hat / position rows) · dual-hat + open-case guard → **RB-4** (see gaps).

---

## 1. Visual ref

- **Wireframe:** `settings-wireframes.html` §`#f11` (lines 1391–1443). Pins 45, 46, 55.
- **Atlas:** `settings-state-atlas.html` §`#s11` (lines 767–774) — loading (server-side stream) / no-matches / deactivate-blocked-by-open-cases.
- **Layout & states:** **Search-first directory** — a search box ("name, email, or position…") + filter chips (Office ▾ / Role ▾ / Project ▾, plus a **Standard/SEAH** filter only for a SEAH-capable admin) + "+ Invite officer". A table (Officer — *position title* / Office / Role / Project / Manage) with **server-side pagination** ("Showing 1–20 of 4,812 … 241 pages"). A **dual-hat officer shows each position as its own row**. The **Manage** modal exposes three first-class lifecycle actions — **Edit role & area** (staged scope rows), **Transfer** (new office/position → offer role/area re-sync; old rows end, nothing silently re-scoped), **Deactivate** (ends roles + scopes, keeps history/audit). **In-flight guard:** deactivate — and transfer for non-moving cases — first requires **reassigning the officer's open cases** (pin 55; atlas tile "Deactivate blocked").

---

## 2. Component subtree (DESIGN §3 `officers/`)

```
OfficersDirectory.tsx        [refactor]  from OfficersTab.tsx (whole file). Add: position-title column
   │                                     (§5.1), server-side search/filter/pagination (F3), SEAH filter
   │                                     gating (F4), dual-hat one-row-per-position.
   ├─ (search + filter chips) [refactor] today client-side useMemo filter (OfficersTab.tsx:110–165) →
   │                                     must move to server params (see §4 GAP).
   ├─ (table row)             [refactor] Name shows "R. Thapa — SDE" (display_name + position title,
   │                                     from OfficerRosterEntry.positions[], §5.1). RoleLabel for role.
   ├─ Pagination              [new]      server-side page controls ("1–20 of 4,812").
   └─ OfficerManageModal.tsx  [refactor] from OfficerModals.tsx `EditOfficerModal` (lines 167–466).
        ├─ (Edit) OfficerScopeTable.tsx [keep]  staged draft rows — OC-06 strength; token pass only.
        ├─ (Transfer)  TransferOfficer  [new]   new office/position → re-sync via shared review flow.
        │     └─ ReviewHoldersModal.tsx [new]   shared with Position-types D3 re-sync (Frame 06).
        ├─ (Deactivate) + open-case guard [new] reassign-open-cases-first gate (pin 55).
        └─ ReassignCasesPanel   [new]   lists the officer's open tickets, forces reassignment.

shared/  RoleLabel.tsx        [new]      slug → catalog display_name (F11).
         ErrorNotice.tsx      [new]      wraps lib/user-messages.ts formatUserFacingError (user-messages.ts:145).
         SeverityBadge.tsx    [new]      "Invited"/"Active" + the blocked-delete states as text+dot.
         Bilingual.tsx        [keep]     EXISTS (components/shared/Bilingual.tsx) — office/position names.
```

**Existing → reuse/replace map:** `OfficersTab.tsx` is the directory today (search + 5 client-side filter selects at lines 47–51 / 110–165, table at 343–459, Resend/Manage/Remove actions at 424–452). `EditOfficerModal` (OfficerModals.tsx:167–466) is the manage surface today: it does org-correction + staged `OfficerScopeTable` + `Delete officer` (326–338, 439–444) — but **has no Transfer, no soft Deactivate, and no open-case guard**. `OfficerScopeTable` (imported in OfficerModals.tsx:32–38) is kept as-is.

---

## 3. Governing interaction rules (§7.F)

1. **Search-first, server-side (F3, pin 45).** With ~5,000 staff the list must not be fully materialised + client-filtered (today's OfficersTab.tsx:110–165). Search + Office/Role/Project/track filters + pagination run server-side. Empty result is normal ("No officers match 'thapa … Ilam'", atlas tile), not an error.
2. **SEAH filter gating (F4, doc 16 §6).** The Standard/SEAH filter chip appears **only for a SEAH-capable admin**; a standard-only admin never sees that SEAH exists. People still appear in the shared directory — only SEAH *case existence* is hidden (round-3 correction, atlas Surface 13). Gate client-side on `GET /users/me/admin-context` (defense-in-depth) plus server track-scoping.
3. **Position-title display (§5.1, pin 46).** Show the officer's active position title(s), not raw role keys. Backend already returns them: `OfficerRosterEntry.positions` = `["Senior Divisional Engineer · DOR_JHA", …]` (users.py:850–863). A **dual-hat** officer (multiple active positions, doc 16 §3.3) renders **one row per position**.
4. **Lifecycle is first-class (F1, pin 46).** Manage = **Edit** (staged scope rows), **Transfer** (pick new office/position → offer role/area re-sync through the shared review-holders flow; old rows end via `DELETE /users/{id}/positions/{opid}`, **no silent re-scope** — matches `officer_positions.py:183–198` docstring), **Deactivate** (ends `user_roles` + `officer_scopes`, keeps history/audit).
5. **Open-case guard (round-2/3 fix, pin 55).** Before **Deactivate** — and before **Transfer** for cases that don't move — the flow **requires reassigning the officer's open cases first**; no ticket is left owner-less. This is a hard gate with a friendly `ErrorNotice` ("Reassign R. Thapa's 4 open cases first"). **No backend endpoint enforces this yet** (see §4/§6 GAP).
6. **Transfer re-sync shares the D3 review path.** The role/area re-sync offered on transfer routes through the same `ReviewHoldersModal` the Position-types edit uses (DESIGN D3, Frame 06) — one re-sync surface, not two.

---

## 4. Concrete endpoints

All under `/api/v1`.

| Action | Endpoint | Payload → Returns | Source |
|---|---|---|---|
| Directory list | `GET /users/roster` | — → `OfficerRosterEntry[]` incl. `positions[]`, `scopes[]`, `onboarding_status` | `users.py:747–903` |
| Officer's positions (dual-hat) | `GET /users/{user_id}/positions?active_only=true` | — → `OfficerPositionResponse[]` | `officer_positions.py:86–101` |
| End a position (transfer step) | `DELETE /users/{user_id}/positions/{officer_position_id}` | — → 204 (sets `is_active=false`; **does NOT** remove role/scope, **does NOT** guard open cases) | `officer_positions.py:178–198` |
| Assign new position (transfer target) | `POST /users/{user_id}/positions` | `PositionAssignRequest` → `OfficerPositionResponse` (201) | `officer_positions.py:104–175` |
| Edit scopes | `GET/POST /users/{user_id}/scopes`, `DELETE /users/{user_id}/scopes/{scope_id}` | `ScopeCreate` → `ScopeResponse` | `users.py:970–1114` |
| Sync Keycloak attrs | `PATCH /users/{user_id}` | `OfficerUpdateRequest{role_keys, organization_id, location_code?, sync_keycloak}` → `OfficerUpdateResponse` | `users.py:1447–1487` |
| Resend setup email | `POST /users/{user_id}/resend-invite` | — → `OfficerInviteResponse` | `users.py:1403–1444` |
| Remove officer (hard delete) | `DELETE /users/{user_id}` | — → 204 (removes DB roles/scopes + Keycloak user; **NO open-case guard**) | `users.py:1490–1523` |
| Admin context (SEAH-filter gating) | `GET /users/me/admin-context` | — → `AdminContextResponse` | `users.py:319–327` |
| Reassign a ticket (open-case guard target) | ticket reassign action | reassign event `reason_code`/`notes` | `tickets.py:1400–1455` |

**Frontend wrapper status (`channels/ticketing-ui/lib/api.ts`):**
- Present: `listOfficerRoster` (898), `resendOfficerInvite` (2355), `deleteOfficer` (2362), `updateOfficerKeycloak` (2366), `listScopes` (2232), `addScope` (2236), `deleteScope` (2244).
- **`[GAP]` MISSING wrappers — RB-4 must add:** `listOfficerPositions(userId)` → `GET /users/{id}/positions`; `endOfficerPosition(userId, opid)` → `DELETE /users/{id}/positions/{opid}`; `assignOfficerPosition(...)` → `POST /users/{id}/positions` (shared with Frame 03).
- **`[GAP]` `OfficerRosterEntry` type omits `positions`.** api.ts:883–896 has no `positions?: string[]` field, yet the backend returns it (users.py:743, format `"{display_name} · {org_id}"`). Add it — the directory's position-title column (§5.1, pin 46) cannot render without it.

**Backend `[GAP]`s (data owner tickets):**
- **`[GAP]` No server-side roster search / filter / pagination.** `GET /users/roster` returns the *entire* list with no `q` / `office` / `role` / `project` / `track` / `page` params (users.py:747–903); Frame 11's "1–20 of 4,812" and search-first premise (F3, pin 45) are unbuildable against it. Needs a new paged/filtered roster endpoint. Owner: OC-03 follow-up / SH.
- **`[GAP]` No soft "deactivate" distinct from hard delete.** Only `DELETE /users/{id}` (hard) exists; there is no "keep history/audit, end roles+scopes" deactivate as §7.F1 requires.
- **`[GAP]` No open-case guard / no officer-open-cases listing.** Neither `DELETE /users/{id}` nor `DELETE /users/{id}/positions/{opid}` checks open tickets; there is no endpoint that lists an officer's open cases to drive the "reassign 4 open cases first" gate (pin 55, atlas tile). Needs a server guard (409 with counts) + an open-cases query. Owner: **RB-4 / SH**.

---

## 5. Tokens / labels contract (§7.C)

- **Labels, never slugs.** Role column via `RoleLabel` (`role_key`→`display_name`); position via `positions[]` display titles; office via org `name`. Current OfficersTab renders roles through `roleProjectsLines(...)` (OfficersTab.tsx:113,358–363) and `location_codes` in `font-mono` (400–411) — replace the mono slug/code output with labels.
- **Text severity beside color (F11).** Status "Invited"/"Active" already text (OfficersTab.tsx:413–423) — keep, move to `SeverityBadge` and off raw `bg-amber-100`/`bg-green-100` onto `design-tokens.ts` (`warning`/`success`, exports 83–95). The missing-area highlight (`bg-amber-50/60`, OfficersTab.tsx:370) → `warning` token.
- **Friendly errors.** Delete/deactivate/transfer failures (esp. the open-case 409 once it exists) through `ErrorNotice` → `formatUserFacingError` (user-messages.ts:145). Replace the raw `confirm()` + `e.message` pattern (OfficersTab.tsx:189–206, 329–338) and the success `✓` string (228–231) with the shared components.
- **Bilingual** office/position names via `components/shared/Bilingual.tsx` (`_ne` where present, EN fallback, never fabricate — D4).
- **No banned hues / no emoji.** The current `✓` glyph and raw blue/green/amber/slate utility classes get the design-token pass.

---

## 6. Open gaps / risks for RB-2/3/4

1. **[GAP · backend, blocking F3]** No paged/filtered/searchable roster endpoint. Frame 11's search-first directory at 4,812 rows is not buildable on `GET /users/roster` as-is. Highest-risk item — flag to data owner before RB-3 builds the table.
2. **[GAP · backend, blocking F1]** No soft-deactivate and no open-case guard/query. The signature lifecycle action (deactivate with case-reassignment, pin 55) has no server enforcement; `DELETE /users/{id}` will happily orphan tickets. RB-4 must add the guard + open-cases listing; until then the UI gate is advisory only.
3. **[GAP · api.ts]** Missing `positions` field on `OfficerRosterEntry` and missing `listOfficerPositions`/`endOfficerPosition`/`assignOfficerPosition` wrappers — required for both the dual-hat one-row-per-position display and the Transfer flow.
4. **Transfer semantics (RB-4).** Transfer = end old position (`DELETE …/positions/{opid}`) + assign new (`POST …/positions`) + offer scope re-sync (shared `ReviewHoldersModal`). The end-position endpoint deliberately leaves role/scope rows intact (officer_positions.py:189–198), so the re-sync step is what actually re-scopes — sequence carefully to avoid a window where the officer holds stale + new scope simultaneously.
5. **Dual-hat rendering.** `positions[]` can be empty for legacy officers (invited-but-no-position); fall back to the role-based row (§5.1) so those officers still appear.
6. **SEAH-filter gating depends on `admin-context`.** Ensure the SEAH chip is hidden by *both* client gate and server track-scoping — a client-only hide would leak SEAH existence via the roster payload (doc 16 §6). Cross-check with Frame 13 / OC-04 leak tests.
