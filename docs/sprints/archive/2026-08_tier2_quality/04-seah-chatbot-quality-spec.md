# H2-08 — SEAH form mixin + Nepali copy repair

> Workstream D · Branch `tier2/h2-08-seah` · Independent.
> Paths under `backend/actions/`. Evidence: conversation-layer review in [`docs/reviews/devils_advocate_codebase.md`](../../reviews/devils_advocate_codebase.md). Re-locate line numbers before editing.
> ⚠️ **Live SEAH intake code.** The existing SEAH orchestrator tests are the safety net; run them constantly. No state-machine changes (that's Tier-3).

## Problems (verified)

**Duplication — the two SEAH forms are copy-paste siblings:**
- `extract_/validate_seah_project_identification` **byte-identical** in `backend/actions/forms/form_seah_2.py:37-64` vs `form_seah_focal_point.py:242-269` — including identical commented-out dead code in the ask actions (`form_seah_2.py:158-163` vs `form_seah_focal_point.py:550-555`).
- `sensitive_issues_new_detail` extract/validate near-identical (`form_seah_2.py:66-125` vs `form_seah_focal_point.py:271-335`; only delta: skip-allowed + `len>3` vs no-skip + `len>=8`).
- `_build_multiselect_buttons` copy-pasted **5×** inside `ValidateFormSeahFocalPoint2` ask actions (`form_seah_focal_point.py:564-577, 583-596, …`).
- Utterance blocks duplicated wholesale: `utterance_mapping_rasa.py:1440-1460` (`form_seah_2`) vs `:1507-1527` (`form_seah_focal_point`) — same EN, separately-maintained NE **already drifted**.

**Nepali copy defects (user-facing, SEAH-critical):**
- `utterance_mapping_rasa.py:90` — SEAH main-menu button NE label repeats "असुरक्षित व्यवहार" three times instead of translating "sexual exploitation, abuse, and harassment".
- `:25-28` — NE OCMC referral text does not correspond to the EN at all.
- `:34-35` — garbled hospital address ("हस्तान्याउन हस्तान्याउन").
- `:44, :48` — stray "ू" typo prefixes.
- English-only messages bypassing the utterance system: `backend/actions/services/contact/phone.py:40` ("You entered a PH number…"), `backend/actions/services/contact/validators.py:223` ("Please enter your correct village and address").

## Change

### 1. Shared SEAH slot mixin

1. New `backend/actions/forms/seah_shared.py`: mixin (or plain helper module — match the codebase's existing mixin style in `base_classes/base_mixins.py`) providing the shared slot logic, **parameterized** where the forms genuinely differ:
   - `seah_project_identification` extract/validate (identical → shared verbatim).
   - `sensitive_issues_new_detail` extract/validate with params `(skip_allowed: bool, min_length: int)` — `form_seah_2` uses `(True, 4)`-equivalent, focal uses `(False, 8)`-equivalent. **Preserve current thresholds exactly** (`len>3` vs `len>=8` — note the operator difference; encode faithfully, don't "clean up").
   - One `_build_multiselect_buttons` helper replacing the 5 copies.
2. Both form classes consume the mixin; delete the duplicated bodies and the commented-out dead blocks (both copies).
3. **Merge the duplicated utterance blocks**: single shared section keyed so `get_utterance_base`'s file/function lookup still resolves (constraint: keys derive from `file_name` + function name via stack introspection — `base_classes.py:118-127`. Verify how the mapping keys resolve for mixin-hosted methods **before** moving; if the introspected key changes, add explicit alias entries rather than renaming keys — replacing the lookup mechanism is Tier-3, out of scope).
4. Where the NE variants had drifted, adopt the better translation for both (flag which in the translation sheet, §2).

### 2. Nepali copy repair (agent prepares, human signs off)

1. **Mechanical fixes now** (unambiguous defects): the ":44/:48" stray-"ू" typos, the tripled phrase at `:90` (replace with the correct full NE rendering of "sexual exploitation, abuse and harassment" — source it from the ADB-reviewed copy in `docs/sprints/archive/Refactor specs/May5_seah/09_updated_seah_workflow.md` if present; otherwise mark for translator).
2. **Translation sheet**: generate `docs/seah/translations_seah_review.csv` — every SEAH-flow utterance/button (grep the `utterance_mapping_rasa.py` SEAH sections + `BUTTONS_SEAH_*` constants): columns `key, en, ne_current, ne_proposed, status(ok|fixed|needs_translator), note`. Mark `:25-28` (OCMC mismatch) and `:34-35` (garbled address) `needs_translator` with the factual issue described — support-centre addresses must be verified against the seeded `seah_service_providers` data (pub009), not guessed.
3. **Route the two English-only validator messages** through the utterance system (`phone.py:40`, `validators.py:223`): add EN/NE entries; NE marked `needs_translator` in the sheet if no reviewed translation exists.
4. Human sign-off on the sheet is a **sprint DoD item** — record reviewer + date in PROGRESS. Agent must not invent Nepali for `needs_translator` rows.

## Tests (acceptance)

- [ ] Existing SEAH suites green unchanged: `tests/orchestrator/test_seah_*` (anonymous OTP hop, focal ask buttons, seah2 contact channels) + `tests/actions/` + full `tests/orchestrator/`.
- [ ] New `tests/actions/test_seah_shared_parity.py`:
  - For each shared slot: `form_seah_2` and `form_seah_focal_point` produce **identical** extract/validate results on the same inputs where behavior is shared, and the parameterized deltas hold (skip accepted only on victim form; length thresholds `>3` vs `>=8` at the boundaries: 3,4 chars and 7,8 chars).
  - Multiselect ask actions emit identical button payload structures via the shared helper.
- [ ] New utterance-integrity test (cheap, prevents the drift class): every SEAH utterance key referenced by the forms resolves in `utterance_mapping_rasa.py` for both `en` and `ne`, and no NE value equals its EN value (placeholder detector) except keys whitelisted in the test with a comment.
- [ ] Translation sheet generated and committed; `needs_translator` count reported in PROGRESS.

## Manual verification (record in PROGRESS)

- [ ] Full SEAH walk-through in the webchat (local stack), EN and NE: victim identified, victim anonymous, witness exit (support centres render), focal path — copy renders correctly, buttons work, submission succeeds, outro variants correct.
- [ ] The `:90` menu button and outro referral text visually checked in NE.
