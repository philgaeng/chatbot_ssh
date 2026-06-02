# Messaging Rules – WhatsApp and SMS (Staff Notifications)

**Status (June 2026):** Active policy. Implemented in operational process and referenced by the shared messaging service spec.
**Related:** [../services/05_messaging_service.md](../services/05_messaging_service.md), [03_ticketing_api_integration.md](03_ticketing_api_integration.md), [Escalation_rules.md](Escalation_rules.md)

---

## 1. Scope

This document covers **staff-facing notifications** (assignment/escalation alerts and ticket links).
It does **not** cover complainant closure messaging content.

---

## 2. Locked rules

### 2.1 No PII in staff notifications

- Do not include complainant name, phone, email, or address in SMS/WhatsApp staff alerts.
- Allowed payload: grievance reference, short category/location text, status, and ticket link.

Example:
`Escalation: GRV-2025-001 (Road safety, Morang). Open: https://grm.facets-ai.com/tickets/...`

### 2.2 WhatsApp channel constraints

- System messages are **1:1 only** when using official WhatsApp APIs.
- Group posting is not supported by official APIs; do not use unofficial automation.
- If groups are required operationally, use a **human bridge** who forwards link-only summaries.

### 2.3 Group hygiene: links-only

- In WhatsApp groups, do not post screenshots/files directly.
- Upload evidence to managed storage and share links.
- Keeps auditability and access control outside chat history.

### 2.4 SMS is default/fallback

- Use SMS as primary fallback for reliability and approval simplicity.
- WhatsApp can be used where business verification/templates are already in place.

---

## 3. Operational model

| Actor | Channel | Rule |
|---|---|---|
| System → Officers | SMS (default) or WhatsApp 1:1 | Link-only, no PII |
| Bridge person | WhatsApp groups | Forward summary + link only |
| Managers / Boss | 1:1 digest or group | No attachments, links only |

---

## 4. Compliance

- Notification sends and contact reveal actions are auditable.
- Staff training includes: no PII in messages, no file uploads in group chats, links only.
