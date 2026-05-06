## Messaging API – Specs (SMS & Email as Services)

This document specifies the **Messaging API** that exposes SMS and email as HTTP services so that **any system** (chatbot, ticketing, gsheet, external tools) can send messages through a single, policy‑controlled layer.

The key design rule is:
- **Callers** (chatbot, ticketing, etc.) are responsible for **content** (subject, body, links, language).
- The **Messaging API** is responsible only for **delivery** (SMS/email), validation, logging, and enforcement of basic rules (e.g. “no PII in SMS” if configured).

Messaging remains implemented by `backend/services/messaging.py` (SNS/SES), but it is always invoked through HTTP routes.

---

## 1. Goals and Non‑Goals

- **Goals**
  - Provide a **single HTTP API** for sending SMS and email.
  - Allow **multiple callers** (chatbot, ticketing UI, gsheet backend, future tools) to send notifications without knowing SNS/SES details.
  - Centralize **logging, throttling, and policy checks** for all messages.
  - Keep **message templates and wording** on the caller side (chatbot/app), not in the Messaging API.

- **Non‑Goals (v1)**
  - No full template engine or multi‑language catalog in the Messaging API.
  - No group messaging / broadcast lists (callers loop and call per recipient).
  - No WhatsApp transport in v1 (only SMS + email); WhatsApp is handled separately and may share concepts later.

---

## 2. API Surface

Base path (suggested): `/api/messaging`

### 2.1 `POST /api/messaging/send-sms`

**Purpose**

- Send a single SMS message to one recipient, with optional context for audit.

**Request**

```json
{
  "to": "+9779800000000",
  "text": "Escalation: grievance #abc123 – Road safety, KL Road. Link: https://...",
  "context": {
    "source_system": "chatbot", 
    "purpose": "escalation_notification",
    "grievance_id": "abc123",
    "ticket_id": "T-2025-0001",
    "office_user": "kl_road_officer_1",
    "channel": "sms",
    "client_message_id": "optional-id-for-idempotency"
  }
}
```

- **Fields**
  - `to` (string, required): Phone number in any local format acceptable to `Messaging.format_phone_number`; API will normalize to E.164 (e.g. `+977...` or `+63...`) using `SMSClient._format_phone_number`.
  - `text` (string, required): Raw SMS body as decided by the caller.  
    - **Policy:** Per [08_messaging_rules_whatsapp_sms.md](08_messaging_rules_whatsapp_sms.md), callers **must not** include complainant PII in SMS content for staff notifications.
  - `context` (object, optional): Arbitrary metadata for logging and troubleshooting.
    - Recommended keys: `source_system`, `purpose`, `grievance_id`, `ticket_id`, `office_user`, `channel`, `client_message_id`.

**Response (success)**

```json
{
  "status": "SUCCESS",
  "message": "SMS sent",
  "message_id": "provider-or-internal-id",
  "to": "+9779800000000"
}
```

**Response (error)**

```json
{
  "status": "FAILED",
  "error_code": "VALIDATION_ERROR|DELIVERY_ERROR|RATE_LIMITED|UNAUTHORIZED",
  "error": "Human readable description"
}
```

**Behaviour**

- Validates `to` and `text` (non‑empty, length under provider limit).
- Uses `Messaging().send_sms(to, text)` internally, which:
  - Normalizes number, enforces whitelist (`WHITELIST_PHONE_NUMBERS_OTP_TESTING`) and `SMS_ENABLED`.
  - Sends via AWS SNS (region `AWS_REGION`).
- Logs a structured event via `TaskLogger` including:
  - `to`, truncated `text`, full `context`, outcome, provider id or error.
- Returns `SUCCESS` only if SNS call succeeded and `SMS_ENABLED` allowed sending.

---

### 2.2 `POST /api/messaging/send-email`

**Purpose**

- Send one email (possibly to multiple recipients) with pre‑built subject and HTML body.

**Request**

```json
{
  "to": ["user@example.org", "boss@example.org"],
  "subject": "Grievance #abc123 escalated to Level 2",
  "html_body": "<p>Escalation: grievance <b>#abc123</b> – Road safety, KL Road. <a href=\"https://...\">Open ticket</a></p>",
  "context": {
    "source_system": "ticketing",
    "purpose": "escalation_notification",
    "grievance_id": "abc123",
    "ticket_id": "T-2025-0001",
    "office_user": "kl_road_officer_1",
    "channel": "email",
    "client_message_id": "optional-id-for-idempotency"
  }
}
```

- **Fields**
  - `to` (array of strings, required): Recipient email addresses.
  - `subject` (string, required): Email subject, as decided by the caller.
  - `html_body` (string, required): HTML body.
  - `context` (object, optional): Same idea as for SMS.

**Response (success)**

```json
{
  "status": "SUCCESS",
  "message": "Email sent",
  "message_id": "ses-message-id",
  "to": ["user@example.org", "boss@example.org"]
}
```

**Response (error)**

```json
{
  "status": "FAILED",
  "error_code": "VALIDATION_ERROR|DELIVERY_ERROR|RATE_LIMITED|UNAUTHORIZED",
  "error": "Human readable description"
}
```

**Behaviour**

