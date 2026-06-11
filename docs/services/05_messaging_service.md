# Messaging Service Spec

## 1) Scope

This is the production contract for shared messaging functionality used across the project.

Source implementation:

- API router: `backend/api/routers/messaging.py`
- service implementation: `backend/services/messaging.py`
- SMTP env resolution: `backend/config/smtp_config.py`
- client wrappers: `backend/clients/messaging_api.py`, `ticketing/clients/messaging_api.py`

This spec is intentionally outside `docs/rest_chatbot` because messaging is cross-project.

## 2) API Endpoints

### `POST /api/messaging/send-sms`

Request body:

- `to` (string, required)
- `text` (string, required)
- `context` (optional object)

SMS delivery provider is selected via env (`backend/config/sms_config.py`):

| `SMS_PROVIDER` | Transport | Notes |
|----------------|-----------|--------|
| `doit` (default when `DOIT_SMS_BEARER_TOKEN` is set) | [DOIT SMS gateway](https://sms.doit.gov.np/developer-guide/) | Production Nepal — `POST /api/sms` |
| `aws_sns` | AWS SNS | Dev / international fallback; PH `+63` numbers, whitelist gate |
| `disabled` | — | No outbound SMS |

Set `SMS_ENABLED=true` to allow sends. AWS SNS path still respects `WHITELIST_PHONE_NUMBERS_OTP_TESTING` when `SMS_WHITELIST_ONLY` is true (default for `aws_sns`).

### `POST /api/messaging/send-email`

Request body:

- `to` (array of emails, required)
- `subject` (string, required)
- `html_body` (string, required)
- `context` (optional object)
  - `attachments` (optional array): `{ filename, content_base64, content_type? }`

Email is delivered via **SMTP** (mailbox relay). See §6.

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
- `attachments` — email attachments (see send-email above)
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

## 6) Email (SMTP)

Email is sent by `EmailClient` in `backend/services/messaging.py` using your provider's SMTP relay (STARTTLS, port 587 by default). The same `SMTP_*` env vars are used for Keycloak officer invite email (`ticketing/auth/keycloak_smtp.py`).

| Variable | Required | Notes |
|----------|----------|-------|
| `SMTP_SERVER` | yes | e.g. `mail.infomaniak.com` |
| `SMTP_PORT` | no | default `587` |
| `SMTP_USERNAME` | yes | SMTP auth user |
| `SMTP_PASSWORD` | yes | In `env.local`, `$$` = literal `$` for Docker Compose |
| `SMTP_FROM` | yes* | From address (*falls back to `SMTP_USERNAME`) |
| `SMTP_FROM_DISPLAY` | no | default `GRM Ticketing` |

After changing SMTP env for Keycloak, apply to the `grm` realm:

```bash
docker compose -f docker-compose.yml -f docker-compose.grm.yml --profile auth \
  exec ticketing_api_auth python -m ticketing.auth.keycloak_setup
```

## 7) Internal Usage Patterns

Messaging service is used by:

- chatbot submission/status notifications (grievance recap emails)
- grievance status update endpoint logic
- ticketing: officer password reset, quarterly report delivery
- Celery `send_email_task` (via `backend/clients/messaging_api.py`)

Preferred internal usage from backend code:

- `backend.clients.messaging_api.send_sms(...)`
- `backend.clients.messaging_api.send_email(...)`

Ticketing callers use `ticketing.clients.messaging_api` (HTTP to the same backend routes).

## 8) Operational Notes

- **No self-hosted mail server** — use your provider's SMTP relay (Infomaniak, Nepal local provider, Google Workspace, etc.).
- API callers should treat messaging as best-effort and handle failed delivery gracefully.
- Quarterly report XLSX attachments are sent via `context.attachments`.
| `DOIT_SMS_BEARER_TOKEN` | yes (doit) | Bearer token from [newsms.doit.gov.np](https://newsms.doit.gov.np) |
| `DOIT_SMS_BASE_URL` | no | default `https://sms.doit.gov.np` |
| `SMS_PROVIDER` | no | `doit` \| `aws_sns` \| `disabled` |
| `SMS_ENABLED` | no | `true` to send (falls back to `constants.SMS_ENABLED` if unset) |
| `SMS_WHITELIST_ONLY` | no | default `true` for `aws_sns`, `false` for `doit` |

- Email and SMS are independent transports.
