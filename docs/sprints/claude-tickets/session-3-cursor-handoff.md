# Cursor Handoff — GRM Ticketing Frontend (Week 2)

**Branch:** `feature/grm-ticketing`  
**Worktree:** `~/projects/nepal_chatbot_claude` (WSL) or `\\wsl.localhost\Ubuntu\home\philg\projects\nepal_chatbot_claude` (Windows)  
**Frontend target:** `channels/ticketing-ui/` — fresh Next.js 16 app (you create this)  
**Backend:** `ticketing/` — FastAPI on port 5002, fully built and seeded

---

## 1. Start the backend

```bash
# In WSL terminal
cd ~/projects/nepal_chatbot_claude
conda activate chatbot-rest
uvicorn ticketing.api.main:app --host 0.0.0.0 --port 5002 --reload
```

Interactive docs: http://localhost:5002/docs  
Health check: http://localhost:5002/health

---

## 2. Authentication (PROTO vs PRODUCTION)

### Proto (Week 2 — what's live now)

**All officer endpoints return mock super_admin** — no token needed.  
The stub in `ticketing/api/dependencies.py → get_current_user()` always returns:
```json
{ "user_id": "mock-super-admin", "role_keys": ["super_admin"], "organization_id": "DOR" }
```

That means every GET/POST works out of the box — just call the API with no `Authorization` header.

**Inbound-only** (chatbot → ticketing) requires:
```
x-api-key: <TICKETING_SECRET_KEY from env.local>
```

### Production wiring (INTEGRATION POINT in dependencies.py)

Replace `get_current_user()` with Cognito JWT validation:
```python
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> CurrentUser:
    claims = verify_cognito_token(credentials.credentials)
    return CurrentUser(
        user_id=claims["sub"],
        role_keys=claims.get("custom:grm_roles", "").split(","),
        organization_id=claims.get("custom:organization_id", ""),
        location_code=claims.get("custom:location_code"),
    )
```
Cognito pool: `COGNITO_GRM_USER_POOL_ID` / `COGNITO_GRM_CLIENT_ID` in env.local.  
This is a **separate pool** from Stratcon. Copy the Stratcon middleware, swap the pool IDs.

---

## 3. Key data structures

### Ticket list item (GET /api/v1/tickets)
```json
{
  "ticket_id": "46662b4a-5d88-460f-9a93-27d481167ff2",
  "grievance_id": "GRV-2025-001",
  "grievance_summary": "Dust from road construction is entering homes...",
  "status_code": "GRC_HEARING_SCHEDULED",
  "priority": "HIGH",
  "is_seah": false,
  "organization_id": "DOR",
  "location_code": "MORANG",
  "project_code": "KL_ROAD",
  "assigned_to_user_id": "mock-officer-grc-chair",
  "sla_breached": false,
  "step_started_at": "2026-04-07T16:18:49+08:00",
  "created_at": "2026-04-06T16:18:49+08:00",
  "unseen_event_count": 2
}
```

### Ticket detail (GET /api/v1/tickets/{id})
Same fields as above, plus:
```json
{
  "complainant_id": "CPL-2025-001",
  "session_id": "session-demo-dust-001",
  "grievance_categories": "Environmental Impact, Health and Safety",
  "grievance_location": "Urlabari, Morang District, Province 1",
  "current_step": {
    "step_id": "00000000-0000-0000-0001-000000000013",
    "step_order": 3,
    "step_key": "LEVEL_3_GRC",
    "display_name": "Level 3 – Grievance Redress Committee (GRC)",
    "assigned_role_key": "grc_chair",
    "response_time_hours": 24,
    "resolution_time_days": 15
  },
  "events": [
    {
      "event_id": "...",
      "event_type": "CREATED",
      "old_status_code": null,
      "new_status_code": "OPEN",
      "note": "Ticket created from grievance GRV-2025-001",
      "seen": true,
      "created_at": "2026-04-06T16:18:49+08:00",
      "created_by_user_id": "system"
    }
  ]
}
```

