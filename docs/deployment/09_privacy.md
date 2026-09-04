# Privacy and Sensitive Data Safety Spec

**Status:** live specification (tier 1) — authoritative for what the system does today.
**Last updated:** 2026-08-18 · ⚠ backfilled from git 2026-09-04; not re-verified against the code

> For the full platform security feature index, see [13_security.md](13_security.md).

## Purpose

Define a single, safer data architecture for grievance and complainant data, including SEAH, without splitting into two complainant databases.

This spec is implementation-facing and aligned with:

- `CLAUDE.md` data boundaries
- `docs/ticketing_system/03_ticketing_api_integration.md`
- `docs/ticketing_system/04_ticketing_schema.md`
- `docs/sprints/archive/Refactor specs/May5_seah/*` (sprint-era SEAH specs)
- `docs/seah/` — current SEAH documentation set (being consolidated; see [`../seah/README.md`](../seah/README.md))

## Core decisions (LOCKED)

1. One canonical complainant/grievance data domain.
2. Original grievance text and attachments are treated as sensitive content, not only contact fields.
3. Ticketing stores no PII and no raw grievance narrative in `ticketing.*`.
4. Officer default experience is summary-first (redacted and policy-safe).
5. Original vault reveal is permitted for officers, but controlled, audited, and time-bounded.

## Schema ownership (LOCKED)

> **Re-motivated 2026-07-15 (T3-07).** This section was headed *"Worktree and schema
> ownership"* and justified by *"to support parallel development in separate worktrees"* — a
> workflow **retired in June 2026** (`a371e4a4`; CLAUDE.md §Single-agent workflow). The
> ownership split below is kept because **schema ownership is real architecture** — it is what
> keeps the three migration streams from fighting over the same DDL — but it does not depend on
> worktrees, and never really did. Rule 4 below was also **factually false** and is corrected.
> Evidence: [`../sprints/archive/2026-08_tier3_structural/00-reassessment.md`](../sprints/archive/2026-08_tier3_structural/00-reassessment.md) §6.

| Ownership | Owner | Schema/tables | Responsibilities |
|---|---|---|---|
| Public/chatbot domain | chatbot/public migration stream (`migrations/public/`) | `public.*` | intake, canonical grievance identity, vault storage, policy gate, reveal authorization, immutable security audit of sensitive reads |
| Ticketing domain | ticketing migration stream (`ticketing/migrations/`) | `ticketing.*` | operational metadata/events, officer workflow state, derived summaries/anomaly signals, UI consumption, ticket-level interaction audit |

Rules:

1. `ticketing.*` never stores raw original grievance narrative or direct PII. **Pinned by `tests/ticketing/test_boundary_policy.py`.** (Caveat: `grievance_summary` is cached and is free text — see CLAUDE.md §Data rules rule 4.)
2. `public.*` remains system of record for original grievance/vault content.
3. Access to **complainant PII and vault content** always goes through brokered API policy checks. **This does not extend to non-PII grievance content or file metadata** — ticketing reads those directly (rule 4).
4. **Ticketing reads and writes an enumerated, closed set of `public.*` tables** through its own session — the list is in CLAUDE.md §Data rules rule 1, gated by `tests/ticketing/test_boundary_policy.py`. Adding to it is a deliberate decision.
   > This replaces *"No direct `ticketing.*` -> `public.*` joins; integrate through API/event contracts"*, which had been **false for months** when it was written down here. Ticketing issues 11 statements against `public.*`, 3 of them writes. Routing them through `GET /api/grievance/{id}` as this rule implied would be a **security downgrade**: the direct read carries a Keycloak JWT and a jurisdiction gate that the API still lacks even after T3-06 (§6; D-38).
5. **No cross-schema FK** from `ticketing.*` into `public.*`. Kept, and pinned by a test — this is what preserves the option to extract ticketing later.

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
- stored in `ticketing.*` where possible for officer workflow and AI operations

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
- persisted in `ticketing.*` as officer-facing operational artifacts

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

Ownership split for API contracts:

- Public/chatbot API owns original-content reads/writes and reveal authorization.
- Ticketing API owns metadata/event ingestion, summary status, and officer workflow actions.
- Ticketing may proxy reveal requests to public API, but does not bypass policy checks.

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

Audit stream ownership:

- Public/chatbot side (authoritative): sensitive content access audit (`reveal_*`, decrypt decisions).
- Ticketing side: workflow/action audit and summary generation lifecycle audit.
- Correlation key between streams: `grievance_id` + `reveal_session_id` + `request_id`.

## Retention and minimization

- longer retention only where policy/legal basis exists
- distinct retention profile for SEAH
- redact/purge jobs for derived artifacts
- legal hold support for selected cases
- **resolved-case archiving** (soft retire, not delete): [`docs/ARCHIVING_AND_RETENTION.md`](../ARCHIVING_AND_RETENTION.md) — `ticketing.settings.archiving_policy`, daily Celery job, attachment cold tier; PII retained with tighter access on archived cases

## Implementation boundaries for this repo

- Ticketing-side implementation lives in `ticketing/` and `channels/ticketing-ui/`.
- Public schema and chatbot data model changes follow `migrations/public/*` and existing backend migration ownership.
- **Ticketing may read and write `public.*` through its own session — but only the enumerated, closed set**
  in [`CLAUDE.md`](../../CLAUDE.md) §Data rules, rule 1, which is pinned by
  `tests/ticketing/test_boundary_policy.py`. Adding a table to that set is a deliberate decision, not a
  default. Grievance **state** changes still go over HTTP (`POST /api/grievance/{id}/status`), never SQL —
  that invariant is real and stays.
- **No foreign keys** from `ticketing.*` into `public.*`, and **no complainant PII columns** in
  `ticketing.*`. Both pinned by tests. These are the two rules that survived, and they are the ones that
  carry the privacy weight.
- Each schema owns its migration stream (`ticketing/migrations`, `migrations/public`, `ops/migrations`);
  no two streams own DDL for the same table.

> ⚠ **Amended 2026-08-18 (sprint deviation D-21), and the reason travels with the rule.** This section
> previously read *"Do not implement direct cross-schema joins from `ticketing.*` into `public.*`"* and
> *"expose integration through API contracts only"*. **That rule was deliberately retired by T3-07 on
> 2026-07-15** and this document was not updated, so a live privacy spec spent a month forbidding what the
> locked architecture permits and tests enforce.
>
> **Why it went.** The rule was written 2026-03-11 to keep two options open: move ticketing to its own
> database by changing a connection string, and keep the chatbot working if ticketing were removed.
> **Both goals were abandoned in the code, by both sides, months before anyone amended the rule** —
> ticketing issues 11 statements against `public.*`, three of them writes, and the chatbot's intake
> location validation reads `ticketing.locations` through its own connection. The rule had no enforcement
> (one database, one role), had been false for months, and honouring it today would **degrade privacy**:
> the direct read sits behind a Keycloak JWT and a jurisdiction gate that `GET /api/grievance/{id}`
> cannot offer. Evidence and the decision:
> [`sprints/archive/2026-08_tier3_structural/00-reassessment.md`](../sprints/archive/2026-08_tier3_structural/00-reassessment.md) §6.
>
> A doc reorganisation in June deleted that rationale and left the bare rule, which is why it read as
> arbitrary fiat and then survived a correction it should not have. **If you amend a rule here, move its
> reason with it** — [engineering rule 7](../engineering/00_engineering_index.md).
