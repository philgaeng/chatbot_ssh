# Sprint summary — April 2026: Deployment refactor

> Original docs: [`archive/deployment refactor/`](<archive/deployment refactor/>) · Status: **Phase 1 delivered** (documentation-led)

## Goal

Define the deployment and data architecture for going beyond local dev: single-host all-Docker Phase 1, with a Phase 2 path to S3 and managed Postgres.

## Delivered

- Phase 1 architecture: single EC2 host, everything in Docker Compose (chatbot stack + GRM overlay), nginx as the only edge.
- Secrets policy: `env.local` for dev, AWS Parameter Store/Secrets Manager direction for prod; never commit secrets.
- Backup mandate (later realized as `scripts/ops/backup_db.sh` + restore drill + ops container monitoring).
- Agent guardrails that became standing constraints: no Rasa server in prod, two-service topology (orchestrator + backend), nginx-only edge, correct uvicorn/celery module names.

## Realized beyond the sprint

Production now runs on DOR government infrastructure (`grm-chatbot.dor.gov.np`, TLS + `grm-auth` subdomain for Keycloak), deployed via Makefile targets — see `docs/deployment/`.

## Where the durable content lives now

| Content | Permanent home |
|---|---|
| Architecture + service map | `docs/deployment/01_architecture.md` |
| Setup/operations runbooks | `docs/deployment/02_setup.md`, `03_operations.md` |
| Secrets & key lifecycle | `docs/deployment/14_key_and_secret_lifecycle.md` |
| Host hardening | `docs/deployment/15_host_hardening.md` |
| Environment URLs | `docs/deployment/12_environment_urls.md` |

## Leftovers noted at close

- Phase 2 (S3 for uploads, managed Postgres) — not started; open questions in the original doc were never formally resolved.
