# Vault and summary operating model (May5 SEAH)

## Scope

This spec defines how grievance content, complainant PII, and officer-facing summaries should be stored and served for both standard and SEAH flows.

This document explicitly splits implementation ownership between:

- chatbot/public worktree (`public.*`)
- ticketing worktree (`ticketing.*`)

It complements:

- `00_overview_and_scope.md`
- `03_submission_mapping_and_fallback.md`
- `docs/PRIVACY.md`

## Problem this solves

Current storage paths include dual write patterns (regular vs SEAH tables) and direct narrative persistence, which increases policy drift and accidental exposure risk.

The model below keeps one data safety posture while preserving operational simplicity.

## Target model (LOCKED)

### A) Vault content (restricted)

Includes:

- original grievance narrative text
- original follow-up complainant messages
- direct contact identifiers
- attachment originals and optional OCR text

Storage rules:

- encrypted at rest
- sensitivity key selection by `case_sensitivity`
- no ticketing table stores raw vault narrative
- owned by chatbot/public worktree in `public.*`

### B) Case metadata (operational)

Includes:

- grievance/ticket references
- workflow progression (queue, status, assignments, escalations)
- geography and org routing fields
- event log pointers

Storage rules:

- no direct PII fields
- no raw free text complaint body
- owned by ticketing worktree in `ticketing.*`

### C) Derived summaries (officer-facing)

Includes:

- redacted and translated grievance summary
- fact checklist and coverage score
- summary confidence and freshness
- generation provenance (`model_version`, `prompt_version`, `input_hash`)

Storage rules:

- publish only after leakage checks pass
- persist prior versions for auditability
- owned by ticketing worktree in `ticketing.*`

## Ownership matrix (implementation)

| Capability | Owner | Storage/API owner |
|---|---|---|
| Intake of original grievance text and contact | Public/chatbot worktree | `public.*` + backend grievance API |
| Vault encryption and key selection (`standard`/`seah`) | Public/chatbot worktree | `public.*` |
| Officer workflow state (assignment/escalation/status) | Ticketing worktree | `ticketing.*` |
| Metadata event log for ticket lifecycle | Ticketing worktree | `ticketing.*` |
| Summary generation and anomaly detection for officer UI | Ticketing worktree | `ticketing.*` |
| Reveal authorization decision | Public/chatbot worktree | backend grievance API policy gate |
| Reveal request UX and session handling UI | Ticketing worktree | `channels/ticketing-ui/` + ticketing API proxy/orchestrator |

## Intake and update flow

1. Intake receives grievance content and contact fields.
2. Public/chatbot writes original content to vault payload in `public.*`.
3. Ticketing writes metadata/event record to `ticketing.*` for workflow.
4. Async summary job runs:
   - redact -> summarize -> validate
5. Derived summary is updated for officer use.
6. Ticketing UI reads metadata + derived summary only by default.

Cross-worktree contract:

- Ticketing receives only allowed payloads from public/chatbot side (`grievance_id`, sensitivity, non-PII routing metadata, and policy-safe narrative input shape).
- Ticketing must not fetch raw vault tables directly.

## Minimum event format for metadata updates

Each case event must include:

- `event_id` (uuid)
- `grievance_id`
- `case_sensitivity`
- `event_type` (submitted, note_added, escalated, resolved, message_sent, etc.)
- `actor_id` and `actor_role`
- `event_time_utc`
- `safe_delta` (non-PII details only)
- `summary_regen_required` (bool)

Recommended JSON shape:

```json
{
  "event_id": "uuid",
  "grievance_id": "NP-XXXX",
  "case_sensitivity": "seah",
  "event_type": "status_changed",
  "actor_id": "user-123",
  "actor_role": "site_safeguards_focal_person",
  "event_time_utc": "2026-04-27T07:00:00Z",
  "safe_delta": {
    "old_status": "SUBMITTED",
    "new_status": "L1_REVIEW"
  },
  "summary_regen_required": true
}
```

## LLM summary generation requirements

### Input contract

- sanitized event stream from metadata
- selected vault excerpts only when policy permits
- language preference
- desired summary profile (`officer_operational`, `internal_safe`, `complainant_update`)

### Output contract

- redacted text body
- fact checklist fields
- confidence score
- stale flag
- leakage check result and rule hits

### Required blockers

Do not publish summary when any of these are true:

- leakage checker detects high-confidence PII
- coverage score below threshold
- model/proxy response missing required checklist fields

## Ticketing integration rule

Ticketing processing and UI must consume:

- metadata events
- validated derived summaries

Ticketing must not consume:

- raw vault narrative
- raw complainant direct identifiers except through explicit reveal flow

Public/chatbot side must expose:

- stable grievance reference APIs
- explicit reveal authorization APIs
- optional policy-safe excerpt endpoint for summary regeneration where needed

## Migration steps (implementation)

1. Public/chatbot worktree: standardize `case_sensitivity` and vault ownership in `public.*`.
2. Ticketing worktree: add metadata event payload contract and append-only writes in `ticketing.*`.
3. Ticketing worktree: add async summary regeneration task per event with idempotency key.
4. Public/chatbot + ticketing: define API contracts for reveal/policy-safe excerpt exchange.
5. Ticketing worktree: enforce leakage/coverage validation gates before publishing summaries.
6. Ticketing worktree: move default UI rendering to summary-first mode.

## Test matrix (minimum)

- Standard case with complete summary update after status change.
- SEAH case where leakage checker blocks unsafe summary.
- Metadata-only event that does not require summary regeneration.
- Concurrent updates where stale summary indicator flips until regen completes.
- Ticketing endpoint returns no vault narrative in default responses.
