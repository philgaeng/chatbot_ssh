# Brief — Roles catalog cleanup (for a fresh agent)

> **Status:** open (unstarted) · **Owner:** settings/roles · **Size:** S–M · **Type:** UI clarity + backend parity
> **Purpose:** two small, related cleanups to the operational **Roles catalog** (Settings → Workflows, roles & permissions → Roles & permissions), surfaced during a manual review. Self-contained — read this + the linked specs and you can start immediately. Both mirror patterns **already shipped this session** (see §Precedent), so this is "copy the position pattern to roles," not new design.

---

## The two tasks

### Task A — Rename the "Archetype" field → "This role acts as"

**Why:** in the New/Edit operational role modal, the field is labelled **"Archetype"** — jargon. A reviewer asked "what is the archetype?" — exactly the confusion the redesign flagged. It's a **permissions preset**: picking one pre-fills the role's `permissions` from a template (`ticketing/constants/role_archetypes.py`). The redesign (F20) calls to relabel it **"This role acts as"**, using the same plain-language vocabulary as the workflow step cast (Handler / Supervisor / Informed / Viewer / GRC committee / SEAH handler).

- **Spec:** `DESIGN-settings-redesign.md` §4.4 (F20 — *"the jargon 'archetype' is replaced by 'this role acts as', using the same vocabulary as the step cast"*); `docs/ticketing_system/11_roles_and_permissions.md` §3.4.
- **Scope:** **label only** — the field values and the `archetype` payload key are unchanged. Do **not** rename the API field or the `role_archetypes.py` keys.
- **Where:** `channels/ticketing-ui/components/settings/roles/RoleCreateModal.tsx:87` (the `Archetype` label). Check `RoleEditModal.tsx` for the same label. The option labels already come from `listRoleArchetypes()` (`ARCHETYPE_LABELS`) — leave them.
- Optional polish: the values read "Field actor (L1-style)" etc.; the spec's "acts as" framing is Handler/Supervisor/Informed/Viewer. Keep the existing option labels unless you also want to align them (out of scope for the minimal relabel).

### Task B — Remove the user-facing "Role key (slug)" field; server-mint it

**Why:** the create modal shows a **"Role key (slug)"** input ("auto-generated if empty"). It creates confusion — admins shouldn't author a slug. Same decision as position types this session: **remove the field; always server-mint the key.**

**⚠️ Critical constraint — the key must still be generated and stored, never dropped.** `role_key` is a load-bearing **soft reference** (`String(64)`, no FK), referenced by:
- `workflow_steps.assigned_role_key` + the JSON tier fields (`supervisor_role`, `informed_roles[]`, `observer_roles[]`) — `ticketing/models/workflow.py`
- `position_types.default_role_key` — `ticketing/models/position_type.py:63`
- `officer_scopes.role_key`, `admin_scopes.role_key` — `ticketing/models/*` (grep `role_key.*mapped_column` to confirm the full set)

So this is the **position_key situation exactly**: drop *user authorship*, keep the generated key. **Do not** switch anything to the UUID PK — that would make seeds/refs unreadable and fight the repo's string-key architecture (this was explicitly decided for `position_key`).

**Backend** (`ticketing/api/routers/users.py` `create_role`, `ticketing/api/schemas/user.py` `RoleCreate`):
- `RoleCreate.role_key` is **already `str | None`** and `create_role` already auto-slugs: `role_key = (body.role_key or slugify_role_key(body.display_name)).strip().lower()`. **But it 409s on collision** (two roles with the same name → same slug). Since the admin no longer sees/resolves the key, add a **uniqueness suffix** (`_2`, `_3`…).
- **Copy `ticketing/api/routers/position_types.py::_unique_position_key` verbatim as `_unique_role_key`** (slugify + suffix-until-unique), and use it. Keep the existing guards: reject reserved `ADMIN_ROLE_KEYS`, keep `slugify_role_key`'s fallback for empty/non-ASCII titles.
- Recommended (matches what we did for `PositionTypeCreate`): **remove `role_key` from `RoleCreate` entirely** so it can never be user-supplied. Seeds construct `Role(...)` directly and are unaffected.

