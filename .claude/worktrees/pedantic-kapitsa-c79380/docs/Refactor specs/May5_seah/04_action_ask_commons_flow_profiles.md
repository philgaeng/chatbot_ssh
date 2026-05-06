# `action_ask_commons` flow profiles (`grievance` / `seah-victim` / `seah-other` / `seah-focal`)

## Scope

Define how reusable ask actions in `backend/actions/action_ask_commons.py` should change prompts/buttons
based on the current intake flow profile, while keeping one validation source of truth in form logic.

This spec is about **ask-layer wording/routing hints**, not DB schema.

## Why

Today `action_ask_commons` prompts are mostly generic, causing ambiguity in SEAH focal/other paths
(who is being asked about: reporter vs affected person). We need explicit, inspectable profiles.

## Proposed profile key (LOCKED for this spec)

Use an explicit profile value at ask-time:

- `grievance`
- `seah-victim`
- `seah-other`
- `seah-focal`

Preferred implementation:

- Derive from existing slots (`story_main`, `seah_victim_survivor_role`, `seah_focal_stage`) in one helper
  OR store a dedicated slot (e.g. `ask_contact_profile`) set by state machine before contact asks.

No numeric profile IDs.

## Initial mapping logic (proposed)

- `grievance`: `story_main in ('new_grievance', 'grievance_submission')`
- `seah-victim`: `story_main == 'seah_intake'` and `seah_victim_survivor_role == 'victim_survivor'`
- `seah-other`: `story_main == 'seah_intake'` and `seah_victim_survivor_role == 'not_victim_survivor'`
- `seah-focal`: `story_main == 'seah_intake'` and `seah_victim_survivor_role == 'focal_point'`

For focal path, wording may further vary by `seah_focal_stage` (reporter bootstrap vs complainant capture).

## Actions in scope

These should support profile-aware prompt selection:

- `action_ask_complainant_phone`
- `action_ask_complainant_location_consent`
- `action_ask_complainant_consent`
- `action_ask_complainant_full_name`
- `action_ask_complainant_email_temp`
- (optional) location asks where “your grievance” wording may be misleading

Validation methods in form classes remain unchanged (single source of truth).

## Prompt behavior goals by profile

### `grievance`

- Keep current baseline wording.

### `seah-victim`

- Keep direct first-person wording ("your contact", "your location") unless policy requires anonymity variants.

### `seah-other`

- Clarify reporter vs affected person context where needed.
- Avoid forcing the reporter to feel they are declaring victim identity.

### `seah-focal`

- During reporter bootstrap: prompts should clearly indicate reporter/focal person details.
- During complainant capture stage: prompts should clearly indicate affected person details.

## Buttons

- Reuse existing button constants where possible.
- Profile differences should primarily affect text, not payload contracts, unless state machine requires new intents.

## Mapping/utterance structure

Move away from opaque numeric-only semantics in this area by introducing profile-aware keys in mapping data, e.g.:

- `default.primary`
- `seah_focal.reporter_primary`
- `seah_focal.complainant_primary`

Backward compatibility path:

- Keep existing numeric keys as fallback while migrating.

## Implementation notes (non-normative)

- Add helper in `action_ask_commons.py`:
  - `_get_ask_profile(tracker) -> str`
  - optional `_get_focal_prompt_phase(tracker) -> str` (`reporter`, `complainant`)
- Use helper result to choose utterance key, fallback to current generic key.
- Do not duplicate field validation logic in ask actions.

## Tests

Minimum coverage:

1. `grievance` profile still emits current baseline prompt/button behavior.
2. `seah-victim` emits SEAH-specific victim wording where configured.
3. `seah-other` emits non-victim wording.
4. `seah-focal` emits reporter wording in bootstrap stage.
5. `seah-focal` emits complainant wording in complainant stage.
6. Fallback behavior when profile cannot be derived (defaults to `grievance`/generic).

## Resolved decisions

1. **`seah-other` wording target**
   - Contact details collected in `seah-other` are for the **reporting person** (other), not the victim.
   - Prompts should explicitly clarify this where ambiguity is likely.

2. **Focal bootstrap contact consent**
   - Keep focal bootstrap consent behavior as-is for now (no separate flow split required in this tranche).
   - Wording can still be profile-adjusted for clarity.

3. **Email in focal stages**
   - Collect email only for the **affected person** in complainant stage.
   - Do not collect reporter email in focal bootstrap stage.

4. **Location consent wording**
   - In `seah-focal` complainant stage, location consent prompt must explicitly refer to the **affected person’s grievance location**.

5. **Slot/profile strategy**
   - Use derived profile helper (recommended path) rather than introducing a new explicit `ask_contact_profile` slot in this tranche.

6. **Migration pace**
   - Execute full profile rollout for in-scope ask actions in **one PR** (not a staged partial rollout).
