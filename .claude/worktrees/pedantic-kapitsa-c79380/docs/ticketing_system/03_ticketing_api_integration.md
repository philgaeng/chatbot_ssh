# Ticketing System – API Integration

The ticketing system integrates with the rest of the ecosystem **only through APIs**. This document describes the **v1 API contracts** (inbound and outbound) at a practical level.

---

## 1. Chatbot / Backend → Ticketing (Inbound)

The chatbot (or its backend) calls the **Ticketing API** to create and update tickets.

### 1.1 Create ticket (from submitted grievance)

- **When**: After a grievance is successfully submitted (e.g. after OTP verification and DB persistence).
- **Who**: Backend or orchestrator (same process that creates the grievance) calls Ticketing API.
- **Contract (conceptual)**:
  - `POST /api/tickets` (or `/api/v1/tickets`)
  - Body: `grievance_id`, `chatbot_id`, `source` (country, organization_id, location), optional `session_id`, optional `priority`, optional `category`.
  - Response: `ticket_id`, `status`, `created_at`.

The ticketing system may store a copy of key grievance fields or only the reference; when details are needed (e.g. for approval UI), it can fetch from the Backend Grievance API (see below) if that is the chosen design.

### 1.2 Update ticket (optional)

- **When**: Grievance updated (e.g. status change, additional details).
- **Contract**: `PATCH /api/tickets/{ticket_id}` with fields to update (e.g. status, metadata). Optional for v1 if all updates are done inside the ticketing system.

### 1.3 Link conversation (optional)

- **When**: To associate a ticket with a conversation for “view in chat” or “reply in chat”.
- **Contract**: `POST /api/tickets/{ticket_id}/link` with `session_id` (or `conversation_id`) and optionally `chatbot_id`. Ticketing stores the link and uses it when calling the chatbot to send a message.

---

## 2. Ticketing → Chatbot (Outbound)

When an agent wants to **send a message to the complainant** (or receive bot replies), the ticketing system calls the **Orchestrator** (or backend) API.

### 2.1 Send message to user (conversation)

- **When**: Agent sends a reply in the context of a ticket (e.g. “We have reviewed your case…”).
- **Contract**: Same as current Orchestrator `POST /message`:
  - Body: `user_id` (e.g. session_id or complainant identifier), `message_id`, `text`, `payload`, `channel`.
  - Response: `messages`, `next_state`, `expected_input_type`.

The ticketing system uses the stored `session_id` (or equivalent) as `user_id` so the message is delivered in the same conversation. Base URL for the orchestrator is configured in ticketing settings (per chatbot_id).

### 2.2 Get conversation history (optional, v2)

- **When**: Ticket UI shows “Conversation” tab.
- **Contract**: e.g. `GET /api/conversations/{session_id}/history` (or equivalent) if the orchestrator/backend exposes it. If not, v1 can omit this and only support “send message” and a link to the chat channel.

---

## 3. Ticketing → Backend Grievance API (Outbound, optional)

If the ticketing system does **not** store full grievance payload, it can fetch details from the existing **Backend API**.

- **Contract**: Use existing endpoints, e.g.:
  - `GET /api/grievance/{grievance_id}` – full grievance details.
  - `GET /api/grievance/statuses` – list of statuses.

Ticketing needs the **base URL** of the backend (per chatbot or per deployment) in settings. Same network/security rules as today (e.g. internal only, or with API key).

---

## 4. Ticketing → Messaging API (Outbound)

All **SMS and email** sent by the ticketing system (e.g. assignee notified, complainant status update) go through the **Messaging API**, not in-process code.

### 4.1 Send SMS

- **Contract**: e.g. `POST /api/messaging/send-sms` with recipient, body, optional template_id.
- **When**: After assignment, escalation, or status change, according to workflow/settings.

### 4.2 Send email

- **Contract**: e.g. `POST /api/messaging/send-email` with to, subject, body, optional template_id.
- **When**: Same as above.

The Messaging API is the same one used by the chatbot backend (see [BACKEND.md](../BACKEND.md)). If it does not exist yet, it can be added on the backend (FastAPI) and used by both the backend and the ticketing system.

---

## 5. Authentication and Authorization

- **Inbound (Chatbot/Backend → Ticketing)**  
  Ticketing API must authenticate the caller (e.g. API key, JWT). Only allowed clients (e.g. backend service) should create/update tickets.

- **Outbound (Ticketing → Chatbot, Backend, Messaging)**  
  Ticketing acts as a client; it needs credentials (API key or service account) to call Orchestrator, Backend, and Messaging API. Store in settings/env, not in code.

Detailed auth scheme (API key vs JWT, scopes) to be defined in a security spec.

---

## 6. Summary Table

| Direction | Purpose | Contract |
|-----------|--------|----------|
| Chatbot/Backend → Ticketing | Create/update ticket, link conversation | `POST /api/tickets`, `PATCH /api/tickets/{id}`, `POST /api/tickets/{id}/link` |
| Ticketing → Chatbot (Orchestrator) | Send message to user | `POST /message` (existing) |
| Ticketing → Backend | Get grievance details | `GET /api/grievance/{id}` (existing) |
| Ticketing → Messaging | Send SMS/email | `POST /api/messaging/send-sms`, `POST /api/messaging/send-email` (to be added if not present) |

---

## Next Steps

1. Answer the [first questions](00_ticketing_overview_and_questions.md#first-questions-to-answer) and record decisions.
2. Implement or confirm Messaging API on the backend so ticketing can depend on it.
3. Add Ticketing API routes (FastAPI) for `POST /api/tickets` (and optionally PATCH, link) with auth.
4. Implement outbound clients in the ticketing service for Orchestrator, Backend, and Messaging API using settings for base URLs and credentials.
