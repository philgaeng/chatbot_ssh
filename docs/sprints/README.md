# Sprints — summaries and archive

**Audience:** internal — excluded from the public repository (lifecycle §10.4).

## Standing rule — log every deferral (no silent debt)

Whenever a sprint **defers** work rather than doing it — downgrading a lint rule to `warn`, suppressing/`# noqa`-ing a warning, scoping a finding out of a ticket, quarantining a test (`-m "not integration"`), or leaving a `TODO`/`INTEGRATION POINT` — it **must** be recorded in two places, in the same commit that creates the deferral:

1. A tracked follow-up doc under the sprint: `sprints/<sprint>/followups/<slug>.md` (measured inventory + definition of done + endgame). Exemplar: [`2026-07_hardening/followups/portal-lint-cleanup.md`](2026-07_hardening/followups/portal-lint-cleanup.md).
2. A one-line pointer row in [`../TODO.md`](../TODO.md) under **🔵 TECH DEBT**, linking that follow-up.

A downgrade/suppression/scope-cut that is **not** logged this way is treated as a defect, not a deferral — the whole point is that debt stays visible. These follow-ups accumulate into the TECH DEBT backlog so that, once the main Tier-2/Tier-3 refactors have landed, a dedicated **clean-up sprint** can be launched against a complete, measured list rather than rediscovered by grep.

## Active & queued sprints

| Sprint | Status | Folder | Focus |
|---|---|---|---|
| **July 2026 — Tier-1 Hardening** | Residual | [`2026-07_hardening/`](2026-07_hardening/) | HR-01…07 all shipped; folder stays open for the pending-human items (HR-07 browser sweep, HR-05 live-failure/branch-protection checks). Tracker: [`PROGRESS.md`](2026-07_hardening/PROGRESS.md) |
| **August 2026 — DPG compliance & LLM independence** | **🟡 In progress — Sprint 0 ✅ (2026-08-18)** | [`2026-08-llm/`](2026-08-llm/) | DPG-01…46 (27 tickets) across four sub-sprints: licensing/governance → LLM-agnostic clients (**two** LLM surfaces, **one** config file) → open-model benchmarks + CI evidence → Nepali PII redaction. ⚠ **T2 self-hosting is parked** (no run-cost owner), so production runs a hosted open-weights provider and the PII sprint is the only control on a permanent third-party egress. Start at [`README.md`](2026-08-llm/README.md); tracker [`PROGRESS.md`](2026-08-llm/PROGRESS.md), tests [`TESTS.md`](2026-08-llm/TESTS.md), **decisions** [`DECISIONS.md`](2026-08-llm/DECISIONS.md) (18 taken, answers verbatim) and **still-live questions** [`QUESTIONS.md`](2026-08-llm/QUESTIONS.md) (Q-02 licence choice, Q-19 LLM budget, Q-01 IP determination in flight) |
| **September 2026 — QA & build pipeline** | 📋 **Proposed — not approved** | [`2026-09_qa_automation/`](2026-09_qa_automation/) | QA-01…05: CI-built images (the 2026-09-04 deploy-OOM incident's own logged fix), stack isolation, and a Playwright harness that can *look* at the officer UI — its first end-to-end coverage (22 routes, zero today). Optionally retires HR-07's never-run manual sweep, on the **webchat** surface. Two parallel agent streams, **both ready to start** — all 15 questions answered 2026-09-04 and folded into the ticket specs ([`QUESTIONS.md`](2026-09_qa_automation/QUESTIONS.md) keeps the reasoning). Start at [`README.md`](2026-09_qa_automation/README.md) |
| **September 2026 — Review feedback loop** | 📋 **Proposed — not approved** | [`2026-09_review_feedback_loop/`](2026-09_review_feedback_loop/) | In-context feedback widget on staging (comment + annotated screenshot → GitHub issue) and a triage agent that reads it. Precondition **decided**: staging holds synthetic data only, enforced by an `ops` check. Its "agent applies the fix" phase is blocked on the QA sprint. Design: [`DESIGN-review-feedback-loop.md`](2026-09_review_feedback_loop/DESIGN-review-feedback-loop.md) |

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
| August 2026 | [`2026-08_tier2_quality.md`](2026-08_tier2_quality.md) | Tier-2 quality/perf: OIDC refresh, `tickets.py` split + engine, sync watermark, auth cache, shared thread hook, SEAH mixin + Nepali repair (+ authz-gaps & apifetch follow-ups) |
| August 2026 | [`2026-08_tier3_structural.md`](2026-08_tier3_structural.md) | Tier-3 structural: explicit utterance keys (**two live bugs — an HTTP 500 on SEAH intake**), `run_flow_turn` −21% + dead-air fix, voice-chunk serialization (**+ the webchat's first test suite**), PII boundary unified in `backend/`, settings `page.tsx` 4,372→301, grievance-API authn/audit/contract, boundary rules amended to as-built + pinned, and the `@integration` quarantine ended (**CI 364→897 tests**). **~76% → ~81%**; 2 of 5 dimension targets missed and stated as such |

## Archive map

| Archive folder | Original location |
|---|---|
| `archive/Refactor specs/March 5/` | March 2026 refactor specs |
| `archive/Refactor specs/April20_seah/` | April SEAH intake specs |
| `archive/Refactor specs/May5_seah/` | May SEAH canonical/privacy specs |
| `archive/claude-tickets/` | Ticketing build working docs, UI handoffs, session notes |
| `archive/June5/` | June5 sprint specs + agent prompts |
| `archive/deployment refactor/` | Deployment refactor notes |
| `archive/2026-08_tier2_quality/` | Tier-2 sprint specs, tracker (`PROGRESS.md`), agent prompts, `followups/` |
| `archive/2026-08_tier3_structural/` | Tier-3 sprint: **[`00-reassessment.md`](archive/2026-08_tier3_structural/00-reassessment.md)** (why 4 of the review's 5 Tier-3 rows were wrong, and the §6 boundary DECISION), 6 specs, tracker (`PROGRESS.md`, **58 deviations**), `followups/` |

Operational logs that used to live in `claude-tickets/` moved to the docs root: [`../PROGRESS.md`](../PROGRESS.md), [`../TODO.md`](../TODO.md); the Docker runbook is now [`../deployment/DOCKER.md`](../deployment/DOCKER.md) and the Keycloak auth guide [`../deployment/16_auth_keycloak.md`](../deployment/16_auth_keycloak.md).
