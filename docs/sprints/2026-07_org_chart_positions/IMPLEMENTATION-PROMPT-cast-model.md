# Implementation prompt — Tier cast, positions-as-titles, per-package staffing & reassignment

> Hand this whole file to the implementing agent. Fill in **"Scope for THIS run"** first.

You are implementing the design spec at
**`docs/sprints/2026-07_org_chart_positions/DESIGN-cast-model-and-package-staffing.md`**.
That doc is the **single source of truth**, and every design fork in it is already **decided** —
do **not** re-open design decisions. If you hit a genuine blocker or a spec gap, **stop and ask
the human**; do not improvise an alternative design or silently deviate.

---

## Scope for THIS run

> **All phases — §7 Phase 1 → Phase 5** (Phase 0 is DROPPED per spec). Decided with the human 2026-07-23.
> Work them **in order**, each shipping with the full ticketing suite green before the next, on a single
> feature branch off `fix/demo-officer-switcher-trap`. Hand back the whole diff for human review — no merge/push.

Work the spec's phases **in order** (§7: 1 → 5) unless told otherwise. Each phase must ship with
the **full test suite green** before the next. **Prefer handing back after each phase** rather than
batching multiple phases into one diff.

---

## Read first (in this order)

1. The spec doc above — **all of it**, especially §3 (target model), §5 (invariants), §6 (mechanism), §7 (phased tasks + per-phase acceptance), §11 (test impact).
2. `CLAUDE.md` — architecture, DB schema-ownership rules, the **Docker-only** build rule, conventions.
3. As-built refs the spec leans on: `docs/ticketing_system/11_roles_and_permissions.md`, `docs/deployment/16_auth_keycloak.md`, `docs/deployment/DOCKER.md`.
4. The code the spec names, before editing it: `ticketing/engine/workflow_engine.py`; `ticketing/api/routers/{users,position_types,officer_positions}.py`; `ticketing/models/{workflow,officer_scope,position_type,user}.py`; `ticketing/services/{supervisor,officer_admin}.py`; `ticketing/constants/role_archetypes.py`; `channels/ticketing-ui/components/settings/**`; `channels/ticketing-ui/lib/api.ts`. Read `channels/ticketing-ui/AGENTS.md` before writing any Next.js code.

---

## Non-negotiable rules

- **Docker only** for build/run/migrate/seed. `dcg = docker compose --env-file env.local -f docker-compose.yml -f docker-compose.grm.yml`. Never `pip install` / `uvicorn` / `alembic` / `npm run build` on the host to build or serve — host CLIs are read/inspection only. Source is baked into images, so **rebuild** `backend` / `ticketing_api` / `grm_ui` after changes.
- **Do not break the §5 invariants.** `officer_scopes` stays the **single** enforcement + auto-assign source of truth; positions are display-only and **never** gate access; **no complainant PII columns in `ticketing.*`**; **no FK from `ticketing.*` into `public.*`** (soft `String(64)` refs only); the **admin plane** (`admin_scopes`, `super/org/project/officer_admin`) is **untouched**; every model carries `__table_args__ = {"schema": "ticketing"}`.
- **All ticketing DDL through the ticketing Alembic stream** (`ticketing/migrations/`), each migration starting with the CLAUDE.md safe-to-run header. Never touch `public.*` or `ops.*` DDL from here.
- **Keep `role_key` as the join key** (spec §6, Option A): permissions derive from the **step field** the role sits in — **no `tier` column, no materialized view**. Existing named keys **coexist**; only newly-enabled slots mint synthetic keys.
- **Branch, don't push.** Work on a feature branch off the current branch. **Do not commit to `main`, do not push, do not open a PR.** The diff is for human review.
- **Log any deferral same-commit** in `docs/sprints/2026-07_org_chart_positions/followups/` **and** `docs/TODO.md` (repo rule).
- Conventions: snake_case, Pydantic v2, type hints, UTC `timestamptz`, UUID4 ids; match surrounding code style.

---

## Apply the tests — both senses of "apply"

1. **Write/update** the tests called out in spec §11 for your phase(s):
   - **New:** per-package staffing → `officer_scope` generation; the self-escalation guard (§3.3); the reassignment resolution chain + the go-live "every step resolves to a reassigner" check (§3.4); position create with no default role.
   - **Rewrite to the new model:** `test_roles_crud`, `test_workflow_step_roles`, `test_position_types`, `test_role_delete_guard`, `test_escalation_engine`, `test_seah_leak_notifications` (SEAH keyed on track, not role).
2. **Run the full ticketing suite green, in-container** — do not claim done until it passes:
   ```
   dcg exec -T ticketing_api python -m pytest tests/ticketing -q
   ```
   These **must stay green** (invariants — treat any red here as a stop-the-line): `test_pii_boundary`, `test_boundary_policy`, `test_ticket_access_matrix`, `test_authz_matrix_extended`, `test_admin_ladder`, `test_org_authz`.
3. **Frontend:** `tsc --noEmit` clean; rebuild `grm_ui` (+ `backend`/`ticketing_api`) and confirm the containers are healthy.
4. If a test is red: fix it, or — if it's a genuine conflict with the spec — **stop and ask the human**. **Never** hand back with a red suite, and never present a skipped/xfail test as passing.

---

## Verify the one performance assumption (§6 / §3.6)

Confirm the tier-derivation hot path — the **Supervisor** queue tab — is acceptable as a live query. **Only if it is measurably slow**, materialize *supervisor membership* at write-time using the existing `ticket_viewers` pattern (`escalation._apply_step_tier_roles`) — a normal projection table maintained by the same Python logic. **Never** an MV or a `tier` column. If you don't build it, say so and why.

---

## Hand back for final review — do NOT merge

Produce, for the human reviewer:
- A **summary** of what changed, per file/area, mapped to the spec sections you implemented.
- The **full test output** pasted verbatim, plus the image-rebuild/health result and the `tsc --noEmit` result.
- Any **deviation from the spec**, with rationale, and anything **deferred** (with the `followups/` + `TODO.md` entries you added).
- The **diff on the feature branch**, uncommitted-to-`main` and unpushed, ready for the human to review and merge.

Do not merge, push, or mark the work complete — the human does the final review and the merge.
