# 03 - SEAH Submission and Storage

## Objective

Document the **implemented** SEAH submission path: dedicated action, DB writes, case identifiers, and separation from general grievance submission.

This spec is a child of:

- `docs/Refactor specs/April20_seah/00_seah_sensitive_flow_spec.md`

Slot and flow contract:

- `docs/Refactor specs/April20_seah/01_seah_route_and_slots.md`
- `docs/Refactor specs/April20_seah/07_seah_focal_point_flow.md`

Ticketing and internal notifications:

- `docs/Refactor specs/April20_seah/xx-ticketing-sytem-seah.md`

Follow:

- `docs/Refactor specs/AGENT_INSTRUCTIONS.md`

---

## Implemented behavior (summary)

| Concern | Implementation |
|--------|------------------|
| Submit action | `ActionSubmitSeah` in `backend/actions/action_submit_grievance.py` (`name`: `action_submit_seah`) |
| Orchestrator invocation | `state_machine.py` invokes `action_submit_seah` after `form_seah_2` or `form_seah_focal_point_2` completes (when `story_main == seah_intake`) |
| DB API | `PostgresService.submit_seah_to_db` in `backend/services/database_services/postgres_services.py` |
| Tables | `complainants_seah`, `grievances_seah` (created on demand via `_ensure_seah_tables`) |
| General grievance submit | **`action_submit_grievance` is not used** for final SEAH persistence |

---

## Payload and slots

`ActionSubmitSeah`:

1. Builds base payload via **`collect_grievance_data`** (shared helper with grievance flow) so complainant + grievance-shaped fields populate consistently.
2. Adds SEAH-specific top-level keys from the tracker, including:
   - `seah_not_adb_project`, `seah_contact_consent_channel`
   - Focal and SEAH narrative slots listed in `seah_fields` (e.g. `seah_victim_survivor_role`, `seah_project_identification`, focal risk fields, `seah_focal_phone`, `seah_focal_lookup_status`, `seah_focal_verification_status`, …).

`submit_seah_to_db`:

- Inserts one row into **`complainants_seah`** (complainant identity/location/contact fields from the collected payload).
- Inserts one row into **`grievances_seah`** with:
  - `grievance_description`, summary/categories/status/timeline/language
  - `submission_type` fixed to **`seah_intake`**
  - **`seah_payload`**: JSON serialization of the **full** data dict passed in (audit-friendly snapshot including SEAH slots).

---

## Case identifiers

| Field | Role |
|-------|------|
| `seah_case_id` | Internal-style id, format `SEAH-YYYY-######` (random suffix) |
| `seah_public_ref` | User-facing reference, format `SEAH-REF-YYYY-######` |

On success, `ActionSubmitSeah` sends an **on-screen** message (en/ne) including **`seah_public_ref`** and sets slots `seah_case_id`, `seah_public_ref`, `grievance_status` submitted.

Stakeholder decision (**00**): public-safe reference token vs internal id — implementation exposes **public ref string** in message; both stored in DB row.

---

## SMS and notifications

- **`ActionSubmitSeah`** does **not** call **`_send_grievance_recap_sms`** (unlike the generic grievance submit path in the same module).
- **OTP / transactional SMS:** `ActionAskOtpInput` can still send SMS in flows that use full OTP; for **`seah_intake` + `grievance_sensitive_issue`**, `ValidateFormOtp` only requires **`complainant_phone`**, so the OTP SMS path is **not** used for that sensitive SEAH phone collection (see `04`).

Internal ops email / webhooks: **`xx`** ticketing spec.

---

## Scope boundaries

**In scope (this doc / current code):** submit action contract, tables, JSON payload, public ref messaging.

**Out of scope:** ticketing assignment, encryption column matrix (stakeholder parity with “main flow” per `00`), production retention—track with infra / `xx`.

---

## Acceptance criteria (implementation-aligned)

1. [x] SEAH finalization uses **`submit_seah_to_db`**, not **`create_grievance`** / general grievance insert for the SEAH submit action path.
2. [x] `complainants_seah` + `grievances_seah` receive rows; `seah_payload` stores a JSON snapshot.
3. [x] No grievance recap SMS from **`ActionSubmitSeah`**.
4. [x] User sees confirmation text including **`seah_public_ref`** after successful submit.

---

## Test requirements

- Unit: `submit_seah_to_db` happy path and failure (`ok: False`).
- Unit/integration: `ActionSubmitSeah` includes expected SEAH keys in data passed to DB layer.
- Negative: assert grievance recap SMS helper is **not** invoked for SEAH submit (mock/spy).

---

## Delivery checklist

- [x] Document tables and submit action in PR notes when changing schema.
- [ ] Migration strategy if moving from `_ensure_seah_tables` inline DDL to versioned migrations.
- [ ] Align outro / referral / timer UX with frontend when built (`00` decisions).

---

## Changelog

- **2026-04-21:** Aligned with codebase: `ActionSubmitSeah`, `submit_seah_to_db`, table names, `seah_payload`, refs, SMS omission; cross-links to `01`/`07`/`04`.
