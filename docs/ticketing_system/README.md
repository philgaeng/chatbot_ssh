# GRM Ticketing System – Documentation Index

> Last updated: June 2026. Reflects as-built state.

---

## Core specs

| Document | Contents | Status |
|---|---|---|
| [`00_ticketing_decisions.md`](00_ticketing_decisions.md) | All settled product, architecture, and integration decisions | ✅ Current |
| [`00_ticketing_overview_and_questions.md`](00_ticketing_overview_and_questions.md) | Vision, goals, integration diagram, deployment URLs | ✅ Current |
| [`01_ticketing_scope_and_stack.md`](01_ticketing_scope_and_stack.md) | Scope, full tech stack, repo layout, Docker compose | ✅ Current |
| [`02_ticketing_domain_and_settings.md`](02_ticketing_domain_and_settings.md) | All entities: ticket, events, workflow, org, project, package, QR, users, settings | ✅ Current |
| [`03_ticketing_api_integration.md`](03_ticketing_api_integration.md) | Full API endpoint reference (inbound + outbound + all routes) | ✅ Current |
| [`04_ticketing_schema.md`](04_ticketing_schema.md) | Postgres schema for all ~25 `ticketing.*` tables + migration history | ✅ Current |
| [`05_ticketing_impl_plan.md`](05_ticketing_impl_plan.md) | As-built status by phase; remaining/planned work | ✅ Current |
| [`06_messaging_rules_whatsapp_sms.md`](06_messaging_rules_whatsapp_sms.md) | Staff messaging policy (WhatsApp/SMS rules) | ✅ Current |
| [`Escalation_rules.md`](Escalation_rules.md) | SLA rules, escalation levels, as-implemented summary | ✅ Current |
| [`LOCATION_CODES.md`](LOCATION_CODES.md) | Canonical Nepal location codes scheme | ✅ Current |

## Extended specs

| Document | Contents | Status |
|---|---|---|
| [`07_officer_management_and_assignment.md`](07_officer_management_and_assignment.md) | Officer accounts, roles, OfficerScope, assignment logic | Current |
| [`08_ticket_resolution_and_case_summary.md`](08_ticket_resolution_and_case_summary.md) | Resolution flow, resolved summary, 4-tier model spec | Current |
| [`09_reports_and_report_builder.md`](09_reports_and_report_builder.md) | Reports: Overview / Pivot / Quarterly email (built); Summary tab §12 (planned) | Current |

## Features

| Document | Contents |
|---|---|
| [`features/projects_catalog_admin_layers_and_settings.md`](features/projects_catalog_admin_layers_and_settings.md) | Projects table, country-agnostic admin layers, settings CRUD |
| [`features/settings/settings_tab_projects_and_seah_contact_centers.md`](features/settings/settings_tab_projects_and_seah_contact_centers.md) | Settings tab: projects + SEAH contact centers |

## Shared service contract

| Document | Contents |
|---|---|
| [`../services/05_messaging_service.md`](../services/05_messaging_service.md) | Canonical messaging API contract used by ticketing and chatbot |

## Platform security

| Document | Contents |
|---|---|
| [`../deployment/13_security.md`](../deployment/13_security.md) | Security features index across chatbot, backend, and ticketing |

## Archive (superseded)

Moved to `archive/`. Kept for historical reference only; do not update.

| Document | Why archived |
|---|---|
| `archive/06_flicket_gap_assessment.md` | Flicket was evaluated and rejected; custom FastAPI built instead |
| `archive/07_gsheet_ticketing_spec.md` | Google Sheets ticketing superseded by full web UI |
| `archive/march_features.md` | Features from March 2026 planning; all either built or folded into main specs |
| `archive/teardown_1.md` | Empty placeholder |

---

## Quick reference

**Create a ticket from chatbot:** `POST /api/v1/tickets` with `X-Ticketing-Secret` header  
**Public QR scan:** `GET /api/v1/scan/{token}` (no auth)  
**Run migrations:** `cd ticketing/migrations && alembic upgrade head`  
**Seed demo data:** `python -m ticketing.seed.kl_road_standard && python -m ticketing.seed.mock_tickets`  
**Local UI:** http://localhost:3001 with `NEXT_PUBLIC_BYPASS_AUTH=true`
