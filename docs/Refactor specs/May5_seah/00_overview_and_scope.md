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
| `agents_instructions.md`                    | Agent split (roles, boundaries, handoffs) and mandatory docs/checklists per agent for execution.                                                                          |

## Execution note

Implement DDL and application wiring in a **dedicated agent / branch** after ticketing geography migrations exist (or in lockstep with an integration worktree). Update this folder if the ticketing physical model diverges from the spec during review.

## Relation to “live grievances” and ticketing

You noted ticketing is **not yet** tightly coupled to **live** grievance/complainant rows — that is the **window** to introduce stable identifiers (`contact_id`, `location_code`, `country_code`) before hard joins multiply migration cost.
