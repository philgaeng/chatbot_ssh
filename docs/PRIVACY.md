# Privacy and Sensitive Data Safety Spec

## Purpose

Define a single, safer data architecture for grievance and complainant data, including SEAH, without splitting into two complainant databases.

This spec is implementation-facing and aligned with:

- `CLAUDE.md` data boundaries
- `docs/ticketing_system/03_ticketing_api_integration.md`
- `docs/ticketing_system/04_ticketing_schema.md`
- `docs/Refactor specs/May5_seah/*`

## Core decisions (LOCKED)

1. One canonical complainant/grievance data domain.
2. Original grievance text and attachments are treated as sensitive content, not only contact fields.
3. Ticketing stores no PII and no raw grievance narrative in `ticketing.*`.
4. Officer default experience is summary-first (redacted and policy-safe).
5. Original vault reveal is permitted for officers, but controlled, audited, and time-bounded.

## Data domains

### 1) Vault domain (restricted)

Stores original sensitive content:

- raw grievance narrative (`grievance_description` and follow-up narratives)
- complainant direct identifiers (name, phone, email, address)
- attachment originals and OCR output (if produced)

Security requirements:

- encryption at rest with envelope model
- key split by sensitivity (`standard` vs `seah`)
- no direct table access from officer/ticketing services

### 2) Metadata domain (operational)

Stores workflow and case state used by ticketing and reporting:

- grievance reference IDs
- assignment, escalation, status events, timestamps
- sensitivity class (`case_sensitivity`)
- non-PII geography and routing metadata

Security requirements:

- no vault plaintext duplication
- strict schema and payload allowlist

### 3) Derived summary domain (consumable)

Stores policy-safe outputs for officer UI and integrations:

- redacted summary
- extracted fact checklist
- translation variants
- confidence and summary freshness metadata

Security requirements:

- generated only from controlled pipeline
- post-generation PII leakage validation
- blocked publication if leakage checks fail

## Access policy model

All access to sensitive fields uses a policy gate with:

- actor role
- org/location/project scope
- case sensitivity (`standard` or `seah`)
- purpose/reason code
- action type (`view_summary`, `reveal_original`, `export`, `reply`)

### Reveal original policy

- Allowed for officer levels (including L1), but never as default.
- Requires explicit reason code and policy acknowledgement.
- Returns short-lived view token (for example, 60-120 seconds).
- Reveal sessions are fully audited.
- SEAH uses stricter threshold (smaller role audience, tighter rate limits, stronger alerting).

## UI containment controls

Required controls for vault reveal UI:

- disable text selection and copy/cut in client UI
- disable common print/export actions in UI
- full-screen overlay watermark with actor/time/case reference
- auto-hide content on expiry or tab switch (best effort)

Note: screenshots cannot be fully prevented on end-user devices. Mitigation is deterrence + traceability (watermark + audit + alerts).

## LLM summary safety controls

### Processing sequence

1. redact detected PII/entities
2. summarize and structure facts
3. run policy leakage validation
4. publish only validated summary

### Required outputs

- `officer_operational_summary` (strict redaction)
- `internal_safe_summary` (broader but still policy-bounded)
- `complainant_update_text` (channel-safe update text)

### Omission and drift controls

- fact checklist coverage score (who/what/when/where/harm/remedy/urgency)
- confidence score and stale summary indicator
- prompt/model version pinning
- golden-case regression test set before rollout

## API contract principles

- single grievance API surface for ticketing integrations (no per-table branching)
- brokered endpoints for sensitive reads
- deny-by-default for direct sensitive reads

Minimum endpoint set:

- `GET /api/grievance/{id}` -> metadata + safe summary
- `GET /api/grievance/{id}/complainant` -> masked complainant profile by default
- `POST /api/grievance/{id}/reveal` -> begin reveal session (reason required)
- `POST /api/grievance/{id}/reveal/close` -> close reveal session

## Audit and monitoring requirements

Every sensitive access action must log:

- actor id and role
- grievance id and sensitivity
- action and reason code
- result (`granted` / `denied` / `expired`)
- session id, source IP, user agent
- opened/closed timestamps and duration

SEAH alerting baseline:

- any denied reveal attempt
- unusually high reveal count per actor/day
- off-hours reveal bursts
- repeated long-duration reveals

## Retention and minimization

- longer retention only where policy/legal basis exists
- distinct retention profile for SEAH
- redact/purge jobs for derived artifacts
- legal hold support for selected cases

## Implementation boundaries for this repo

- Ticketing-side implementation lives in `ticketing/` and `channels/ticketing-ui/`.
- Public schema and chatbot data model changes follow `migrations/public/*` and existing backend migration ownership.
- Do not implement direct cross-schema joins from `ticketing.*` into `public.*`.
