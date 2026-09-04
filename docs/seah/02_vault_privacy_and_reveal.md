# 02 — Vault, Privacy, and Reveal Model (as-built)

**Status:** As-built, July 2026 — verified against code on `integration/seah-claude`.
**Last updated:** 2026-09-04 · ⚠ backfilled from git 2026-09-04; not re-verified against the code
**Sources consolidated:** `docs/sprints/archive/Refactor specs/May5_seah/05_vault_and_summary_operating_model.md`, `06_vault_reveal_audit_and_ui_controls.md`, `07_phase2_decision_questions.md`; `docs/sprints/archive/claude-tickets/seah-privacy-worktree-handoff.md`.
Policy baseline lives in [../deployment/09_privacy.md](../deployment/09_privacy.md) (data domains, access-policy model, LLM summary safety, retention); this doc is the **detailed SEAH-facing data model and its implementation status** — it does not restate 09's policy text. Intake behavior is in [01_seah_intake_flow.md](01_seah_intake_flow.md).

> Historical note: the April 2026 spec `03_seah_submission_and_storage.md` (dedicated `complainants_seah` / `grievances_seah` tables, `seah_public_ref` public token) is **obsolete**. Phase 2 (`pub004`) backfilled and **dropped** those tables; `grievance_id` is the only case reference.

---

## 1. Canonical model (LOCKED, implemented)

One data domain in `public.*` for standard **and** SEAH cases:

| Table | Role |
|-------|------|
| `public.grievances` | one canonical grievance table; SEAH rows carry `case_sensitivity = 'seah'`, `grievance_sensitive_issue = TRUE`, `source = 'seah_intake'`, `grievance_description = NULL` (narrative lives in the vault), `vault_payload_ref`, `vault_last_updated_at` |
| `public.complainants` | one canonical person table — identity/contact only, no case role |
| `public.grievance_parties` | per-case person↔role link (see §2) |
| `public.grievance_vault_payloads` | original narratives / sensitive free text (see §3) |
| `public.grievance_reveal_sessions`, `public.grievance_sensitive_access_audit` | reveal lifecycle + immutable sensitive-access audit (schema exists; see §5) |

Migrations (public Alembic stream, `migrations/public/`): `pub003_vault_reveal_audit_foundation` (case_sensitivity + vault/reveal/audit tables), `pub004_phase2_canonical_consolidation` (grievance_parties, backfill of legacy SEAH tables, **drop** of `grievances_seah`/`complainants_seah`), `pub009_seah_service_providers` (support-centre directory).

Canonical identifier decisions (phase 2, all implemented): `grievance_id` is canonical for standard + SEAH; `seah_public_ref` replaced by the canonical id directly; id format enforced in app code, not a DB constraint.

## 2. `grievance_parties` — person / case-role model

DDL (pub004):

- `party_id` (text PK), `grievance_id` (FK → grievances, CASCADE), `complainant_id` (FK → complainants, **nullable** — strict-anonymous rows keep role context without identity), `party_role`, `is_primary_reporter` (bool), `contact_allowed` (bool), `contact_channel` (jsonb), `consent_scope` (jsonb), `notes_safe` (non-PII note), timestamps.
- `party_role` CHECK: `victim_survivor` | `witness` | `relative_or_representative` | `seah_focal_point` | `reporter_other`.
- Partial unique index: **exactly one** `is_primary_reporter = TRUE` row per grievance.

Rules (locked): identity never depends on case role; role lives only here; every grievance gets ≥ 1 party row (default role `victim_survivor`); one person can hold different roles across grievances. The chatbot encodes 3 roles (`victim_survivor`, `relative_or_representative` — mapped from `not_victim_survivor`, `seah_focal_point`); `witness`/`reporter_other` are officer-assignable in ticketing.

Write path (`submit_seah_to_db`, `postgres_services.py`):

1. Complainant row upserted only when identity exists; anonymous route with no identity fields ⇒ `complainant_id = NULL`.
2. Grievance row upserted with the SEAH field mapping of §1.
3. Parties: if the multi-party `party_contacts` slot payload exists (built during intake by `backend/actions/services/seah/party_payload.py`), rows are replaced from it; otherwise a single primary-reporter row is derived from `seah_victim_survivor_role`, with `contact_allowed = NOT seah_anonymous_route`, `contact_channel = {"channel": seah_contact_consent_channel}`, `consent_scope = {"complainant_consent": …}`.

