# Org chart, positions, and the position→role matrix

**Status:** Agreed design (July 2026) — not yet implemented.
**Related:** [10_settings_overview.md](10_settings_overview.md), [11_roles_and_permissions.md](11_roles_and_permissions.md), [07_officer_management_and_assignment.md](07_officer_management_and_assignment.md), [12_workflows_configuration.md](12_workflows_configuration.md)

---

## 1. Problem

The Government of Nepal wants (a) the ministry org chart in the system — Ministry of Physical Infrastructure → Department of Roads → directorates, provincial and district offices — and (b) every officer on a project recorded with their exact position title and reporting line.

Until now the only place to record "this person is the SDE of Ilam Division Office" was the role catalog, so setup admins recreated the hierarchy by minting one role per position. That explodes the catalog, breaks workflow step bindings, and duplicates permissions.

**Design principle (locked):** a new role is justified only when **permissions or workflow step bindings differ** ([11 §3.1](11_roles_and_permissions.md)). The inverse rule: if two positions need the same permissions, they **share a role** — the *position* carries the title, org placement, and reporting line.

## 2. Three layers

| Layer | Holds | Size | Owner |
|---|---|---|---|
| **Org chart** — org units + position types | Ministry structure, position titles, reporting rules, office territories | Large (government-shaped) | `country_admin` (standard track), CSV import |
| **Roles** — behavior catalog | Permissions + workflow step bindings | Small (~10–15, unchanged) | As per doc 11 |
| **Matrix** — position type → role | `default_role_key` on each position type | One row per position type | `country_admin` (standard track) |

`user_roles` + `officer_scopes` remain the **enforcement truth**. Positions are descriptive and *generate* those rows at invite time; they never replace them.

## 3. Data model

### 3.1 Org tree — extend `ticketing.organizations`

| New column | Notes |
|---|---|
| `parent_organization_id` | Self-FK, nullable. Existing flat orgs become roots. |
| `unit_type` | `ministry` \| `department` \| `directorate` \| `provincial_office` \| `division_office` \| `company` \| `development_partner` |
| `territory_location_code` | Optional — e.g. Jhapa Division Road Office covers Jhapa district |
| `territory_includes_children` | Boolean, same semantics as `officer_scopes.includes_children` |

One tree; "officer belongs to DoR" becomes a subtree check. Existing `officer_scopes` / `tickets.organization_id` FKs unchanged. Territory makes an office **routable** (§5.2, invite pre-fill).

### 3.2 `ticketing.position_types` (new)

| Column | Notes |
|---|---|
| `position_type_id` | UUID PK |
| `position_key` | Slug, immutable after save |
| `display_name` | e.g. "Senior Divisional Engineer" |
| `allowed_unit_types` | JSON list — which org-unit levels this position exists at |
| `reports_to_position_key` | Default reporting rule (nullable) |
| `reports_to_locus` | `same_unit` \| `parent_unit` |
| **`default_role_key`** | **The matrix** — FK-by-key into `ticketing.roles` |
| `visibility_mode` | `none` \| `direct_reports` \| `subtree` — supervisor visibility depth (§5.3) |
| `workflow_track` | `standard` \| `seah` \| `both` — catalog filtering only |

~20–50 rows expected. Not individual seats: the system is not an HRIS; a "seat" is simply an officer holding a type at a unit.

### 3.3 `ticketing.officer_positions` (new)

| Column | Notes |
|---|---|
| `officer_position_id` | UUID PK |
| `user_id` | Officer |
| `position_type_id` | FK |
| `organization_id` | The org unit where the position is held |
| `reports_to_user_id` | **Override** (nullable) — deputation / acting arrangements |
| `is_active` | Transfers end the old row and add a new one |

Multiple active positions per officer allowed (dual-hat); each suggests its own role/scope rows at invite.

**Supervisor resolution order:** `reports_to_user_id` override → derived (holder of `reports_to_position_key` at same/parent unit) → workflow step `supervisor_role` fallback.

## 4. Matrix semantics — default, overridable

- Picking a position at invite **pre-fills** role (matrix), organization (tree), and location scope (office territory). Admin may override any field before saving.
- Saving creates standard `user_roles` + `officer_scopes` rows — assignment engine unchanged.
- Editing a position type's `default_role_key` does **not** silently re-sync existing holders; the UI offers a "review holders" prompt. Transfers likewise prompt to refresh role/scopes.
- Overrides are visible on the officer Manage modal (role differs from matrix default → informational badge).

