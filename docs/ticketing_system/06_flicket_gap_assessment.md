# Flicket Gap Assessment – Matching Our Ticketing Specs

This document assesses what needs to be done to adapt [Flicket](https://github.com/evereux/flicket) to match our ticketing specifications ([00_ticketing_decisions.md](00_ticketing_decisions.md), [02_ticketing_domain_and_settings.md](02_ticketing_domain_and_settings.md), [Escalation_rules.md](Escalation_rules.md), [03_ticketing_api_integration.md](03_ticketing_api_integration.md), [04_ticketing_schema.md](04_ticketing_schema.md)).

**Flicket snapshot**: Python 3.90+, Flask, SQLAlchemy, PostgreSQL/MySQL/SQLite, MIT license, ~140 stars, 65 forks, 499 commits, last release 0.3.5 (Jun 2024).

---

## 1. What Flicket Already Provides

| Area | Flicket | Notes |
|------|---------|-------|
| **Stack** | Python, Flask, SQLAlchemy | Aligns with our Python preference; PostgreSQL supported |
| **Ticket model** | `FlicketTicket` (flicket_topic): id, title, content, started_id, assigned_id, status_id, category_id, ticket_priority_id | Basic ticket CRUD; no grievance/workflow linkage |
| **Departments & categories** | `FlicketDepartment` → `FlicketCategory` | Hierarchical; can partially map to org/location with extension |
| **Status & priority** | `FlicketStatus`, `FlicketPriority` | Fixed lookup tables; not workflow-step based |
| **Users & auth** | `FlicketUser`, groups (flicket_admin, super_user), token auth for API | Internal user store; no Cognito |
| **REST API** | `/flicket-api/tickets`, create/get/list, Bearer token | [API docs](https://flicket.readthedocs.io/en/latest/api.html); create requires title, content, category_id, ticket_priority_id |
| **Ticket actions** | `FlicketAction` (assign, status change, etc.) | Audit trail; can extend for escalation events |
| **Posts** | `FlicketPost` – replies/thread per ticket | Conversation thread |
| **Notifications** | Flask-Mail (in-process) | Not Messaging API |
| **UI** | Jinja2 templates, Bootstrap-style | Web UI; not “tiles” / Node.js SPA |
| **i18n** | Flask-Babel, en/fr | Can add more locales |

---

## 2. Gaps vs. Our Specs

### 2.1 Data model & domain

| Our spec | Flicket | Gap |
|----------|---------|-----|
| `grievance_id`, `complainant_id` | Not present | Add columns or extension table linking ticket ↔ grievance |
| `chatbot_id` | Not present | Add column |
| `organization_id`, `location_code`, `project_code` | Department/category exist but different semantics | Add columns or new `organizations`, `locations` tables |
| `session_id` (for “reply in chat”) | Not present | Add column |
| Workflow (steps, SLA, escalation) | None | New tables: `workflow_definitions`, `workflow_steps`, `workflow_assignments` |
| Ticket ↔ workflow step | None | Add `current_workflow_id`, `current_step_id`, `assigned_role_id` |
| Configurable roles (TOR GRMS) | Groups (flicket_admin, super_user) hard-coded | New `roles`, `user_roles` with permissions, org/location scope |
| Ticket events (CREATED, ESCALATED, etc.) | `FlicketAction` tracks some actions | Extend or add `ticket_events` for full audit with workflow_step_id |
| Settings (workflow, integration URLs) | Config in `config.json` | Add `settings` table or extend config for DB-driven settings |

### 2.2 Workflows, SLA, and escalation

| Our spec | Flicket | Gap |
|----------|---------|-----|
| Configurable workflows | None | Implement from scratch |
| Configurable escalation levels | None | Implement from scratch |
| SLA per level (response_time_hours, resolution_time_days) | None | Implement from scratch |
| Auto-escalation when SLA exceeded | None | Background job (Celery or cron) to check SLA, advance step, reassign |
| Last level with “no timeline” | N/A | Support `resolution_time_days = NULL` in workflow steps |

### 2.3 API

| Our spec | Flicket | Gap |
|----------|---------|-----|
| `POST /api/v1/tickets` with grievance_id, chatbot_id, org, location, project, priority | `POST /flicket-api/tickets` with title, content, category_id, ticket_priority_id | Extend API: new fields, map category/department to org/location or add new params |
| `POST /api/v1/tickets/{id}/link-conversation` | None | New endpoint |
| API auth for chatbot (API key / service account) | Bearer token (user) | Add API-key or service-account auth for machine-to-machine |
| Idempotency (409 if ticket exists for grievance_id) | None | Add check on create |

### 2.4 Integration

| Our spec | Flicket | Gap |
|----------|---------|-----|
| Chatbot creates ticket via API | Possible with extended API | Ensure create payload matches our contract |
| Ticketing → Messaging API (SMS/email) | Flask-Mail only | Replace with HTTP client to Messaging API |
| Ticketing → Orchestrator `POST /message` | None | New outbound client |
| Ticketing → Backend `GET /api/grievance/{id}` | None | New outbound client for grievance details |

### 2.5 Identity & access

| Our spec | Flicket | Gap |
|----------|---------|-----|
| AWS Cognito | Internal users only | Integrate Cognito (e.g. JWT validation, map Cognito sub → FlicketUser or new user_roles) |
| Roles 100% configurable | Hard-coded groups | New roles/permissions model |
| Access scoped by org/location | Not applicable | Implement in queries and API |

### 2.6 UI

| Our spec | Flicket | Gap |
|----------|---------|-----|
| “Modern tiles” UX | Standard list/detail | May require frontend overhaul or new dashboard |
| English only | en/fr | Restrict to English acceptable |
| Usable by Nepali staff | Generic UI | Accessibility and usability review |

---

## 3. Effort Overview (Rough)

| Work area | Effort | Notes |
|-----------|--------|-------|
| **Schema extensions** | Medium | New columns on FlicketTicket, new tables for workflow/org/location/roles; migrations |
| **Workflow engine** | High | New tables, logic to resolve workflow per ticket, assignment by role |
| **Escalation worker** | Medium | Celery task or cron; read SLA, escalate, reassign, log events, call Messaging API |
| **API extensions** | Medium | New endpoints, payload changes, API-key auth |
| **Messaging API integration** | Low–Medium | Replace Flask-Mail with HTTP client; template handling |
| **Cognito integration** | Medium | Auth middleware, user mapping |
| **Roles/permissions** | Medium | New model, migrate from groups, apply in views/API |
| **Outbound clients** | Low | Orchestrator, Backend HTTP clients |
| **UI refresh** | Medium–High | If “tiles” require new frontend; else incremental |

---

## 4. Recommended Approach

### 4.1 Strategy

- **Use Flicket as base**: Keep core ticket CRUD, posts, UI structure, and API where possible.
- **Extend, don’t replace**: Add tables and columns; keep Flicket’s models as the primary ticket store.
- **Isolate new logic**: Workflow and escalation in separate modules; call into Flicket for ticket updates.

### 4.2 Phased implementation

1. **Phase 1 – Schema & minimal integration**
   - Add grievance_id, complainant_id, chatbot_id, organization_id, location_code, project_code, session_id to `FlicketTicket` (or an extension table).
   - Add `organizations`, `locations` if not mapped to departments.
   - Extend `POST /flicket-api/tickets` (or add `/api/v1/tickets`) to accept grievance_id, etc., and create FlicketTicket.
   - Add `POST /api/v1/tickets/{id}/link-conversation`.

2. **Phase 2 – Workflow & roles**
   - Add `workflow_definitions`, `workflow_steps`, `workflow_assignments` (as in [04_ticketing_schema.md](04_ticketing_schema.md)).
   - Add `roles`, `user_roles` with org/location scope.
   - Add current_workflow_id, current_step_id, assigned_role_id to ticket (or link table).
   - Seed KL Road 4-level workflow.

3. **Phase 3 – Escalation & notifications**
   - Escalation worker: periodic job to check SLA, advance step, reassign.
   - Replace Flask-Mail with Messaging API client.
   - Add `ticket_events` (or extend FlicketAction) for CREATED, ESCALATED, etc.

4. **Phase 4 – Auth & UI**
   - Cognito integration for web users.
   - API-key auth for chatbot/backend.
   - UI improvements for “tiles” if required.

### 4.3 Schema options

- **Option A – Extend Flicket tables**: Add columns to `flicket_topic`; add new tables in same DB/schema. Simpler, but ties us to Flicket’s schema.
- **Option B – Separate ticketing schema**: Put our workflow/org/events in a `ticketing` schema; link to Flicket’s `flicket_topic` via grievance_id or a shared ticket_id. Cleaner separation, easier to migrate later.

Recommendation: **Option B** if we may move away from Flicket; **Option A** for fastest path.

---

## 5. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Flicket is a small project (~140 stars) | Fork and maintain internally; treat as a base, not a dependency |
| Flicket upgrades may conflict with our extensions | Isolate extensions in separate modules; document migration path |
| Workflow logic is substantial | Implement in dedicated package; keep Flicket views/models thin |
| Cognito + Flicket user model | Use Cognito as primary; sync or map to FlicketUser for compatibility |

---

## 6. Conclusion

Flicket provides a usable Python/Flask ticketing base (tickets, posts, API, UI) but **does not** provide workflows, SLA, escalation, org/location scoping, grievance linkage, or Messaging API integration. Adapting it requires:

- **Schema**: New columns and tables for grievance linkage, workflow, roles, org/location.
- **Logic**: Workflow engine, escalation worker, and outbound integrations.
- **API**: Extended create endpoint, link-conversation, and machine auth.
- **Auth**: Cognito for users, API key for services.

Rough effort: **8–14 weeks** for a small team, depending on UI scope and Cognito integration depth. The main advantage is reusing ticket CRUD, posts, and basic UI; the main cost is implementing and maintaining the workflow and escalation layer on top of Flicket’s simpler model.