## 3. Vault (restricted content)

`grievance_vault_payloads` columns: `vault_payload_id`, `grievance_id`, `seah_case_id` (legacy backfill only), `case_sensitivity` (`standard`|`seah`), `payload_type` (`original_grievance` | `follow_up_message` | `attachment_ocr` | `other`), `content_ciphertext`, `content_redacted`, `content_hash`, `pii_detection_metadata`, `source_channel`, `source_language_code`, `created_by`, timestamps.

- SEAH submit writes the incident narrative as an `original_grievance` payload (`case_sensitivity='seah'`, `source_channel='chatbot'`) and stamps `vault_payload_ref` on the grievance; `grievances.grievance_description` stays NULL for SEAH. Vault is the **single source of truth** for original narrative (phase-2 decision Q10); the legacy `seah_payload` JSON snapshot is no longer written (Q9).
- **Complainant PII encryption (implemented):** `complainant_phone`, `complainant_email`, `complainant_full_name`, `complainant_address` are pgcrypto-encrypted (`pgp_sym_encrypt`, hex) plus hashed lookup columns (`complainant_phone_hash`, …) using `DB_ENCRYPTION_KEY` (`base_manager.py` / `complainant_manager.py`). Same scheme for standard and SEAH (per decision D-16).
- **Gap / Planned:** the vault **narrative** insert currently stores plaintext in the `content_ciphertext` column (no `pgp_sym_encrypt` on that write path), and the envelope model with **separate keys per sensitivity class** (`standard` vs `seah`) from 09_privacy is not implemented. `content_redacted`, `content_hash`, `pii_detection_metadata` are not yet populated.

## 4. Metadata and summaries (ticketing side)

Boundary rules (LOCKED, enforced by design + CLAUDE.md):

- `ticketing.*` stores **no PII and no raw narrative**; non-PII cache at ticket creation only (summary, categories, location, priority, `is_seah`, `case_sensitivity`).
- No SQL joins / FKs from `ticketing.*` into `public.*`; integration via the grievance API + webhook only.
- SEAH tickets are filtered **at query level** for non-SEAH roles (`WHERE is_seah = FALSE`, `ticketing/api/routers/tickets.py`); `workflow_type = seah` gates visibility (see [../ticketing_system/12_workflows_configuration.md](../ticketing_system/12_workflows_configuration.md)).
- Officer default view is **summary-first**; ciphertext must never render. **As-built since T3-04:** the grievance API returns plaintext (the backend decrypts server-side), so `ticketing/services/pii_vault.py` no longer decrypts anything and ticketing holds **no** `DB_ENCRYPTION_KEY` — the key is owned solely by `backend`. `pii_vault.py` now only shapes the card and **fails closed + loud** if ciphertext ever arrives (that would mean the backend regressed). SEAH stays masked until vault reveal. *Until T3-04 this module broker-decrypted single fields with its own copy of the key — a client-side workaround for a server-side omission, not a second PII path.*

**Planned (not implemented):** the derived-summary pipeline from the May5 05 spec — redact → summarize → validate with leakage/coverage blockers, fact checklist, confidence/staleness, provenance (`model_version`, `prompt_version`, `input_hash`), and the minimum metadata event format (`event_id`, `safe_delta`, `summary_regen_required`). No leakage-checker or summary-generation code exists in `ticketing/` yet. Required ticketing-ingest fields (phase-2 Q12): `grievance_id`, `case_sensitivity`, non-PII routing (`country_code`, `location_code`, `organization_id`, `project_code`), `summary_profile_version`, `safe_summary`.

## 5. Reveal workflow + audit

Target design (LOCKED policy — May5 06): summary-first default; any officer role may **request** reveal of original content with a reason code + policy acknowledgement; grants are short-lived, never default-open, always audited; the **public/chatbot grievance API is authoritative** for the policy decision (role, scope, sensitivity, rate limit), ticketing only proxies and renders.

### Endpoint contract (authoritative, public API) — **Planned**

