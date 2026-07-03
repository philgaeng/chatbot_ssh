# Agent runbook — HR-01 + HR-02: Auth hardening

**Branch:** `hardening/hr-01-02-auth` off `integration/seah-claude` · **Spec:** [`../01-auth-hardening-spec.md`](../01-auth-hardening-spec.md) · Read [`README.md`](README.md) common rules first. Do HR-01 fully (commit + tests) before starting HR-02.

## Mission

Make authentication fail **closed** (HR-01), then centralize per-ticket authorization into one dependency and apply it to the endpoints that currently skip checks (HR-02). This closes the two worst security findings in the July 2026 review: missing-env-var ⇒ everyone is super_admin, and file/PII endpoints that pierce the SEAH wall.

## HR-01 steps

1. Read `ticketing/api/dependencies.py` end to end, plus `ticketing/config/settings.py`, `ticketing/api/main.py` startup, and `backend/api/routers/grievance.py` (API-key check). Map every fail-open branch (the spec lists four — verify each still exists, find any others and log them).
2. Implement per spec §1: `TICKETING_ENV` (default `production`), startup guards in both apps, per-request 503 fallback, least-privilege header identity. **Before changing the header-identity default role, grep for internal callers** (`x-internal-user-id` senders: grievance_sync? dispatch? tests?) and preserve their real needs explicitly.
3. Compose files: `TICKETING_ENV=dev` in `docker-compose.override.yml` only. Update `docs/deployment/DOCKER.md` env table and the `env.local` template mention.
4. Write `tests/ticketing/test_fail_closed_auth.py` (6 cases per spec). Pattern reference for settings monkeypatching: `tests/ticketing/test_auth_dependencies.py`.
5. `docs/deployment/13_security.md`: add the "Fail-closed guarantees" section (what refuses to start/serve, under which env values).
6. Manual verification per spec; record in `../PROGRESS.md`.

## HR-02 steps

1. Read the reference implementations of correct gating: `get_ticket` (`tickets.py` ~748-777) and `list_tickets` scope filtering (~525-557), plus `ticketing/services/admin_access.py` and the scope services. The dependency must reproduce exactly this decision set — no new policy.
2. Create `ticketing/api/ticket_access.py` (`require_ticket_access`, `require_file_access`) per spec §2. File→ticket resolution covers both `ticketing.ticket_files` and chatbot files in `public.file_attachments` (via the ticket's `grievance_id`).
3. Sweep `ticketing/api/routers/tickets.py`: list every endpoint taking a `ticket_id`/`file_id`; replace inline checks with the dependency. Keep a table of endpoint → old gates → new gates in your PROGRESS notes; any endpoint where behavior would *change* for an already-correct persona must be flagged, not silently altered.
4. Write `tests/ticketing/test_ticket_access_matrix.py` — the parametrized persona × endpoint matrix from the spec. Build personas from the seed roles (`ticketing/seed/grm_roles.py`, `mock_tickets.py` fixtures); reuse existing test fixtures (`tests/ticketing/conftest.py`) rather than inventing new scaffolding.
5. Full suite green: `python -m pytest tests/ticketing -q`. Manual verification per spec.

## Constraints

- No changes to `list_tickets` query filtering, PII masking rules (TP-15), or the reveal flow's own logic.
- No router splitting, no renames — Tier-2/3 work.
- If you find additional ungated endpoints beyond the three in the spec, gate them (that's the point of the class fix) and list them in PROGRESS deviations.

## Done means

All HR-01 + HR-02 checklist boxes ticked in `../PROGRESS.md`, both test files green in the full suite run, manual checks recorded, security doc updated.
