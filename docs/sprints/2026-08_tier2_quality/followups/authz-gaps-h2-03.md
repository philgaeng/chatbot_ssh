# Follow-up — authorization gaps surfaced by H2-03 (authz matrix extension)

> **Status:** open (unstarted) · **Owner:** backend · **Priority:** medium (real authz gaps; no known active exploit — officer accounts are trusted, but least-privilege is violated)
> **Origin:** H2-02/H2-03 authz matrix (`tests/ticketing/test_authz_matrix_extended.py`, 2026-07-14). The matrix was written to **surface** these, not fix them (H2-03 is a test-only ticket). Each is either pinned by the test (regression-guarded) or documented here for a dedicated authz-hardening ticket. **Do not codify the current behavior as correct.**

## The gaps

### 1. Unauthenticated reference/config reads on the locations/projects router
`GET` endpoints that serve with **no authentication** (verified by the Part-3 sweep under real Keycloak, no token → 200/404 not 401):

| Endpoint | Assessment |
|---|---|
| `GET /api/v1/countries` | geography reference — plausibly intended-public |
| `GET /api/v1/locations`, `GET /api/v1/locations/{location_code}` | geography reference — plausibly intended-public |
| `GET /api/v1/locations/import/template.{csv,json}` | static import templates — benign |
| `GET /api/v1/projects`, `GET /api/v1/projects/{project_id}` | project list/detail — **questionable** (project metadata) |
| `GET /api/v1/projects/{id}/{actor-roles,donors,go-live,locations,messaging,organizations,packages,workflows}` | project **config** reads — **questionable** (messaging/org-structure/workflow bindings exposed unauthenticated) |

- **Regression-guarded:** `test_unauthenticated_sweep_no_new_holes` asserts the served-unauthenticated set is a subset of `_KNOWN_UNAUTH_READS`. Any **new** unauthenticated endpoint fails the test; locking one of these down makes the test pass with a smaller set (then trim the allowlist).
- **DoD:** decide per-row public-vs-protected (geography likely stays public; project-config reads should require `get_authenticated_user` + scope). Add auth deps, then remove the locked rows from `_KNOWN_UNAUTH_READS`.

### 2. `DELETE /api/v1/roles/{role_id}` — no admin gate on non-system roles
`ticketing/api/routers/users.py:292-303`: only **system-origin** roles are gated (super_admin); a `custom` / `operational` role has **no admin check** beyond `get_authenticated_user` — any authenticated officer can delete one. Documented only (destructive to exercise in a live test).
- **DoD:** gate the whole handler on the appropriate admin tier (org_admin authoring the catalog, per doc 11 §3.3); add a matrix row once gated.

### 3. `PATCH /api/v1/projects/{project_id}` — no admin gate on metadata
`ticketing/api/routers/locations.py:1509-1560`: metadata fields (`name`, `short_code`, `description`, `is_active`, `implementing_agency_org_id`) have **no authorization check** despite the handler's "Admin only" docstring; only the two workflow-binding fields are gated (`can_assign_project_workflow`). Any authenticated officer can rename or deactivate a project.
- **Pinned:** `test_project_metadata_patch_should_require_admin` (`xfail`, `strict=False`) — asserts the spec (non-admin → 403). Flips to **xpass** the moment a gate is added, prompting removal of the marker.
- **DoD:** gate metadata edits on super/org/project-admin (doc 11 §2.3/§4); the xfail becomes a passing test.

## Non-issues confirmed by the matrix (recorded so they aren't re-flagged)
- `POST /api/v1/reports/build` is authentication-only + row-level data scoping (SEAH downgraded, not blocked) — **intended** per doc 09 (report viewers = any officer with OfficerScope), not a gap.
- `POST /api/v1/users/invite` uses the blunt `require_admin` (is_any_admin) rather than the finer `SettingsAction.INVITE_OFFICERS` predicate — behavior-equivalent for tier membership (both admit every admin tier, deny non-admins).
