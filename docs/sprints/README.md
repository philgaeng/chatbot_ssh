# Sprints — summaries and archive

## Active & queued sprints

| Sprint | Status | Folder | Focus |
|---|---|---|---|
| **July 2026 — Tier-1 Hardening** | Active | [`2026-07_hardening/`](2026-07_hardening/) | HR-01…07: fail-closed auth, ticket-access gates, unique ticket index, escalation locking, CI, portal + webchat robustness. Tracker: [`PROGRESS.md`](2026-07_hardening/PROGRESS.md) |
| **Aug 2026 — Tier-2 Quality & Performance** | Queued (after Tier-1) | [`2026-08_tier2_quality/`](2026-08_tier2_quality/) | H2-01…08: OIDC refresh, tickets.py split + engine extraction, authz/escalation test extensions, sync watermark, auth-dependency cache, shared thread hook, SEAH mixin + Nepali repair. Tracker: [`PROGRESS.md`](2026-08_tier2_quality/PROGRESS.md) |

## Completed sprints

One summary document per sprint, in chronological order. Full original sprint specs, agent prompts, and progress trackers are preserved under [`archive/`](archive/) — **read-only, historical**; durable specification content has been extracted into the permanent spec tree (see each summary's "Where the durable content lives now" table).

| Sprint | Summary | Focus |
|---|---|---|
| March 2026 | [`2026-03_chatbot_refactor.md`](2026-03_chatbot_refactor.md) | Rasa runtime → FastAPI orchestrator, Flask → FastAPI, REST webchat |
| April 2026 | [`2026-04_seah_intake.md`](2026-04_seah_intake.md) | Dedicated SEAH intake flow (victim + focal paths) |
| April–June 2026 | [`2026-04_grm_ticketing_build.md`](2026-04_grm_ticketing_build.md) | GRM ticketing backend + officer portal ("claude-tickets") |
| April 2026 | [`2026-04_deployment_refactor.md`](2026-04_deployment_refactor.md) | Single-host Docker deployment architecture, secrets policy |
| May 2026 | [`2026-05_seah_canonical_privacy.md`](2026-05_seah_canonical_privacy.md) | Canonical SEAH data model, PII vault, geography reference |
| June 2026 | [`2026-06_voice_and_ux.md`](2026-06_voice_and_ux.md) | Voice notes, chatbot/portal UX round, roles & permissions matrix |

## Archive map

| Archive folder | Original location |
|---|---|
| `archive/Refactor specs/March 5/` | March 2026 refactor specs |
| `archive/Refactor specs/April20_seah/` | April SEAH intake specs |
| `archive/Refactor specs/May5_seah/` | May SEAH canonical/privacy specs |
| `archive/claude-tickets/` | Ticketing build working docs, UI handoffs, session notes |
| `archive/June5/` | June5 sprint specs + agent prompts |
| `archive/deployment refactor/` | Deployment refactor notes |

Operational logs that used to live in `claude-tickets/` moved to the docs root: [`../PROGRESS.md`](../PROGRESS.md), [`../TODO.md`](../TODO.md); the Docker runbook is now [`../deployment/DOCKER.md`](../deployment/DOCKER.md) and the Keycloak auth guide [`../deployment/16_auth_keycloak.md`](../deployment/16_auth_keycloak.md).
