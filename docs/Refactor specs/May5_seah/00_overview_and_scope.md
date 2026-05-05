# May 5 SEAH / contact refactor — overview and scope

## Purpose

Capture **scoped** decisions for:

1. A **public** (`public.*`) **contact** store that **reduces linkage risk** by keeping channel/address tokens **decoupled** from grievance narrative and from display names where possible.
2. **Alignment** with **ticketing** geography and country tables you are introducing (`ticketing.countries`, `ticketing.locations`, …).
3. A clear handoff so a **dedicated implementation agent** can execute DDL + app changes without contradicting `CLAUDE.md` or `docs/MIGRATIONS_POLICY.md`.

This folder does **not** replace execution: it is the **spec** source of truth for that work.

## Non-goals (for this tranche)

- Rewriting the full SEAH conversation UX (utterances, focal flows) — see `April20_seah/*` for product behaviour.
- Merging **auth credentials** into the same physical row as **complainant PII** — credentials stay on the user/auth side; **contact profile** may link via FK only.

## Migration ownership (LOCKED)

| Change                                                                                  | Stream                                                          |
| --------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| `ticketing.countries`, `ticketing.location_*`, …                                        | **Ticketing Alembic** only — `ticketing/migrations/alembic.ini` |
| `public.contact_info`, party bridges, evolution of `complainants` / `complainants_seah` | **Public Alembic** — `migrations/public/alembic.ini`            |

Never put `public.*` DDL in ticketing migrations, or `ticketing.*` in public migrations. See `docs/MIGRATIONS_POLICY.md`.

## Documents in this folder

| File                                        | Contents                                                                                                                                                                  |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `01_ticketing_geography_reference_model.md` | Canonical ticketing tables for country + hierarchical locations + translations (your design).                                                                             |
| `02_public_contact_info_and_party_links.md` | `contact_info`, links from `complainants`, `complainants_seah`, `users`, `resource_persons`; risk posture; FK to `country_code` / optional `location_code`.               |
| `03_submission_mapping_and_fallback.md`     | Submit-time contract for `action_submit_grievance.py` / `action_submit_seah`: map codes first, always persist level free text, never block submission on missing mapping. |
| `04_action_ask_commons_flow_profiles.md`    | Flow-aware ask prompt profiles for `grievance` / `seah-victim` / `seah-other` / `seah-focal` with explicit open questions.                                                |
| `05_vault_and_summary_operating_model.md`   | Vault-first storage model for original grievance content + metadata events + validated summary pipeline for officer-facing workflows.                                        |
| `06_vault_reveal_audit_and_ui_controls.md`  | Controlled reveal contract (reason codes, TTL tokens), immutable audit schema, UI containment controls, and SEAH-specific hardening rules.                                 |
| `07_phase2_decision_questions.md`           | Phase-2 decision questionnaire used to lock canonical IDs, party-role rules, cutover behavior, reveal policy inputs, and migration policy.                                  |
| `08_phase2_query_and_submit_amendments.md`  | Exhaustive checklist of submit-path and SQL query amendments required in `action_submit_grievance.py` and DB service managers for canonical phase-2 rollout.                |
| `agents_instructions.md`                    | Agent split (roles, boundaries, handoffs) and mandatory docs/checklists per agent for execution.                                                                          |

Related implementation handoff:

- `docs/claude-tickets/seah-privacy-worktree-handoff.md` — worktree ownership split, cross-worktree API contracts, delivery sequence, and acceptance criteria for Claude-led ticketing implementation.
- `docs/claude-tickets/phase2-public-canonical-implementation-handoff.md` — function-level backend implementation sequence for canonical public submit/query paths (phase 2).

## Execution note

Implement DDL and application wiring in a **dedicated agent / branch** after ticketing geography migrations exist (or in lockstep with an integration worktree). Update this folder if the ticketing physical model diverges from the spec during review.

## Relation to “live grievances” and ticketing

You noted ticketing is **not yet** tightly coupled to **live** grievance/complainant rows — that is the **window** to introduce stable identifiers (`contact_id`, `location_code`, `country_code`) before hard joins multiply migration cost.
