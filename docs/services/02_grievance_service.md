# Grievance Service Spec

## 1) Scope

Shared grievance retrieval and status management API used by chatbot, ticketing, and monitoring integrations.

Primary implementation:

- `backend/api/routers/grievance.py`
- `backend/services/database_services/grievance_manager.py`

## 2) API Endpoints

### `GET /api/grievance/statuses`

Returns available grievance status codes.

Success shape:

- `status: "SUCCESS"`
- `message`
- `data` (list of statuses)

### `GET /api/grievance/{grievance_id}`

Returns grievance detail bundle:

- `grievance`
- `current_status`
- `status_history`
- `files`

Success shape:

- `status: "SUCCESS"`
- `message`
- `data` object

### `POST /api/grievance/{grievance_id}/status`

Updates grievance status.

Request body:

- `status_code` (required)
- `notes` (optional)
- `created_by` (optional)

Behavior:

- Updates status in DB
- Triggers notification flow (office email + complainant SMS) via messaging client wrappers

### `PATCH /api/complainant/{complainant_id}`

Auth-gated complainant update endpoint for integrations (for example ticketing).

Auth:

- `x-api-key` checked against `TICKETING_SECRET_KEY` when configured

Allowed fields (whitelist):

- `complainant_address`
- `complainant_village`
- `complainant_ward`
- `complainant_municipality`
- `complainant_district`
- `complainant_province`
- `complainant_email`

Disallowed by design:

- identity/phone fields (`full_name`, `phone`, etc.)

## 3) Error Behavior

Typical responses:

- `404` for unknown grievance/complainant
- `422` for empty or invalid update field set
- `500` for internal errors

## 4) Cross-Service Dependencies

- Messaging API client (`backend/clients/messaging_api.py`) for notifications
- Database layer (`db_manager` / grievance manager methods)