- Validates `to` array is non‑empty and contains syntactically valid emails.
- Uses `Messaging().send_email(to, subject, html_body)` internally (SES, region `AWS_REGION`, `SES_VERIFIED_EMAIL` as sender).
- Logs via `TaskLogger` (recipients, truncated subject/body, context, provider id or error).

---

### 2.3 Future: `POST /api/messaging/send-batch` (optional, v2)

- Allow sending multiple messages (SMS or email) in one call:
  - Request body: `{ "messages": [ { ...same as above per message... } ] }`.
  - Response includes result per item.
- v1 callers can simply call `/send-sms` and `/send-email` in a loop.

---

## 3. Auth, Rate Limiting, and Policy

### 3.1 Authentication

- Messaging API is **internal only**; only trusted services should call it:
  - Chatbot backend / orchestrator.
  - Ticketing service.
  - Backend gsheet/monitoring tasks.
- Recommended auth options (to be finalized in security spec):
  - **Service API key** in header (e.g. `x-api-key`).
  - Or **JWT** with service claims (e.g. `sub=chatbot_service`).
- Unauthorized requests return HTTP 401/403 with `status: FAILED` and `error_code: UNAUTHORIZED`.

### 3.2 Rate Limiting / Quotas

- Basic per‑service and global rate limits to protect SNS/SES quotas:
  - Example: N SMS per minute per `source_system`; global cap per hour.
  - Example: M emails per minute; burst/peak limits.
- On rate limit hit, return HTTP 429 with `error_code: RATE_LIMITED`.
- Exact thresholds are configuration, not hard‑coded in the spec.

### 3.3 Content Policy Hooks

- While **callers own content**, Messaging API can enforce simple rules:
  - Maximum message length (SMS).
  - Optional regex / keyword checks (e.g. disallow obvious PII patterns in SMS for staff notifications).
  - Logging `purpose` to allow future per‑purpose policy decisions.
- For now, the primary enforcement of “no PII in staff notifications” is **process and documentation** (see `08_messaging_rules_whatsapp_sms.md`); technical checks are an optional enhancement.

---

## 4. Callers and Responsibilities

### 4.1 Chatbot / Orchestrator

- **Can call** `/api/messaging/send-sms` and `/send-email` for:
  - OTP delivery (if not already using a direct provider).
  - User‑facing notifications (e.g. grievance submission confirmation).
  - Staff notifications (e.g. internal alerts).
- **Must:**
  - Build the full `text` / `subject` / `html_body`.
  - Include useful `context` (grievance_id, ticket_id, purpose).
  - Respect messaging rules (no PII in staff SMS/WhatsApp per `08_messaging_rules_whatsapp_sms.md`).

### 4.2 Ticketing System

- **Can call** Messaging API for:
  - Assignee notifications (new ticket, escalation, SLA breach).
  - Admin reports / digests (daily/weekly email).
  - Optional complainant notifications (if policy allows SMS/email to complainants via this API).
- **Must:**
  - Use `source_system: "ticketing"` in `context`.
  - Use purpose tags like `escalation_notification`, `assignment_notification`, `digest`.
  - Use links to the ticket/grievance instead of embedding sensitive content.

### 4.3 Gsheet / Monitoring Flows

- **Can call** Messaging API indirectly via backend logic (e.g. when an escalation is triggered from `EscalationRules` or from gsheet actions).
- **Must:** Follow same rules as ticketing and chatbot regarding PII and links.

---

## 5. Error Model and Logging

### 5.1 HTTP Status Codes

- `200` – Request accepted and processed (even if provider returned non‑fatal warnings).
- `400` – Validation error (missing fields, invalid phone/email).
- `401/403` – Authentication/authorization failure.
- `429` – Rate limited.
- `500` – Unexpected internal error (exceptions, provider unavailability).

### 5.2 Response Envelope

- Always returns JSON with:

```json
{
  "status": "SUCCESS|FAILED",
  "message": "optional human-readable message",
  "message_id": "optional provider/internal id",
  "error_code": "optional machine-readable error code",
  "error": "optional error description"
}
```

### 5.3 Logging

- Each request/response pair is logged with:
  - Timestamp.
  - Caller identity (from auth).
  - Transport (`sms` / `email`).
  - Destination (phone/email; may be redacted in logs if required).
  - Truncated content (e.g. first 100 chars).
  - Context object.
  - Result (`SUCCESS` / `FAILED`, `error_code`, provider ids).

---

## 6. Implementation Notes

- **Location:** Implement routes in the FastAPI backend (e.g. a new router `backend/api/routers/messaging.py`).
- **Internal usage:** Existing Python code that currently calls `messaging.send_sms` / `send_email` directly should gradually be migrated to call the HTTP API, or to go through a small internal client that hits these endpoints.
- **Testing:** Provide a non‑production configuration where:
  - SMS is disabled or forced into whitelist only.
  - Emails are sent to a sandbox or logged only.
  - The API still behaves the same, allowing integration testing without sending real messages.

---

## 7. References

- Messaging implementation: `backend/services/messaging.py`
- Backend architecture: `docs/BACKEND.md`
- Ticketing API integration: `03_ticketing_api_integration.md` (section “Ticketing → Messaging API”)
- Staff messaging rules (WhatsApp/SMS): `08_messaging_rules_whatsapp_sms.md`
