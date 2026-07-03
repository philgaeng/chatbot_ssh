# Sprint summary — April 2026: Dedicated SEAH intake

> Original specs: [`archive/Refactor specs/April20_seah/`](<archive/Refactor specs/April20_seah/>) · Status: **Delivered**, storage model later superseded by the May 2026 canonical model

## Goal

Build a dedicated, survivor-centered SEAH intake route in the chatbot, segregated from the standard grievance flow, with focal-point (staff) reporting support.

## Delivered

- Dedicated `seah_intake` route with `form_seah_1` / `form_seah_2` victim path (identified and anonymous variants).
- Focal-point branch with `seah_focal_stage` staging across shared forms plus a focal assessment form.
- Phone-only rule (no OTP verification) for sensitive SEAH intake in `ValidateFormOtp` — rationale: borrowed/shared phones.
- Dedicated submission path with SEAH case IDs and **no complainant recap SMS**.
- SEAH utterance/button inventory (EN/NE) in `utterance_mapping`.
- Rollout behind `ENABLE_SEAH_DEDICATED_FLOW` on branch `feat/seah-sensitive-intake`.
- Design for outro variants O1–O5, `seah_contact_points` referral table, and project catalog decisions.
- 42-question stakeholder decision log (survivor-centered policy: mandatory-but-skippable fields, no status-check/modify for SEAH, storage segregation).

## Superseded

- `03_seah_submission_and_storage.md` and the legacy `complainants_seah`/`grievances_seah` tables + `seah_public_ref` were **replaced in May 2026** by the canonical model (`public.grievances` + `grievance_parties` + PII vault, `grievance_id` as the only reference). Do not use the April storage spec.

## Where the durable content lives now

| Content | Permanent home |
|---|---|
| SEAH intake flow (routes, slots, anonymity, outro, no-OTP rule) | `docs/seah/01_seah_intake_flow.md` |
| Stakeholder decision log | `docs/seah/03_seah_decision_log.md` |
| Storage/privacy model (current) | `docs/seah/02_vault_privacy_and_reveal.md` |

## Leftovers noted at close

- Focal roster + OTP verification for focal points (`unverified_focal_point`) — never implemented.
- Final ADB referral copy (`REPLACE_ME` placeholders) — resolved later via the May/June copy updates and real support-centre data (see `git log`: "SEAH witness exit: show real support centres").
