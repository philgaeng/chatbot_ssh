# Sprint summary — April–June 2026: GRM ticketing build ("claude-tickets")

> Original working docs: [`archive/claude-tickets/`](archive/claude-tickets/) · Status: **Delivered** (demo May 10, then hardened through June)

## Goal

Build the full GRM ticketing system (backend + officer portal) alongside the chatbot: `ticketing.*` schema, workflow engine, SLA escalation, officer UI, admin settings, reports, and chatbot integration — initially for the May 10 demo, then production-hardened.

## Delivered

- **Backend**: `ticketing.*` schema + SQLAlchemy models (~33 tables), Alembic stream (38 revisions), CRUD API grown to 14 routers, workflow engine, SLA watchdog + escalation Celery tasks (`grm_ticketing` app), grievance sync (every 2 min), seed data for both demo scenarios.
- **Settings admin panel**: workflows (templates, steps, slots), users/roles/scopes, organizations, locations (841 Nepal locations, multilingual), projects, packages, project types, go-live checklist.
- **Chatbot → ticketing integration**: `ticketing_dispatch.py` webhook on all submit paths + `grievance_sync` polling fallback (Option A).
- **Tier model (spec 12)**: Actor/Supervisor/Informed/Observer permission tiers + per-workflow notification rules.
- **Auth**: demo bypass roster → full **Keycloak** migration (invite flow, SMTP, onboarding webhook, login themes) — replacing the originally planned Cognito.
- **LLM**: note translation, AI case findings, context builder; PII vault + reveal flow with audit.
- **Reports**: Overview / Pivot builder / export-all XLSX / quarterly email library / overdue episodes / Summary tab.
- **QR tokens**: package-scoped scan URLs + chatbot prefill.
- **UI**: officer portal (Next.js 16) — queue, ticket thread (4-context bubble system), tasks, viewers, settings, reports, mobile app under `/m`, public closure pages.

## Where the durable content lives now

| Content | Permanent home |
|---|---|
| Product/architecture specs | `docs/ticketing_system/00–17` |
| UI spec + design system | `docs/ticketing_system/ui/` |
| Keycloak auth ops | `docs/deployment/16_auth_keycloak.md` |
| Docker runbook | `docs/deployment/DOCKER.md` |
| Vault/PII + reveal model | `docs/seah/02_vault_privacy_and_reveal.md`, `docs/deployment/09_privacy.md` |
| Build/status logs | `docs/PROGRESS.md`, `docs/TODO.md` |

## Leftovers noted at close

- TP-02 officer-side voice transcription (P2) — open.
- Report-share SMS dispatch (TP-05) — wired as integration point only.
- Legacy `workflow_assignments` path retained alongside `project_workflows` slots.
