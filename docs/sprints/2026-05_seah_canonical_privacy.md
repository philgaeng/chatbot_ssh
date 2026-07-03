# Sprint summary — May 2026: SEAH canonical data model, privacy & geography

> Original specs: [`archive/Refactor specs/May5_seah/`](<archive/Refactor specs/May5_seah/>) · Status: **Delivered**

## Goal

Replace the April SEAH bolt-on storage with a canonical data model, lock the privacy (vault) architecture, and align geography/reference data between chatbot and ticketing.

## Delivered

- **Geography reference model**: `ticketing.countries` / `location_level_defs` / `locations` / `location_translations` (migration `f1a3e9c72b05`) with chatbot alignment rules.
- **`public.contact_info`** + party/role link tables + `resource_persons` design; linkage-risk posture.
- **Submit-time location mapping contract**: free text first, map to codes when possible, never block submission.
- **Ask-layer flow profiles**: `grievance` / `seah-victim` / `seah-other` / `seah-focal` with per-profile wording rules.
- **Vault-first operating model (LOCKED)**: PII vault (public schema) / non-PII metadata (ticketing) / validated derived summaries; `grievance_parties` person/case-role table; minimum event format; LLM summary contracts with leakage blockers.
- **Reveal + audit spec (LOCKED)**: reason codes, TTL tokens, watermarking, immutable audit, SEAH hardening and alert thresholds.
- **Phase-2 decisions locked**: `grievance_id` is the only canonical reference, legacy SEAH tables and `seah_public_ref` dropped, vault is the narrative source of truth, exactly-one primary reporter per case (nullable complainant for anonymous).
- **Spec 12 — notification & admin model (LOCKED, implemented)**: 4-tier permissions (Actor/Supervisor/Informed/Observer), per-workflow `notification_rules` JSON, country/project admin split (later refined by June RP-01…11).
- **SEAH flow copy v2** from stakeholder comments: focal-flow field removals, persistent close controls in the composer.

## Where the durable content lives now

| Content | Permanent home |
|---|---|
| Vault/privacy/reveal model | `docs/seah/02_vault_privacy_and_reveal.md`, `docs/deployment/09_privacy.md` |
| Phase-2 canonical decisions | `docs/seah/03_seah_decision_log.md` |
| SEAH flow (incl. copy v2) | `docs/seah/01_seah_intake_flow.md` |
| Geography model + mapping rule | `docs/ticketing_system/18_geography_and_locations.md` |
| Tier model + notification rules | `docs/ticketing_system/11_roles_and_permissions.md`, `12_workflows_configuration.md` |

## Leftovers noted at close

- Support-service referral list was a placeholder (filled later — real SEAH support centres seeded in June).
