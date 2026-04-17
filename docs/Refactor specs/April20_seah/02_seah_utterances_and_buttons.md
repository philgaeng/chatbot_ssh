# 02 - SEAH Utterances and Buttons

## Objective

Implement all SEAH intake copy and button payload mappings in English/Nepali.

This spec is a child of:
- `docs/Refactor specs/April20_seah/00_seah_sensitive_flow_spec.md`

Follow:
- `docs/Refactor specs/AGENT_INSTRUCTIONS.md`

---

## Scope

In scope:
- Add/update utterances for SEAH intro, prompts, consent, confirmation, referral, and branch handling.
- Add/update button mappings for SEAH options and payloads.
- Ensure button payloads align with slot validation logic from `01`.

Out of scope:
- DB-backed localization system changes (decision in `00` is mapping-file based).

---

## Source-of-truth files

- `backend/actions/utils/utterance_mapping_rasa.py`
- `backend/actions/utils/mapping_buttons.py`

---

## Content requirements

- Support `en` and `ne`.
- Use survivor-centered language and avoid investigative prompting.
- Include non-disclosure options (`skipped`, anonymous-style options) where required.
- Include no-SMS-compatible SEAH confirmation copy.
- Include temporary referral copy with clear `REPLACE_ME` markers where pending.

---

## Acceptance criteria

1. All SEAH form/action prompts resolve in both languages.
2. All required button payloads exist and map to valid intents/slot handlers.
3. No missing-key runtime errors in SEAH flow.
4. Copy aligns with decisions in `00`.

---

## Test requirements

- Mapping existence tests for all SEAH utterance keys.
- Mapping existence tests for all SEAH button groups.
- Smoke test across language switch at flow start.

---

## Delivery checklist

- Provide list of new/updated keys in PR.
- Flag every unresolved content dependency as `REPLACE_ME`.
