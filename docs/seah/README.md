# SEAH Specifications (permanent)

**Status:** As-built, July 2026. This folder is the durable home for SEAH (Sexual Exploitation, Abuse, and Harassment) intake + privacy specification content, consolidated from sprint folders. Sprint specs remain as history; when they conflict with this folder, **this folder wins**.

## Documents

| Doc | Contents |
|-----|----------|
| [01_seah_intake_flow.md](01_seah_intake_flow.md) | As-built SEAH chatbot intake: entry routes, victim / witness-other / focal-point paths, forms and slot contracts, anonymity semantics, phone-only (no OTP) rule, ask-profile wording, outro variants + support-centre lookup, persistent close controls, no-SMS / no-status-check policy. |
| [02_vault_privacy_and_reveal.md](02_vault_privacy_and_reveal.md) | Canonical storage + privacy model: single grievance/complainant tables, `grievance_parties` person/case-role model, PII vault (`grievance_vault_payloads`), summary-first officer model, reveal workflow + audit schema, SEAH hardening, UI containment, implementation status. |
| [03_seah_decision_log.md](03_seah_decision_log.md) | Condensed decision log: April 2026 stakeholder Q&A, May 2026 phase-2 (canonical/privacy) decisions, two-bucket sensitive-detection policy — one line each with rationale and current status. |

## Related specs (not duplicated here)

- [../deployment/09_privacy.md](../deployment/09_privacy.md) — platform privacy/sensitive-data policy index (vault domains, access policy, LLM summary safety, retention). Doc 02 here is the detailed SEAH-facing model; 09 is the policy baseline.
- [../ticketing_system/12_workflows_configuration.md](../ticketing_system/12_workflows_configuration.md) — workflow slots (`seah` slot, `workflow_type` visibility gate) on the ticketing side.
- [../rest_chatbot/02_flow_spec.md](../rest_chatbot/02_flow_spec.md) — orchestrator flow engine, payload mapping, SEAH state list; `workflow_maps/seah_intake_turn_map.json` for the turn map.
- [../ARCHIVING_AND_RETENTION.md](../ARCHIVING_AND_RETENTION.md) — resolved-case archiving and retention profiles.

## Source material consolidated (sprint history)

- `docs/sprints/archive/Refactor specs/April20_seah/` — 00 (parent policy + 42-question stakeholder log), 01 (route/slots), 04 (OTP), 07 (focal), 08 (outro/catalog). *03 (submission/storage) is obsolete — legacy `complainants_seah`/`grievances_seah` tables and `seah_public_ref` were dropped in phase 2.*
- `docs/sprints/archive/Refactor specs/May5_seah/` — 04 (flow profiles), 05 (vault/summary model), 06 (reveal/audit/UI), 07 (phase-2 decisions), 09 (updated SEAH workflow — supersedes parts of April20 01/07).
- `docs/sprints/archive/Refactor specs/March 5/14_sensible_content_detection_and_flow..md` — two-bucket sensitive detection.
- `docs/sprints/archive/claude-tickets/seah-privacy-worktree-handoff.md` — PII/reveal ownership rules (worktree framing obsolete; single-agent workflow now).

## Key as-built code locations

- Routing / state machine: `backend/orchestrator/state_machine.py`
- Forms: `backend/actions/forms/form_seah_1.py`, `form_seah_2.py`, `form_seah_focal_point.py`, `form_otp.py`, `form_contact.py` (+ `backend/actions/services/contact/required_slots.py`)
- SEAH services: `backend/actions/services/seah/` (`sensitive_detection`, `witness_exit`, `party_payload`, `contact_channels`, `contact_points`, `outro`, `project_identification`)
- Submit + persistence: `backend/actions/action_submit_grievance.py` (`ActionSubmitSeah`), `backend/services/database_services/postgres_services.py` (`submit_seah_to_db`)
- Outro: `backend/actions/action_outro.py` (`ActionSeahOutro`)
- Public DB migrations: `migrations/public/versions/pub003_vault_reveal_audit_foundation.py`, `pub004_phase2_canonical_consolidation.py`, `pub009_seah_service_providers.py`