### SLA status (GET /api/v1/tickets/{id}/sla)
```json
{
  "ticket_id": "46662b4a-...",
  "step_key": "LEVEL_3_GRC",
  "step_display_name": "Level 3 – Grievance Redress Committee (GRC)",
  "resolution_time_days": 15,
  "step_started_at": "2026-04-07T16:18:49+08:00",
  "deadline": "2026-04-22T16:18:49+08:00",
  "breached": false,
  "remaining_hours": 44.5,
  "urgency": "warning"
}
```

**SLA urgency → UI color:**
| urgency | meaning | color |
|---------|---------|-------|
| `overdue` | SLA already breached (< 0h) | 🔴 red |
| `critical` | < 24h remaining | 🔴 red |
| `warning` | < 72h remaining | 🟡 yellow |
| `ok` | > 72h remaining | 🟢 green |
| `none` | no SLA defined (e.g. L4 Legal) | — grey |

---

## 4. All endpoints

### Tickets

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/tickets` | API key | Create ticket (chatbot inbound) |
| `GET` | `/api/v1/tickets` | JWT | List / queue (see filters below) |
| `GET` | `/api/v1/tickets/{id}` | JWT | Detail + event history |
| `PATCH` | `/api/v1/tickets/{id}` | JWT | Update assignment / priority |
| `POST` | `/api/v1/tickets/{id}/actions` | JWT | Officer action (see action types) |
| `POST` | `/api/v1/tickets/{id}/reply` | JWT | Send message to complainant |
| `GET` | `/api/v1/tickets/{id}/sla` | JWT | SLA countdown data |
| `POST` | `/api/v1/tickets/{id}/seen` | JWT | Clear unread badge (204 No Content) |

#### GET /api/v1/tickets — query params
```
my_queue=true          → only tickets assigned to current user
status_code=OPEN       → OPEN | IN_PROGRESS | ESCALATED | GRC_HEARING_SCHEDULED | RESOLVED | CLOSED
is_seah=true/false     → omit = all visible to current role (SEAH gate enforced server-side)
organization_id=DOR
location_code=MORANG
project_code=KL_ROAD
sla_breached=true/false
page=1                 → 1-indexed
page_size=20           → max 100
```

#### POST /api/v1/tickets/{id}/actions — body
```json
{
  "action_type": "ACKNOWLEDGE",
  "note": "Optional officer note"
}
```

**action_type values:**
| action_type | Status change | When to show |
|-------------|--------------|-------------|
| `ACKNOWLEDGE` | → `IN_PROGRESS` | Officer takes ownership, starts SLA clock |
| `ESCALATE` | → `ESCALATED` | Manual escalation to next level (any time) |
| `RESOLVE` | → `RESOLVED` | Case resolved |
| `CLOSE` | → `CLOSED` | Close without resolution |
| `NOTE` | no change | Internal note (invisible to complainant), requires `note` field |
| `GRC_CONVENE` | → `GRC_HEARING_SCHEDULED` | GRC chair only; also add `grc_hearing_date: "2026-05-03"` |
| `GRC_DECIDE` | → `RESOLVED` or `ESCALATED` | GRC chair only; add `grc_decision: "RESOLVED"` or `"ESCALATE_TO_LEGAL"` |

#### PATCH /api/v1/tickets/{id} — body
```json
{
  "assign_to_user_id": "user-cognito-sub",
  "assigned_role_id": "optional-role-uuid",
  "priority": "HIGH"
}
```

#### POST /api/v1/tickets/{id}/reply — body
```json
{ "text": "Your grievance has been reviewed. The contractor will begin wet-spraying twice daily from tomorrow." }
```

### Workflows, Roles, Settings

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/workflows` | All workflows + steps (use for settings page) |
| `GET` | `/api/v1/workflows/{id}` | Single workflow |
| `GET` | `/api/v1/roles` | All 12 GRM roles with permissions |
| `GET` | `/api/v1/users/{user_id}/roles` | Officer role assignments |
| `POST` | `/api/v1/users/{user_id}/roles` | Assign role (admin only) |
| `DELETE` | `/api/v1/users/{user_id}/roles/{user_role_id}` | Remove role (admin only) |
| `GET` | `/api/v1/users/me/badge` | `{ "unseen_count": 3 }` — for notification badge |
| `GET` | `/api/v1/settings` | All settings |
| `GET` | `/api/v1/settings/{key}` | Single setting |
| `PUT` | `/api/v1/settings/{key}` | Upsert setting (admin only) |
| `GET` | `/api/v1/reports/export` | Download XLSX (query: date_from, date_to, organization_id) |