**Frontend** (`channels/ticketing-ui/components/settings/roles/RoleCreateModal.tsx`):
- Remove the `roleKey` state (:27), the `role_key: roleKey.trim() || undefined` payload line (:46), and the "Role key (slug)" field (:73–74).
- `RoleEditModal.tsx`: `role_key` stays **immutable** — showing it read-only is fine; do not add an editable field.
- `channels/ticketing-ui/lib/api.ts`: drop `role_key` from the `RoleCreate` type (mirror the `PositionTypeCreate` change).

**Tests:** grep `tests/ticketing` for role-create tests that pass/assert `role_key`; move them to the minted-key contract (assert the response carries a server-minted slug; add a "two same-named roles → distinct suffixed keys" case). Mirror what `tests/ticketing/test_position_types.py` now does.

---

## Precedent to copy (shipped this session — do the same for roles)

**`position_key` removal** — commit `32e80792` "position types — … server-mint the identifier":
- `PositionTypeCreate` dropped `position_key`; `_unique_position_key(db, display_name)` mints a unique, non-null slug with a `_2`/`_3` suffix; the "Identifier" field was removed from the editor; `test_position_types.py` moved to the minted-key contract (incl. `test_duplicate_title_gets_unique_key`); live-verified (create → minted key; same title → `_2`).
- Read that commit's diff first — Task B is the same shape.

## Related context from this session (so you're not surprised)

- **`archetype` now persists on the role.** It used to be discarded after deriving permissions; `create_role` now stores `body.archetype` (`users.py`), and it drives the **archetype grouping** of the position-type default-role picker. Migration `b6d8f0h2`.
- **`actor_category` added to roles** (government/donor/…) — migration `c8e0g2i4` — drives the position-type office-type filter and the roles-catalog "actor type" filter.
- **StepCast** was built (workflow step "who's involved" cast). See `followups/step-cast-why-excluded-and-role-ne.md`.
- Session commits: `db8fad11` (role classification), `32e80792` (position types), `48310cf1` (StepCast), plus the roles-catalog filters commit.

## Relevant specs & files (start here)

| What | Where |
|---|---|
| Roles catalog spec (role_key, archetypes, who-manages) | `docs/ticketing_system/11_roles_and_permissions.md` §3 (esp. §3.4) |
| "Archetype → acts as" rename + role catalog surface | `docs/sprints/2026-07_org_chart_positions/DESIGN-settings-redesign.md` §4.4 (F20); build sheet `agents/build-sheets/frame-08.md` |
| Archetype definitions + labels | `ticketing/constants/role_archetypes.py` |
| Role create endpoint + slugify + reserved keys | `ticketing/api/routers/users.py` (`create_role`, `slugify_role_key`, `ADMIN_ROLE_KEYS`) |
| RoleCreate / RoleResponse schemas | `ticketing/api/schemas/user.py` |
| **Pattern to copy** (`_unique_position_key`, no-key create contract) | `ticketing/api/routers/position_types.py` |
| Create/Edit modals | `channels/ticketing-ui/components/settings/roles/RoleCreateModal.tsx`, `RoleEditModal.tsx` |
| Frontend types | `channels/ticketing-ui/lib/api.ts` (`RoleCreate`, `GrmRole`) |

## Acceptance criteria

- No user-facing **"Role key (slug)"** field; creating a role with just a display name mints a unique, non-null `role_key` server-side; two same-named roles get distinct (`_2`) keys — verified against the live API (mirror the position_key check).
- Existing references to `role_key` (workflow step casts, `default_role_key`, officer/admin scopes) are unaffected.
- The create/edit modal reads **"This role acts as"** instead of "Archetype"; values/behaviour unchanged.
- `tsc --noEmit` clean; full `tests/ticketing` green (run in-container: `dcg exec -T ticketing_api python -m pytest tests/ticketing -q`); `grm_ui` rebuilt + healthy.

## Gotchas

- **Never** expose or switch to the UUID PK — keep the human-readable minted `role_key` (soft-ref architecture; same call as position_key).
- Keep the **reserved-key** guard (`ADMIN_ROLE_KEYS`) and `slugify_role_key`'s empty/non-ASCII fallback.
- `role_key` is **immutable** after create (like `position_key`) — the edit modal must not offer to change it.
- All build/run/migrate/seed go through **Docker** (`dcg = docker compose --env-file env.local -f docker-compose.yml -f docker-compose.grm.yml`); source is baked into images, so rebuild `backend`/`ticketing_api`/`grm_ui` after changes (see how this session applied each step).
