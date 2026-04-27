# Vault reveal, audit, and UI containment spec (May5 SEAH)

## Scope

Define the exact behavior for controlled access to original grievance content in vault storage.

This applies to both standard and SEAH grievances, with stricter controls for SEAH.

This document splits reveal implementation across public/chatbot and ticketing worktrees.

## Policy baseline (LOCKED)

- Officer default view is summary-first.
- Any officer role may request reveal of original grievance content.
- Reveal is never permanent and never default-open.
- Every reveal action is audited end-to-end.

Ownership:

- public/chatbot side is authoritative for reveal authorization and vault content serving
- ticketing side is authoritative for officer UX and workflow context

## Reveal workflow

1. Officer clicks `Reveal original`.
2. UI collects required reason code and policy acknowledgement.
3. Ticketing API forwards reveal request to public/chatbot grievance API.
4. Public/chatbot backend evaluates policy:
   - role
   - org/location/project scope
   - case sensitivity
   - rate limit and cooldown
5. If granted, public/chatbot backend returns short-lived reveal session token.
6. Ticketing UI opens read-only reveal mode until token expiry.
7. UI sends explicit close event or backend expires session.

## API contract (proposed)

Ownership note:

- Endpoints below are owned by public/chatbot grievance API.
- Ticketing may expose pass-through endpoints for UI convenience, but cannot replace policy decisions.

### POST `/api/grievance/{grievance_id}/reveal`

Request:

```json
{
  "reason_code": "immediate_safeguarding_action",
  "reason_text": "Need original statement to verify risk details",
  "client_context": {
    "route": "/tickets/123",
    "session_id": "web-session-id"
  }
}
```

Response (grant):

```json
{
  "granted": true,
  "reveal_session_id": "uuid",
  "expires_at_utc": "2026-04-27T07:03:00Z",
  "content_token": "signed-short-lived-token",
  "watermark_text": "user-123 2026-04-27T07:01Z case:NP-XXXX"
}
```

Response (deny):

```json
{
  "granted": false,
  "deny_code": "rate_limited_or_out_of_scope"
}
```

### POST `/api/grievance/{grievance_id}/reveal/close`

Request:

```json
{
  "reveal_session_id": "uuid",
  "close_reason": "user_closed"
}
```

Response:

```json
{
  "ok": true
}
```

## Audit schema (minimum)

Every reveal attempt writes immutable events with this structure:

- `audit_id` (uuid)
- `event_type` (`reveal_requested`, `reveal_granted`, `reveal_denied`, `reveal_closed`, `reveal_expired`)
- `grievance_id`
- `case_sensitivity`
- `actor_id`
- `actor_role`
- `reason_code`
- `reason_text`
- `decision` (`grant`/`deny`)
- `decision_policy_version`
- `source_ip`
- `user_agent`
- `created_at_utc`
- `reveal_session_id` (nullable for denied requests)
- `duration_seconds` (for close/expiry events)

Audit ownership split:

- Public/chatbot audit (authoritative): `reveal_requested`, `reveal_granted`, `reveal_denied`, `reveal_closed`, `reveal_expired`.
- Ticketing audit (operational): UI attempts, button clicks, and correlation metadata.
- Correlate with `grievance_id`, `reveal_session_id`, and `request_id`.

## UI containment requirements

During reveal mode:

- disable text selection and copy/cut shortcuts
- disable contextual menu for copy actions where feasible
- disable print/export buttons for reveal pane
- render visible dynamic watermark over content
- auto-hide on timeout and require re-request for next reveal

Known limit:

- platform screenshots cannot be fully blocked; compensate with watermark + audit + policy/legal notice.

## SEAH-specific hardening

For `case_sensitivity = seah`:

- lower reveal session TTL
- stricter per-user/day reveal quota
- higher-priority alerts for denied and off-hours attempts
- enhanced redaction for default summary view (quasi-identifier removal)

## Alerting thresholds (initial)

- Any denied SEAH reveal: immediate security event.
- More than 3 reveals by same actor on SEAH in 1 hour: elevated alert.
- Any reveal session exceeding max TTL due to client non-close: anomaly event.
- Any actor accessing SEAH cases outside assigned scope: critical alert.

## Implementation checklist

- [ ] Public/chatbot worktree: add authoritative reveal endpoints with reason code validation.
- [ ] Public/chatbot worktree: add policy engine check for scope + sensitivity + quota.
- [ ] Public/chatbot worktree: add signed short-lived content token issuance.
- [ ] Public/chatbot worktree: add immutable sensitive-access audit events.
- [ ] Ticketing worktree: add UI reveal mode with copy/selection deterrence and watermark.
- [ ] Ticketing worktree: pass correlation IDs and close events to public endpoints.
- [ ] Ticketing + public: add alert rules and dashboards for SEAH reveal anomalies.

## Test checklist

- [ ] In-scope standard officer reveal is granted with valid reason.
- [ ] Out-of-scope reveal is denied and audited.
- [ ] Expired token cannot fetch content.
- [ ] Close event writes duration and session closure reason.
- [ ] SEAH quota/rate limits enforce stricter behavior than standard.