## 5. Behaviors driven by the chart

Escalation **still targets the next workflow step's role pool** — the reporting line never redirects escalation. It drives four things:

### 5.1 Display & directory
Position title + org unit shown on officer roster, ticket assignee chips, timeline events, and reports ("SDE, Jhapa Division Office" instead of `site_safeguards_focal_person`).

### 5.2 Invite pre-fill
Org-unit tree picker → position type (filtered by `allowed_unit_types`) → role/org/scope pre-filled. One comprehensible action for low-IT-literacy admins.

### 5.3 Supervisor visibility (query layer)
Officer's **Watching** tab additionally includes tickets assigned to their reports, per the position type's `visibility_mode` (`none` / `direct_reports` / `subtree`). Senior positions should use `direct_reports` or `none` to avoid firehose; broad oversight remains the job of observer roles.

### 5.4 Prefer-own-office assignment (ranking tweak)
In `auto_assign_officer`, among scope-matched candidates: rank officers whose org unit **territory covers the ticket location** first, then least-loaded. A preference, not a filter — the province fallback ([07 §4.4](07_officer_management_and_assignment.md)) still applies.

### 5.5 Supervisor advised on escalation (notification only)
When a ticket escalates off officer X's step, X's resolved supervisor is notified (in-app; channel matrix per [12 §9](12_workflows_configuration.md)). This reuses the existing `supervisor_role` tier: the reporting line is a person-specific resolver for that tier, with `supervisor_role` as fallback.

## 6. SEAH rules

Chart is **shared for directory purposes** — SEAH officers may hold positions. But reporting-line features must never leak SEAH case existence:

- Supervisor visibility (§5.3) **never** surfaces `is_seah` tickets through reporting lines.
- Escalation supervisor notification (§5.5) is **suppressed** on SEAH tickets unless the supervisor independently holds a SEAH role.
- SEAH ticket visibility remains exactly as [11 §9](11_roles_and_permissions.md).

## 7. Ownership & permissions

| Action | `project_admin` | `country_admin` (standard) | `country_admin` (seah) | `super_admin` |
|---|---|---|---|---|
| Edit org tree / CSV import | ❌ | ✅ | ❌ | ✅ |
| Create/edit position types + matrix | ❌ | ✅ | ❌ (may propose SEAH-track types — TBD) | ✅ |
| Assign positions when inviting/staffing | ✅ own scope | ✅ | ✅ SEAH officers | ✅ |
| Override role/scope vs matrix default | ✅ | ✅ | ✅ | ✅ |

Follows the locations pattern, but at **country tier**, not platform.

## 8. Migration / cleanup

Existing per-position custom roles (created by the setup officer) should be unwound:

1. Create position types matching those titles; point each at the correct catalog `role_key`.
2. For each officer holding a per-position role: add `officer_positions` row, re-point `user_roles` to the catalog role, keep scopes.
3. Delete the orphaned custom roles (delete guard already blocks in-use rows).
4. Re-bind any workflow steps that reference per-position keys to catalog keys **before** step 3.

## 9. API sketch

| Method | Path | Access |
|---|---|---|
| `GET/POST/PATCH` | `/api/v1/organizations` (+ `parent_organization_id`, `unit_type`, territory) | Existing router, extended |
| `POST` | `/api/v1/organizations/import` | Org tree CSV, `country_admin` standard |
| `GET/POST/PATCH/DELETE` | `/api/v1/position-types` | `country_admin` standard / `super_admin` |
| `GET/POST/DELETE` | `/api/v1/users/{id}/positions` | Invite/Manage modal |
| `GET` | `/api/v1/users/{id}/supervisor` | Resolver (override → derived → step fallback) |

## 10. Open questions

| Question | Current lean |
|---|---|
| Nepali display names on org units / position types | Add `display_name_ne` columns from day one; cheap now, painful later |
| Vacancy tracking ("no Safeguards Focal at unit X") | Not a table — derive as an admin report; revisit if government insists on seats |
| SEAH-track position types — who authors them | Standard-track admin owns catalog; SEAH-track proposes — confirm with SEAH stakeholders |
| Historical positions (transfers audit) | `officer_positions.is_active` + `admin_audit_log` events; no full HR history in v1 |
