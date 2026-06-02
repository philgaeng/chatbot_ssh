# GSheet Monitoring Service Spec

## 1) Scope

Read-only monitoring API used by Google Sheets and office-monitoring consumers.

Implementation:

- `backend/api/routers/gsheet.py`

## 2) Endpoint

### `GET /gsheet-get-grievances`

Query params:

- `status` (optional)
- `start_date` (optional)
- `end_date` (optional)

Auth header:

- `Authorization: Bearer <token_or_username>`

Accepted auth modes:

1. exact token match against `GSHEET_BEARER_TOKEN`
2. office user identity:
   - static aliases (`pd_office`, `adb_hq`, `Adb_hq`) or
   - active office user in DB (`office_user` table)

Success response:

- `status: "SUCCESS"`
- `message`
- `data: { count, data: [...] }`

Failure responses:

- `403` invalid token/username
- `500` internal errors

## 3) Data Source

Uses database service method:

- `db_manager.gsheet.get_grievances_for_gsheet(...)`

This service is read-only and intended for reporting/monitoring surfaces.