- `POST /api/grievance/{grievance_id}/reveal` — request `{reason_code, reason_text, client_context}`; grant `{granted, reveal_session_id, expires_at_utc, content_token, watermark_text}`; deny `{granted: false, deny_code}`.
- `POST /api/grievance/{grievance_id}/reveal/close` — `{reveal_session_id, close_reason}` → `{ok}`.

### As-built status

| Piece | Status |
|-------|--------|
| DB schema: `grievance_reveal_sessions` (decision, deny_code, policy version, request_id, source_ip, user_agent, opened/expires/closed, duration, close_reason) and `grievance_sensitive_access_audit` (event types `reveal_requested/granted/denied/closed/expired`, `decrypt_attempt/denied/success`) | ✅ created by `pub003` |
| Backend reveal endpoints + policy engine + token issuance | ❌ **not implemented** in `backend/api/` |
| Audit writes to the two tables above | ❌ no code writes them yet |
| Ticketing reveal UX | ✅ `POST /tickets/{ticket_id}/reveal` (`ticketing/api/routers/tickets.py`) with reason code, using a **proto fallback** in `ticketing/clients/grievance_api.py`: fetches `GET /api/grievance/{id}`, mints a synthetic session with TTL **120 s standard / 60 s SEAH**, watermark text `actor · time · case:id`; `close` is a logged no-op. Marked `_proto_mode: true` and `INTEGRATION POINT` for the real endpoints. |
| Reveal-policy party context (phase-2 Q13: include `party_role`, `is_primary_reporter` in policy inputs) | ❌ pending the real policy engine |

### UI containment (reveal pane)

Required during reveal (per 06 / 09_privacy): disable text selection/copy/cut and context menu, no print/export, dynamic watermark overlay, auto-hide on TTL expiry with re-request. Screenshot capture cannot be blocked — mitigation is watermark + audit + policy notice. (Ticketing UI renders the watermark/TTL from the proto session; verify containment details in `channels/ticketing-ui/` before relying on them.)

## 6. SEAH-specific hardening

For `case_sensitivity = 'seah'` (baseline chosen in phase-2 Q14 — lower TTL + quotas + alerts, no dual-approval):

| Control | Status |
|---------|--------|
| Lower reveal TTL (60 s vs 120 s) | ✅ in the proto reveal client |
| Stricter per-user/day reveal quota, cooldowns | Planned (policy engine) |
| Alerting: any denied SEAH reveal ⇒ security event; >3 reveals/actor/hour ⇒ elevated; out-of-scope SEAH access ⇒ critical; TTL-overrun ⇒ anomaly | Planned |
| Enhanced redaction of the default SEAH summary (quasi-identifiers) | Planned (summary pipeline) |
| SEAH back-office 2FA/MFA | Handled by Keycloak auth on ticketing (auth stack is **Keycloak**, not Cognito as older specs said); MFA policy = ops configuration |

## 7. Ownership rules (durable, from the worktree handoff)

The worktree split is obsolete (single-agent workflow), but the **ownership boundaries remain binding**:

1. `public.*` (via `migrations/public/alembic.ini`): canonical grievance/complainant storage, vault content + key policy, reveal authorization decisioning, authoritative sensitive-access audit.
2. `ticketing.*` (via `ticketing/migrations/alembic.ini`): workflow metadata/events, derived summaries and anomaly artifacts, reveal UX, ticket-level interaction audit.
3. Forbidden: ticketing storage of raw narrative or direct PII; duplicate reveal-policy logic in ticketing that bypasses the public API; cross-schema joins; two migration streams owning one table.
4. Audit correlation key across streams: `grievance_id` + `reveal_session_id` + `request_id`.

## 8. Acceptance / test matrix (carried forward)

Still-valid completion gates from the May5 specs, to close the Planned items above:

- In-scope reveal grant with valid reason; out-of-scope deny **audited**; expired token cannot fetch; close writes duration; SEAH quotas stricter than standard.
- Ticketing default responses contain no vault narrative and no raw PII; leakage blocker prevents unsafe summary publication; stale-summary indicator during regeneration.
- Reveal/audit checks pass for the standard + SEAH matrix; public and ticketing audit streams correlate deterministically.
