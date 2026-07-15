# Follow-up — utterance `file_name` derived from module name (~200 sites)

> **Status:** 🔴 **OPEN — deferred out of T3-01 (2026-07-15).** · **Owner:** chatbot / actions · **Priority:** medium (no known live breakage; it is a *latent* refactor trap — the failure mode is silent and only fires when someone moves a class)
> **Origin:** Tier-3 reassessment ([`../00-reassessment.md`](../00-reassessment.md) §4). Surfaced while scoping T3-01. **This is the finding the review's "Replace stack-introspection utterance lookup with explicit keys — makes the chatbot refactorable" item was *actually* aiming at** — but the review conflated it with the 4-site introspection bug, which is what T3-01 fixes.

## The finding

Utterance lookup is `UTTERANCE_MAPPING[file_name][action_name]['utterances'][index][lang]` (`backend/actions/utils/utterance_mapping_rasa.py:2297-2313`). There are **two implicit axes**, not one:

| Axis | Derivation | Sites | Handled by |
|---|---|---|---|
| `action_name` | `inspect.currentframe().f_back.f_code.co_name` (`base_classes.py:118`) | **4** | ✅ **T3-01** |
| `action_name` | `self.name()` — already explicit (`base_mixins.py:303`) | 196 | already fine |
| **`file_name`** | **`self.__class__.__module__.split(".")[-1]`** (`base_mixins.py:63`) | **~200 — all of them** | ❌ **this follow-up** |

```python
# backend/actions/base_classes/base_mixins.py:63
self.file_name = self.__class__.__module__.split(".")[-1]
```

**Every** utterance lookup in the codebase — both implementations — keys on a module name derived at runtime from where the class happens to live.

## Why it matters

**Move a class to another file and its copy silently breaks.** The failure is a `ValueError` from `get_utterance_base` (`utterance_mapping_rasa.py:2310-2312`) on an error/re-prompt branch — i.e. exactly the class of bug T3-01 is repairing, with exactly the same "nobody notices until a user hits the branch" property.

This is not hypothetical. It has **already forced a workaround**: when H2-08 extracted the contact validators to `backend/actions/services/contact/validators.py`, the extracted module-level functions could no longer derive `file_name` from a class at all, so they were forced onto an explicit key helper (`services/contact/utterances.py:6`):

```python
def contact_utterance(function_name: str, language_code: str, index: int = 1) -> str:
    return get_utterance_base("form_contact", function_name, index, language_code)
```

Note the hardcoded `"form_contact"` — the extraction had to **pin the file_name literal** because the derivation no longer worked. That is the tax this finding imposes, already being paid, once.

It also constrains T3-01: `form_story_main_route_step` is not a top-level key in `UTTERANCE_MAPPING`, and the cheap fix ("rename the module to match an existing key") is off the table precisely *because* renaming a module silently re-keys every utterance in it. T3-01 therefore adds the key rather than renaming — see [`../01-conversation-layer-spec.md`](../01-conversation-layer-spec.md) §1 step 3.

## Why it was deferred

- **Scope:** ~200 call sites across every form and action, vs T3-01's 4. Folding it in would have turned an S ticket into an M+ and delayed three live-bug fixes behind a large mechanical migration.
- **Urgency asymmetry:** T3-01's 4 sites are **broken right now** — 3 raise `ValueError` on live user paths. This one is a trap that fires only on a future refactor.
- **Sequencing:** T3-01 establishes the explicit-key convention at the `action_name` axis and builds the call-site-walking integrity test. Both are prerequisites for doing this one safely — the same test shape is what would guard a 200-site migration.

## Measured inventory (2026-07-15)

| Item | Count |
|---|---|
| Classes deriving `file_name` via `base_mixins.py:63` | ~200 (every `BaseAction` / `BaseFormValidationAction` subclass) |
| Top-level keys in `UTTERANCE_MAPPING` | see `utterance_mapping_rasa.py:94` (`form_seah_1`, `form_otp`, `form_status_check`, …) |
| Modules whose name does **not** match a mapping key | ≥1 confirmed (`form_story_main_route_step`) — **a full audit is step 1 of this ticket** |
| Existing explicit-`file_name` precedent | `services/contact/utterances.py:6` (hardcoded `"form_contact"`), `forms/form_status_check_skip.py:96-115` (`get_utterance_base(form_section, ...)`) |

## Definition of done

1. **Audit first** — enumerate every class's derived `file_name` and assert it resolves to a top-level `UTTERANCE_MAPPING` key. Expect this to surface more `form_story_main_route_step`-style mismatches. **This audit is independently valuable even if the migration is never done** — it converts a silent trap into a known list.
2. Introduce an explicit class-level key — e.g. a required `utterance_file: ClassVar[str]` on the base, replacing the `__module__` derivation at `base_mixins.py:63`.
3. Migrate all ~200 subclasses to declare it. Mechanical, but wide — consider a codemod, and land it in reviewable batches (per form family), not one commit.
4. Delete the `__module__` derivation.
5. Extend T3-01's `tests/actions/test_utterance_key_integrity.py` to assert **both** axes are explicit — no derived keys remain anywhere.
6. Fold in the two hardcoded-literal workarounds (`contact_utterance`'s `"form_contact"`, `form_status_check_skip`'s `form_section`) so they use the same declared key rather than a string literal.

## Endgame

Once both axes are explicit, the chatbot's copy is decoupled from its file layout and its function names, and `UTTERANCE_MAPPING` becomes a checkable contract rather than a set of coincidences. That is what "makes the chatbot refactorable" actually means — and it is the precondition for any future decomposition of `backend/actions/` (compare T3-02's decomposition of the orchestrator, which is unblocked because its state strings are already explicit).

**Recommended trigger:** schedule alongside or immediately after the next `backend/actions/` refactor, or in the clean-up sprint the standing deferral rule is accumulating toward ([`../../README.md`](../../README.md)).