---

## 5. SEAH handling (critical)

**The server enforces visibility** — standard roles simply never see SEAH tickets in any list response. The frontend only needs to:

1. **Show the 🔒 SEAH badge** when `is_seah === true` on a ticket row
2. **Apply a subtle red left border** to SEAH ticket cards
3. **Never add a separate SEAH route** — same queue page, same component, different visual treatment

How to detect if current user can see SEAH:
- For proto: mock user is `super_admin` → can see everything
- For production: check if role_keys includes `seah_national_officer`, `seah_hq_officer`, `super_admin`, or `adb_hq_exec`

SEAH ticket example in DB: `GRV-2025-SEAH-001`

---

## 6. Notification badge

```
GET /api/v1/users/me/badge  → { "unseen_count": 3 }
```

- Poll on each page navigation (no WebSocket in proto — CLAUDE.md says SSE is post-proto)
- When officer opens a ticket: `POST /api/v1/tickets/{id}/seen` (204) to decrement
- The `unseen_event_count` field on each ticket list item shows per-ticket unread count
- Badge shows on "My Queue" and "Escalated" tabs (red), plain count on "Watching"

---

## 7. Status codes → UI labels

| status_code | UI label | Tab |
|-------------|----------|-----|
| `OPEN` | New | My Queue |
| `IN_PROGRESS` | In Progress | My Queue |
| `ESCALATED` | Escalated | Escalated |
| `GRC_HEARING_SCHEDULED` | GRC Hearing | My Queue (GRC chair) |
| `RESOLVED` | Resolved | Resolved |
| `CLOSED` | Closed | Resolved |

---

## 8. Queue page layout (CLAUDE.md spec)

```
Tabs: My Queue 🔴 | Watching | Escalated 🔴 | Resolved
         ↑ unseen badge           ↑ sla_breached

My Queue tiles (3 summary cards):
  • Action Needed  → status OPEN + assigned_to = me
  • Due Today      → sla deadline < 24h from now
  • Overdue 🔴     → sla_breached = true

Ticket row columns:
  [🔒 SEAH badge if is_seah]
  [urgency dot 🔴🟡🟢]
  grievance_id
  grievance_summary (truncated)
  location_code / project_code
  status badge
  assigned_to_user_id
  ⏱ SLA countdown (from /sla endpoint)
  [unseen_event_count badge]
```

Query to build each tab:
```
My Queue:  GET /api/v1/tickets?my_queue=true&status_code=OPEN,IN_PROGRESS,GRC_HEARING_SCHEDULED
Watching:  GET /api/v1/tickets?status_code=ESCALATED (not assigned to me)
Escalated: GET /api/v1/tickets?status_code=ESCALATED
Resolved:  GET /api/v1/tickets?status_code=RESOLVED,CLOSED
```

---

## 9. Ticket detail page layout (CLAUDE.md spec)

```
Left panel:
  • Grievance ID + date
  • AI summary (grievance_summary)
  • Categories, location
  • Current step + workflow level indicator (1-2-3-4 stepper)
  • SLA countdown component (from /sla)
  • Assigned officer
  • Priority badge
  • 🔒 SEAH badge if applicable

Right panel — action panel:
  • ACKNOWLEDGE button (if status=OPEN)
  • ESCALATE button (manual, any time)
  • RESOLVE button
  • CLOSE button
  • GRC CONVENE button (if step=LEVEL_3_GRC and role=grc_chair)
  • GRC DECIDE button (if status=GRC_HEARING_SCHEDULED and role=grc_chair)
  • NOTE (text area, always available)
  • Reply to complainant (text area → POST /reply)

Bottom panel — case timeline:
  • events[] rendered as a timeline
  • event_type labels: CREATED | ACKNOWLEDGED | ESCALATED | RESOLVED | NOTE_ADDED | REPLY_SENT | GRC_CONVENED | GRC_DECIDED
  • Internal notes (event_type=NOTE_ADDED) shown with 🔒 Internal label
```

