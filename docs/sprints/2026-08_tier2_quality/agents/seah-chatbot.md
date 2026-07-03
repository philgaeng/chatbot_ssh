# Agent runbook — H2-08: SEAH form mixin + Nepali copy repair

**Branch:** `tier2/h2-08-seah` off `integration/seah-claude` · **Spec:** [`../04-seah-chatbot-quality-spec.md`](../04-seah-chatbot-quality-spec.md) · Read [`README.md`](README.md) first.

⚠️ **Live SEAH intake code — the most sensitive flow in the product.** Run the SEAH test suites after every commit. You prepare the Nepali fixes; a human translator signs off before merge. **Never invent Nepali text for `needs_translator` rows.**

## Mission

Deduplicate the copy-pasted SEAH form logic into one parameterized mixin (~150 lines deleted, single-site policy changes), and repair the Nepali copy defects — mechanical ones now, translator-dependent ones via a review sheet.

## Steps

1. **Understand the lookup constraint first**: read `backend/actions/base_classes/base_classes.py` (~118-127) — utterance keys are derived from the calling function's name and file via `inspect.currentframe()`. Prototype: put one shared method in a mixin, call it from both forms, and check which key `get_utterance_base` resolves. This determines whether the merged utterance blocks need alias entries. **Do this before any bulk move**; document the finding in PROGRESS.
2. Read both forms fully: `backend/actions/forms/form_seah_2.py`, `form_seah_focal_point.py`, plus the SEAH sections of `backend/actions/utils/utterance_mapping_rasa.py` and `mapping_buttons.py` (`BUTTONS_SEAH_*`).
3. **Mixin extraction** per spec §1: `seah_shared.py` with the shared verbatim logic and the `(skip_allowed, min_length)` parameterization — preserve `len>3` vs `len>=8` exactly, including the operator asymmetry. Dedupe `_build_multiselect_buttons` (5 copies). Delete the commented-out dead blocks in both files.
4. **Utterance merge** per your step-1 finding (shared section or aliases). Where EN matched but NE drifted, choose the better NE, flag the choice in the sheet.
5. **Write the parity tests before finishing the move** (`tests/actions/test_seah_shared_parity.py` per spec) — they are your refactor safety net alongside the existing suites (`tests/orchestrator/test_seah_*`).
6. **Nepali repair** per spec §2: mechanical fixes (`:44/:48` typos, `:90` tripled phrase — source correct copy from `docs/sprints/archive/Refactor specs/May5_seah/09_updated_seah_workflow.md` if it has ADB-reviewed NE; else mark for translator). Generate `docs/seah/translations_seah_review.csv` covering every SEAH utterance/button. Verify support-centre addresses against seeded `seah_service_providers` data (migration pub009 / `backend/shared_functions/seah_service_providers.py`) — factual data, not translation.
7. Route the two English-only validator messages (`services/contact/phone.py:40`, `services/contact/validators.py:223`) through the utterance system.
8. Add the utterance-integrity test (all referenced SEAH keys resolve for en+ne; NE≠EN placeholder detector with whitelisted exceptions).
9. **Manual walk-through** per spec (all four SEAH paths, EN + NE) on the local stack. Record in `../PROGRESS.md`.
10. Hand off: PROGRESS gets the `needs_translator` count and the sheet path; the sprint owner arranges translator sign-off (merge blocks on it).

## Constraints

- No state-machine (`state_machine.py`) or form-loop changes — Tier-3.
- No renaming of slots, forms, actions, or utterance keys (aliases only, per step 1).
- Do not touch non-SEAH forms even where the same duplication pattern exists — log it as a deviation instead.

## Done means

Checklist ticked in `../PROGRESS.md`; parity + integrity + existing SEAH suites green in CI; translation sheet committed with `needs_translator` count; manual EN/NE walk-through recorded; translator sign-off field populated (or explicitly pending, blocking merge).
