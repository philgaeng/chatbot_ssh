# Messaging Service Spec

## 1) Scope

This is the production contract for shared messaging functionality used across the project.

Source implementation:

- API router: `backend/api/routers/messaging.py`
- service implementation: `backend/services/messaging.py`
- client wrappers: `backend/clients/messaging_api.py`

This spec is intentionally outside `docs/rest_chatbot` because messaging is cross-project.

## 2) API Endpoints

### `POST /api/messaging/send-sms`

Request body:

- `to` (string, required)
- `text` (string, required)
- `context` (optional object)

### `POST /api/messaging/send-email`

Request body:

- `to` (array of emails, required)
- `subject` (string, required)
- `html_body` (string, required)
- `context` (optional object)

## 3) Authentication

Auth header:

- `x-api-key`

Accepted key:

- `MESSAGING_API_KEY` if set, otherwise
- `TICKETING_SECRET_KEY` if set

If no expected key is configured, auth is effectively bypassed.

Invalid key response:

- HTTP `403`
- detail payload with `status=FAILED` and `error_code=UNAUTHORIZED`

## 4) Request Context Contract

Optional `context` fields:

- `source_system`
- `purpose`
- `grievance_id`
- `ticket_id`
- `office_user`
- `channel`
- `client_message_id`
- `extra` (extensible map)

Context is used for observability/auditing and caller intent tracking.

## 5) Response Contract

Success:

- `status: "SUCCESS"`
- `message: "SMS sent"` or `"Email sent"`

Delivery failure:

- `status: "FAILED"`
- `error_code: "DELIVERY_ERROR"`
- `error` message

Validation/internal errors:

- router raises HTTP errors with structured failure details
- common error codes:
  - `VALIDATION_ERROR`
  - `INTERNAL_ERROR`

## 6) Internal Usage Patterns

Messaging service is used by:

- chatbot submission/status notifications
- grievance status update endpoint logic
- ticketing and other backend integrations via API clients

Preferred internal usage from backend code:

- `backend.clients.messaging_api.send_sms(...)`
- `backend.clients.messaging_api.send_email(...)`

These centralize API calling behavior and context shape.

## 7) Operational Notes

- Delivery transport details (SNS/SES etc.) are encapsulated in `backend/services/messaging.py`.
- API callers should treat messaging as best-effort and handle failed delivery gracefully.
- This service is a shared dependency and should remain backward-compatible for existing callers.
