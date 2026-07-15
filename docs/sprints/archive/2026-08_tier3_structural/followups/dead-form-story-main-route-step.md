# Follow-up — `forms/form_story_main_route_step.py` is dead code (79 lines, 0 importers)

> **Status:** 🔴 **OPEN — deferred out of T3-01 (2026-07-15).** · **Owner:** chatbot / actions · **Priority:** low (it cannot misbehave — nothing can reach it; the cost is that it *looks* live and misleads readers, including two prior review passes)
> **Origin:** the T3-01 §0 reachability trace ([`../00-reassessment.md`](../00-reassessment.md) §4, D-13). Deferred per the T3-01 spec's own §Out of scope: *"Dead branches, if §0 finds any of the three unreachable — that is a dead-code finding, not this ticket's job. Log it."*

## The finding

`backend/actions/forms/form_story_main_route_step.py` defines two classes — `ValidateMenuForm` (`:13`) and `ValidateFormStoryStep` (`:63`). **Neither is reachable in any shipping deployment.**

## The proof (four independent legs, all verified 2026-07-15)

| Leg | Evidence |
|---|---|
| **No importer** | `grep -rn "form_story_main_route_step" --include=*.py .` returns **nothing** outside the file itself. Nothing imports the module, so its classes are never even constructed. |
| **Not in the form registry** | `backend/orchestrator/form_loop.py:328-370` — `_FORMS` is the *only* place form classes are instantiated (`get_form(active_loop)`). It lists 15 forms; `ValidateMenuForm` is **not** among them. |
| **No name reference** | `grep -rn "ValidateMenuForm"` repo-wide hits exactly one line: its own `class` statement. |
| **No Rasa action server** | A `rasa run actions` server would auto-discover it by class scan, which would flip this verdict. There is none: the only `action_endpoint` is `backend/orchestrator/config/source/legacy_rasa_config/endpoints.yml:13` (**legacy**, by its own path); no `rasa run actions` / `--actions` anywhere; and `docker-compose.yml` ships `orchestrator`, `backend`, `db_init`, `celery_file`, `celery_default`, `celery_llm`, `redis`, `db`, `nginx` — **no action server**. |

## Why it looks live (and fooled two review passes)

`backend/orchestrator/config/domain.yml:1054` still declares `validate_form_story_main`, and `:975-976`/`:1148` declare the matching `action_ask_*` actions and the `form_story_main` form. **The domain is Rasa-era config that the orchestrator's hand-rolled state machine no longer honors for this form** — `run_flow_turn` drives forms through `_FORMS`, not through the domain's action list. So a grep for the form name finds plenty of hits and none of them mean the code runs.

This is exactly why the T3-01 §0 gate existed, and why the reassessment insisted the count be resolved by MRO and the reachability by trace rather than grep.

## What T3-01 did and did not do

T3-01 **did**: give the call site (`:33`) an explicit `key=` and author its `UTTERANCE_MAPPING` entry, so the ticket's invariant — *every key passed to `get_utterance` resolves* — holds **totally**, with no exclusion list or `xfail` in `tests/actions/test_utterance_key_integrity.py`. An exclusion list is the thing that rots; a two-string mapping entry is not.

T3-01 **did not**: delete the module. That is this ticket.

## Definition of done

1. **Re-run all four proof legs above.** They are cheap and they are the whole basis for deleting. If a Rasa action server has since been added to any deployment, **stop** — the verdict flips and `ValidateMenuForm` becomes live (and its `validate_language_code` re-prompt would then be a real user-facing path).
2. Delete `backend/actions/forms/form_story_main_route_step.py`.
3. Delete the `form_story_main_route_step` entry from `UTTERANCE_MAPPING` (`utils/utterance_mapping_rasa.py`) — added by T3-01 solely to keep the invariant total. **Module and entry must go together**, or the mapping keeps copy for a file that no longer exists.
4. Drop the corresponding row from the NE review CSV.
5. Audit the neighbouring domain declarations (`domain.yml:975-976`, `:1054`, `:1148`) — if `form_story_main` is dead config too, remove it in the same pass so the next reader isn't misled the same way. **Check first**: `domain.yml` is shared, and other entries in it *are* live.
6. `tests/actions/test_utterance_key_integrity.py` must stay green with **no** exclusion added — after the delete, the call site is simply gone.

**Recommended trigger:** the clean-up sprint the standing deferral rule is accumulating toward ([`../../README.md`](../../../README.md)). Natural companion: the `file_name` derivation follow-up ([`utterance-file-name-derivation.md`](utterance-file-name-derivation.md)), whose step-1 audit walks the same classes and would re-confirm leg 1 for free.
