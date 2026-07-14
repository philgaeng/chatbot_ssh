# Follow-up — authorization gaps surfaced by H2-03 (authz matrix extension)

> **Status:** ✅ **RESOLVED — all three fixed + tested (2026-07-15).** · **Owner:** backend · **Priority:** medium (real authz gaps; no known active exploit — officer accounts are trusted, but least-privilege is violated)
> **Origin:** H2-02/H2-03 authz matrix (`tests/ticketing/test_authz_matrix_extended.py`, 2026-07-14). The matrix was written to **surface** these, not fix them (H2-03 is a test-only ticket). Each is either pinned by the test (regression-guarded) or documented here for a dedicated authz-hardening ticket. **Do not codify the current behavior as correct.**

## The gaps

### 1. Unauthenticated reference/config reads on the locations/projects router ✅ FIXED (2026-07-15)
**Decision:** lock the project-config reads to `get_authenticated_user`; keep geography (countries, locations, import templates) public. **10 GET endpoints gated** — `projects`, `projects/{id}`, and every project sub-resource (`actor-roles`, `donors`, `go-live`, `locations`, `messaging`, `organizations`, `packages`, `workflows`) — via `dependencies=[Depends(get_authenticated_user)]`. The sweep allowlist `_KNOWN_UNAUTH_READS` was trimmed to the 5 remaining geography reads; `test_unauthenticated_sweep_no_new_holes` now proves the project-config reads 401 without a token. Authenticate-only (per-project scope-gating remains an optional later step). Original finding below for the record:

`GET` endpoints that served with **no authentication** (verified by the Part-3 sweep under real Keycloak, no token → 200/404 not 401):

| Endpoint | Assessment |
|---|---|
| `GET /api/v1/countries` | geography reference — plausibly intended-public |
| `GET /api/v1/locations`, `GET /api/v1/locations/{location_code}` | geography reference — plausibly intended-public |
| `GET /api/v1/locations/import/template.{csv,json}` | static import templates — benign |
| `GET /api/v1/projects`, `GET /api/v1/projects/{project_id}` | project list/detail — **questionable** (project metadata) |
| `GET /api/v1/projects/{id}/{actor-roles,donors,go-live,locations,messaging,organizations,packages,workflows}` | project **config** reads — **questionable** (messaging/org-structure/workflow bindings exposed unauthenticated) |

- **Regression-guarded:** `test_unauthenticated_sweep_no_new_holes` asserts the served-unauthenticated set is a subset of `_KNOWN_UNAUTH_READS`. Any **new** unauthenticated endpoint fails the test; locking one of these down makes the test pass with a smaller set (then trim the allowlist).
- **Consumer research (2026-07-15):** the portal calls **all** of these via `apiFetch` (always Keycloak-token-authenticated), and the chatbot/backend consume **none** of the ticketing project/location reads → gating the project-config reads to `get_authenticated_user` breaks **no known consumer**. Geography (`countries`, `locations`, import templates) is low-sensitivity reference data.
- **DoD:** decide per-row public-vs-protected (recommendation: geography stays public; project-config reads — `projects`, `projects/{id}` + `{actor-roles,donors,go-live,locations,messaging,organizations,packages,workflows}` — require `get_authenticated_user`). Add auth deps, then remove the locked rows from `_KNOWN_UNAUTH_READS`. (Optional further step: scope-gate, not just authenticate.)

### 2. `DELETE /api/v1/roles/{role_id}` — no admin gate on non-system roles ✅ FIXED (2026-07-15)
`ticketing/api/routers/users.py`: only **system-origin** roles were gated (super_admin); a `custom` / `operational` role had **no admin check** beyond `get_authenticated_user` — any authenticated officer could delete one.
- **Fix:** non-system roles now gate on `require_settings_write(CREATE_OPERATIONAL_ROLE, track=<role's track>)` — the same catalog-authoring permission as creating a role (super, or org_admin on the role's track; doc 11 §3.3). System roles keep the super-only gate.
- **Test:** `test_delete_custom_role_requires_operational_role_admin` — a non_admin **and** a mere officer_admin both get 403, and the role survives.

### 3. `PATCH /api/v1/projects/{project_id}` — no admin gate on metadata ✅ FIXED (2026-07-15)
`ticketing/api/routers/locations.py`: metadata fields (`name`, `short_code`, `description`, `is_active`, `implementing_agency_org_id`) had **no authorization check** despite the "Admin only" docstring; only the workflow-binding fields were gated.
- **Fix:** the handler now gates on `require_settings_write(MANAGE_PROJECT)` (super/org/project-admin, doc 11 §2.3/§4) before any mutation; the per-track workflow-binding sub-gate is unchanged.
- **Test:** the former `xfail` `test_project_metadata_patch_should_require_admin` is now the passing `test_project_metadata_patch_requires_admin` (non-admin → 403; project_admin passes the gate). xfail marker removed.
- **Possible refinement (not done):** the gate is tier-level (any project_admin), not scoped to the *specific* project_id — matching the pre-existing workflow-binding gate. Per-project scoping for project_admin is a further least-privilege step, out of this fix's scope.

## Non-issues confirmed by the matrix (recorded so they aren't re-flagged)
- `POST /api/v1/reports/build` is authentication-only + row-level data scoping (SEAH downgraded, not blocked) — **intended** per doc 09 (report viewers = any officer with OfficerScope), not a gap.
- `POST /api/v1/users/invite` uses the blunt `require_admin` (is_any_admin) rather than the finer `SettingsAction.INVITE_OFFICERS` predicate — behavior-equivalent for tier membership (both admit every admin tier, deny non-admins).