**Complainant PII** (CLAUDE.md rule):
- Name: shown by default (fetch from `GET /api/grievance/{grievance_id}` on backend port 5001 — NOT implemented in ticketing API, call backend directly or proxy)
- Phone: hidden → "Reveal contact" button → log the reveal as a NOTE event
- **Never** store name/phone/email in `ticketing.*` tables

---

## 10. Demo seed data in the DB

| grievance_id | status | step | is_seah | Notes |
|---|---|---|---|---|
| GRV-2025-001 | GRC_HEARING_SCHEDULED | L3 GRC | No | Main demo: dust/health complaint, 8 events |
| GRV-2025-SEAH-001 | IN_PROGRESS | SEAH L1 | **Yes** | SEAH demo: harassment, 5 events |
| GRV-2025-002 | RESOLVED | — | No | Historical resolved case |
| GRV-2025-003 | OPEN | L1 | No | New unacknowledged ticket |
| GRV-2025-004 | ESCALATED | L3 | No | Was L2, auto-escalated by SLA watchdog |
| GRV-2025-005 | OPEN | L1 | No | SLA breached (`sla_breached=true`) |

**Mock officer user IDs** (used as `assigned_to_user_id`):
```
mock-super-admin          → super_admin @ DOR
mock-officer-site-l1      → site_safeguards_focal_person @ DOR/MORANG
mock-officer-piu-l2       → pd_piu_safeguards_focal @ DOR/PROVINCE_1
mock-officer-grc-chair    → grc_chair @ DOR/PROVINCE_1
mock-officer-grc-member-1 → grc_member @ DOR/PROVINCE_1
mock-officer-seah-national→ seah_national_officer @ DOR/PROVINCE_1
mock-officer-adb-observer → adb_hq_safeguards @ ADB
```

Re-seed from scratch anytime:
```bash
python -m ticketing.seed.mock_tickets --reset
```

---

## 11. Start commands reference

```bash
# Backend API (port 5002)
uvicorn ticketing.api.main:app --host 0.0.0.0 --port 5002 --reload

# Celery worker (SLA watchdog + notifications)
celery -A ticketing.tasks worker -Q grm_ticketing -l info -c 2

# Celery beat scheduler (triggers watchdog every 15 min)
celery -A ticketing.tasks beat -l info

# Re-seed demo data
python -m ticketing.seed.mock_tickets --reset
```

---

## 12. Frontend folder & stack (CLAUDE.md)

```
channels/ticketing-ui/    ← create fresh Next.js 16 app here
  app/
  components/
  lib/
    api.ts                ← fetch wrapper pointing at http://localhost:5002
    auth.ts               ← Cognito OIDC (copy from Stratcon, swap pool IDs)
  ...
```

Stack: **Next.js 16, TypeScript, Tailwind CSS v4, AWS Cognito OIDC**  
Reference (read-only, never fork): https://stratcon.facets-ai.com  
Stratcon repo: https://github.com/philgaeng/stratcon

Patterns to copy from Stratcon:
- Cognito OIDC middleware → officer login + route guards
- Role-based route protection
- Settings page shell
- Sidebar layout
- User management + invite flow

Target domain: **grm.facets-ai.com** (staging: grm.stage.facets-ai.com)

---

## 13. Screens to build (Week 2 priority order)

1. **Officer queue page** (main landing — tabs + tiles + ticket rows with SLA)
2. **Ticket detail + action panel** (acknowledge / escalate / resolve + reply)
3. **Case timeline** (events[] rendered chronologically)
4. **SLA countdown component** (uses /sla endpoint, color-coded by urgency)
5. **Notification badge** (header, polls /users/me/badge)
6. **SEAH visual distinction** (🔒 badge + red left border — same queue page)
7. Auth (login via Cognito OIDC, route guards by role)
8. Settings page shell (admin: workflows, users, orgs)
9. Reports page (trigger XLSX download from /reports/export)

---

*Generated by Claude Code — Session 3 complete, Apr 20 2026*  
*Backend commits: `ca7fe58` (S1) · `ff0cb7f` (S2) · `9e10f1d` (S3) on `feature/grm-ticketing`*
