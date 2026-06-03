# Spec 15: Move `rasa_chatbot/actions` and Orchestrator to Backend

**Status: ✅ Completed** (actions and orchestrator now live under `backend/`. Old `rasa_chatbot/actions/` and `orchestrator/` can be removed when no longer needed.)

---

## Purpose

Move the **actions** package and the **orchestrator** into the backend in a single change. Actions leave `rasa_chatbot/` for `backend/actions/`; the orchestrator moves from repo root to `backend/orchestrator/`. Doing both at once avoids touching orchestrator imports twice and gives one consistent “server” tree. This spec lists target locations, all import and path updates (actions, orchestrator internal, orchestrator external, tests), and entry-point changes.

---

## Recommendation: Where to Put Actions

**Recommendation: move to `backend/actions/`** (not a new top-level `actions/` at repo root).

**Reasons:**

1. **Existing coupling:** The actions already depend heavily on `backend`:
   - `backend.shared_functions.helpers_repo`
   - `backend.services.messaging`, `backend.services.database_services.postgres_services`
   - `backend.config.constants`, `backend.config.database_constants`
   - `backend.task_queue.registered_tasks`
   Placing actions under `backend/` reflects this: they are server-side conversation logic consumed by the orchestrator.

2. **Single “server” package:** The orchestrator today adds both repo root and `rasa_chatbot` to `sys.path` to load actions and domain. After the move, it can rely on repo root (and optionally `backend` if not already on path). All code the orchestrator needs from the app lives under `backend` (actions + APIs/services).

3. **Clear dependency direction:** `orchestrator` → `backend.actions` (and backend APIs if needed). No need for a separate top-level `actions/` package that would sit alongside `backend/` and `orchestrator/`.

**Alternative (not recommended here):** A top-level `actions/` directory would work (e.g. `from actions.forms.form_grievance import ...`). The orchestrator would then depend on two top-level packages (`backend`, `actions`). Prefer `backend/actions` for simplicity.

---

## Should the orchestrator move under backend too?

**Recommendation: do both moves in one go.** Many of the edits for the actions move are inside the orchestrator (action_registry, state_machine, form_loop, path setup). If we move the orchestrator in a follow-up, we’d touch those files again (imports, paths). Doing **actions + orchestrator** together means one round of changes and one consistent layout: `backend/{api, orchestrator, actions, ...}`.

- **Single migration:** All `rasa_chatbot.actions` → `backend.actions` and all `orchestrator` → `backend.orchestrator` in one pass.
- **Path setup once:** Repo root (and thus `backend`) on path; no need to keep a separate `orchestrator` root package.
- **Entry points:** Update launch scripts to run `uvicorn backend.orchestrator.main:app` (or equivalent) instead of `orchestrator.main:app`.

This spec therefore **includes the orchestrator move**: target layout is `backend/actions/` and `backend/orchestrator/`. The sections below cover both.

---

## Scope

- **Actions:** Move entire tree `rasa_chatbot/actions/` → `backend/actions/` (same internal layout: `base_classes/`, `forms/`, `utils/`).
- **Orchestrator:** Move entire directory `orchestrator/` → `backend/orchestrator/` (preserve structure: `adapters/`, `scripts/`, config, etc.).
- **Out of scope:** Moving or changing `rasa_chatbot/domain.yml`, `rasa_chatbot/data/`, or any other Rasa config; those stay in `rasa_chatbot/` until a later decision.

---

## Import Updates Overview

| Consumer | Current prefix | New prefix |
|----------|----------------|------------|
| Actions (internal) | `rasa_chatbot.actions.*` | `backend.actions.*` |
| Orchestrator (internal) | `rasa_chatbot.actions.*` | `backend.actions.*` |
| Orchestrator (internal) | `orchestrator.*` | `backend.orchestrator.*` |
| Tests / scripts | `rasa_chatbot.actions.*` | `backend.actions.*` |
| Tests / scripts | `orchestrator.*` | `backend.orchestrator.*` |

**Note:** Imports from the rest of `backend` (e.g. `backend.shared_functions`, `backend.config`, `backend.services`, `backend.task_queue`) were already absolute in the original actions code and were **not changed** — only `rasa_chatbot.actions.*` and `orchestrator.*` were updated. After the move, orchestrator code lives under `backend.orchestrator` and imports `backend.actions`; anything that imported `orchestrator` must import `backend.orchestrator`.

---

## 1. Imports Inside the Actions Package (after move to `backend/actions/`)

Every `rasa_chatbot.actions` import must become `backend.actions`. Relative imports (e.g. `from .base_mixins import ...`) stay as-is.

### 1.1 `backend/actions/base_classes/base_classes.py`

| Line (approx.) | Current | New |
|----------------|---------|-----|
| 11 | `from rasa_chatbot.actions.utils.utterance_mapping_rasa import ...` | `from backend.actions.utils.utterance_mapping_rasa import ...` |

### 1.2 `backend/actions/base_classes/base_mixins.py`

| Line (approx.) | Current | New |
|----------------|---------|-----|
| 14 | `from rasa_chatbot.actions.utils.utterance_mapping_rasa import get_utterance_base, get_buttons_base, SENSITIVE_ISSUES_UTTERANCES_AND_BUTTONS, UTTERANCE_MAPPING` | `from backend.actions.utils.utterance_mapping_rasa import ...` |
| 15 | `from rasa_chatbot.actions.utils.mapping_buttons import VALIDATION_SKIP, BUTTON_SKIP, BUTTON_AFFIRM, BUTTON_DENY` | `from backend.actions.utils.mapping_buttons import ...` |

### 1.3 `backend/actions/forms/form_modify_grievance.py`

| Current | New |
|---------|-----|
| `from rasa_chatbot.actions.base_classes.base_classes import BaseFormValidationAction, BaseAction` | `from backend.actions.base_classes.base_classes import BaseFormValidationAction, BaseAction` |

### 1.4 `backend/actions/forms/form_modify_contact.py`

| Current | New |
|---------|-----|
| `from rasa_chatbot.actions.forms.form_contact import ContactFormValidationAction` | `from backend.actions.forms.form_contact import ContactFormValidationAction` |
| `from rasa_chatbot.actions.base_classes.base_classes import BaseAction` | `from backend.actions.base_classes.base_classes import BaseAction` |

### 1.5 `backend/actions/forms/form_status_check.py`

| Current | New |
|---------|-----|
| `from rasa_chatbot.actions.base_classes.base_classes import BaseFormValidationAction, BaseAction` | `from backend.actions.base_classes.base_classes import BaseFormValidationAction, BaseAction` |

### 1.6 `backend/actions/forms/form_sensitive_issues.py`

| Current | New |
|---------|-----|
| `from rasa_chatbot.actions.base_classes.base_classes import BaseFormValidationAction, BaseAction` | `from backend.actions.base_classes.base_classes import BaseFormValidationAction, BaseAction` |

### 1.7 `backend/actions/forms/form_grievance.py`

| Current | New |
|---------|-----|
| `from rasa_chatbot.actions.base_classes.base_classes  import BaseFormValidationAction, BaseAction` | `from backend.actions.base_classes.base_classes import BaseFormValidationAction, BaseAction` |

### 1.8 `backend/actions/forms/form_otp.py`

| Current | New |
|---------|-----|
| `from rasa_chatbot.actions.base_classes.base_classes import BaseFormValidationAction, BaseAction` | `from backend.actions.base_classes.base_classes import BaseFormValidationAction, BaseAction` |

### 1.9 `backend/actions/forms/form_grievance_complainant_review.py`

| Current | New |
|---------|-----|
| `from rasa_chatbot.actions.base_classes.base_classes import BaseFormValidationAction, BaseAction, SKIP_VALUE` | `from backend.actions.base_classes.base_classes import ...` |
| `from rasa_chatbot.actions.action_submit_grievance import BaseActionSubmit` | `from backend.actions.action_submit_grievance import BaseActionSubmit` |
| `from rasa_chatbot.actions.utils.utterance_mapping_rasa import BUTTON_SKIP, BUTTON_AFFIRM, BUTTON_DENY` | `from backend.actions.utils.utterance_mapping_rasa import ...` |

### 1.10 `backend/actions/forms/form_contact.py`

| Current | New |
|---------|-----|
| `from rasa_chatbot.actions.base_classes.base_classes  import BaseAction, BaseFormValidationAction` | `from backend.actions.base_classes.base_classes import BaseAction, BaseFormValidationAction` |

### 1.11 `backend/actions/forms/form_story_main_route_step.py`

| Current | New |
|---------|-----|
| `from rasa_chatbot.actions.base_classes.base_classes import BaseFormValidationAction, BaseAction` | `from backend.actions.base_classes.base_classes import ...` |

### 1.12 `backend/actions/forms/form_status_check_skip.py`

| Current | New |
|---------|-----|
| `from rasa_chatbot.actions.forms.form_contact import ContactFormValidationAction` | `from backend.actions.forms.form_contact import ContactFormValidationAction` |
| `from rasa_chatbot.actions.base_classes.base_classes import BaseAction` | `from backend.actions.base_classes.base_classes import BaseAction` |
| (inside a function ~L90) `from rasa_chatbot.actions.utils.utterance_mapping_rasa import get_utterance_base, get_buttons_base` | `from backend.actions.utils.utterance_mapping_rasa import get_utterance_base, get_buttons_base` |

### 1.13 `backend/actions/action_ask_commons.py`

| Current | New |
|---------|-----|
| `from rasa_chatbot.actions.base_classes.base_classes import BaseAction` | `from backend.actions.base_classes.base_classes import BaseAction` |

### 1.14 `backend/actions/action_submit_grievance.py`

| Current | New |
|---------|-----|
| `from .base_classes.base_classes import BaseAction` | Keep as relative: `from backend.actions.base_classes.base_classes import BaseAction` (or keep `from .base_classes.base_classes` — relative still works inside `backend.actions`) |

Relative `from .base_classes.base_classes` remains valid inside `backend.actions`; no change required unless you standardize on absolute.

### 1.15 `backend/actions/generic_actions.py`

| Current | New |
|---------|-----|
| `from .base_classes.base_classes  import BaseAction` | Relative is fine; or `from backend.actions.base_classes.base_classes import BaseAction` |

### 1.16 `backend/actions/__init__.py`

- Imports from `.generic_actions`, `.action_ask_commons`, `.forms.*`, `.test_routing` are relative and stay as-is.
- `from backend.services.database_services.postgres_services import db_manager` — no change (already backend).
- If `get_action_classes()` builds module names like `actions.{file_path.stem}`, update to `backend.actions.{file_path.stem}` so that `import_module` resolves correctly when run from repo root (or document that this helper is only used when `backend` is on path).

### 1.17 `backend/actions/utils/utterance_mapping_rasa.py`

- Has `from .mapping_buttons import *` — keep (relative).

### 1.18 `backend/actions/utils/export_utterances_to_csv.py` and `export_buttons_to_csv.py`

- Currently: `from utterance_mapping_rasa import UTTERANCE_MAPPING` (and `sys.path.insert(0, os.path.dirname(...))`). After the move, either:
  - `from backend.actions.utils.utterance_mapping_rasa import UTTERANCE_MAPPING`, and ensure repo root (or backend) is on path when running the script, or
  - Use relative: `from .utterance_mapping_rasa import UTTERANCE_MAPPING` (if run as part of the package).

---

## 2. Orchestrator Files (after move: `backend/orchestrator/`)

Replace all `rasa_chatbot.actions` imports with `backend.actions`. Remove or repurpose `_RASA_DIR` so that only repo root (and thus `backend`) is needed for imports. File paths below refer to the current `orchestrator/` layout; after the move they live under `backend/orchestrator/`.

### 2.1 `backend/orchestrator/action_registry.py`

| Location | Current | New |
|----------|---------|-----|
| Comment / path (L10–16) | `# Ensure project root and rasa_chatbot are on path`; `_RASA_DIR = ... "rasa_chatbot"`; `if _RASA_DIR not in sys.path: sys.path.insert(0, _RASA_DIR)` | Either remove `_RASA_DIR` for actions, or keep only for domain.yml if still needed elsewhere. Ensure repo root (and thus `backend`) is on path. |
| L27–85 (all lazy imports) | `from rasa_chatbot.actions.generic_actions import (...)` etc. | `from backend.actions.generic_actions import (...)` |
| | `from rasa_chatbot.actions.forms.form_grievance import (...)` | `from backend.actions.forms.form_grievance import (...)` |
| | … (every `rasa_chatbot.actions.*`) | … `backend.actions.*` |

**Full list of import lines to change in action_registry.py:**

- `rasa_chatbot.actions.generic_actions` → `backend.actions.generic_actions`
- `rasa_chatbot.actions.forms.form_grievance` → `backend.actions.forms.form_grievance`
- `rasa_chatbot.actions.forms.form_sensitive_issues` → `backend.actions.forms.form_sensitive_issues`
- `rasa_chatbot.actions.forms.form_modify_grievance` → `backend.actions.forms.form_modify_grievance`
- `rasa_chatbot.actions.forms.form_modify_contact` → `backend.actions.forms.form_modify_contact`
- `rasa_chatbot.actions.forms.form_status_check` → `backend.actions.forms.form_status_check`
- `rasa_chatbot.actions.forms.form_otp` → `backend.actions.forms.form_otp`
- `rasa_chatbot.actions.forms.form_status_check_skip` → `backend.actions.forms.form_status_check_skip`
- `rasa_chatbot.actions.forms.form_grievance_complainant_review` → `backend.actions.forms.form_grievance_complainant_review`
- `rasa_chatbot.actions.action_submit_grievance` → `backend.actions.action_submit_grievance`
- `rasa_chatbot.actions.action_ask_commons` → `backend.actions.action_ask_commons`

### 2.2 `backend/orchestrator/state_machine.py`

| Location | Current | New |
|----------|---------|-----|
| L24 | `_RASA_DIR = os.path.join(_REPO_ROOT, "rasa_chatbot")` (+ sys.path) | Keep if domain.yml or other Rasa config is still loaded from `rasa_chatbot/`; otherwise can be removed or repurposed. |
| L45 | `from rasa_chatbot.actions.forms.form_grievance import ValidateFormGrievance` | `from backend.actions.forms.form_grievance import ValidateFormGrievance` |
| L53 | `from rasa_chatbot.actions.forms.form_status_check import ValidateFormStatusCheck1` | `from backend.actions.forms.form_status_check import ValidateFormStatusCheck1` |
| L61 | `from rasa_chatbot.actions.forms.form_status_check import ValidateFormStatusCheck2` | `from backend.actions.forms.form_status_check import ValidateFormStatusCheck2` |
| L69 | `from rasa_chatbot.actions.forms.form_contact import ValidateFormContact` | `from backend.actions.forms.form_contact import ValidateFormContact` |
| L77 | `from rasa_chatbot.actions.forms.form_otp import ValidateFormOtp` | `from backend.actions.forms.form_otp import ValidateFormOtp` |
| L85 | `from rasa_chatbot.actions.forms.form_grievance_complainant_review import ValidateFormGrievanceComplainantReview` | `from backend.actions.forms.form_grievance_complainant_review import ValidateFormGrievanceComplainantReview` |
| L93 | `from rasa_chatbot.actions.forms.form_status_check_skip import ValidateFormSkipStatusCheck` | `from backend.actions.forms.form_status_check_skip import ValidateFormSkipStatusCheck` |
| L104 | `from rasa_chatbot.actions.forms.form_sensitive_issues import ValidateFormSensitiveIssues` | `from backend.actions.forms.form_sensitive_issues import ValidateFormSensitiveIssues` |
| L115 | `from rasa_chatbot.actions.forms.form_modify_grievance import ValidateFormModifyGrievanceDetails` | `from backend.actions.forms.form_modify_grievance import ValidateFormModifyGrievanceDetails` |
| L126 | `from rasa_chatbot.actions.forms.form_modify_contact import ValidateFormModifyContact` | `from backend.actions.forms.form_modify_contact import ValidateFormModifyContact` |

### 2.3 `backend/orchestrator/form_loop.py`

| Location | Current | New |
|----------|---------|-----|
| L12–16 | `_RASA_DIR = ... "rasa_chatbot"` (sys.path) | Remove or keep for other uses; ensure repo root on path for `backend`. |
| L263–290 (all form imports) | `from rasa_chatbot.actions.forms.form_grievance import ValidateFormGrievance` etc. | `from backend.actions.forms.form_grievance import ValidateFormGrievance` etc. (same pattern for all 10 form imports). |

**Form imports in form_loop.py to change:**

- `rasa_chatbot.actions.forms.form_grievance` → `backend.actions.forms.form_grievance`
- `rasa_chatbot.actions.forms.form_contact` → `backend.actions.forms.form_contact`
- `rasa_chatbot.actions.forms.form_otp` → `backend.actions.forms.form_otp`
- `rasa_chatbot.actions.forms.form_status_check` → `backend.actions.forms.form_status_check` (×2)
- `rasa_chatbot.actions.forms.form_status_check_skip` → `backend.actions.forms.form_status_check_skip`
- `rasa_chatbot.actions.forms.form_grievance_complainant_review` → `backend.actions.forms.form_grievance_complainant_review`
- `rasa_chatbot.actions.forms.form_sensitive_issues` → `backend.actions.forms.form_sensitive_issues`
- `rasa_chatbot.actions.forms.form_modify_grievance` → `backend.actions.forms.form_modify_grievance`
- `rasa_chatbot.actions.forms.form_modify_contact` → `backend.actions.forms.form_modify_contact`

### 2.4 `backend/orchestrator/scripts/verify_form_loop.py`

| Current | New |
|---------|-----|
| `from rasa_chatbot.actions.forms.form_grievance import ValidateFormGrievance` | `from backend.actions.forms.form_grievance import ValidateFormGrievance` |
| `path = PROJECT_ROOT / "rasa_chatbot" / "domain.yml"` | Leave as-is (domain still in rasa_chatbot). |

### 2.5 Other orchestrator files

- **backend/orchestrator/main.py**, **backend/orchestrator/socket_server.py**: They reference `rasa_chatbot` for `domain.yml` and path setup; no change to actions imports. Keep `rasa_chatbot` on path only if domain/config is still loaded from there.
- **backend/orchestrator/scripts/extract_config.py**: Uses `rasa_chatbot/` paths for domain and stories; no actions imports.
- **backend/orchestrator/adapters/tracker.py**, **dispatcher.py**: Comments mention “rasa_chatbot actions”; update to “backend.actions” for clarity.

---

## 3. Orchestrator move: internal and external imports

After moving the directory `orchestrator/` → `backend/orchestrator/`, every import of the form `from orchestrator.X` or `import orchestrator` must become `from backend.orchestrator.X` (or `import backend.orchestrator`). Ensure the repo root is on `sys.path` so `backend` is importable.

### 3.1 Internal imports (inside `backend/orchestrator/`)

Each of these files currently imports other orchestrator modules; update to `backend.orchestrator.*`:

| File | Current | New |
|------|---------|-----|
| `backend/orchestrator/state_machine.py` | `from orchestrator.adapters import ...`; `from orchestrator.action_registry import ...`; `from orchestrator.form_loop import ...` | `from backend.orchestrator.adapters import ...`; `from backend.orchestrator.action_registry import ...`; `from backend.orchestrator.form_loop import ...` |
| `backend/orchestrator/action_registry.py` | `from orchestrator.adapters import ...` | `from backend.orchestrator.adapters import ...` |
| `backend/orchestrator/form_loop.py` | `from orchestrator.adapters import ...`; `from orchestrator.action_registry import ...` | `from backend.orchestrator.adapters import ...`; `from backend.orchestrator.action_registry import ...` |
| `backend/orchestrator/main.py` | `from orchestrator.session_store import ...`; `from orchestrator.state_machine import ...`; `from orchestrator.config_loader import ...`; `from orchestrator.socket_server import ...` | `from backend.orchestrator.session_store import ...`; etc. |
| `backend/orchestrator/socket_server.py` | `from orchestrator.session_store import ...`; `from orchestrator.state_machine import ...`; `from orchestrator.config_loader import ...` | `from backend.orchestrator.session_store import ...`; etc. |
| `backend/orchestrator/scripts/verify_form_loop.py` | `from orchestrator.form_loop import run_form_turn` | `from backend.orchestrator.form_loop import run_form_turn` |
| `backend/orchestrator/scripts/verify_action_layer.py` | `from orchestrator.adapters import ...`; `from orchestrator.action_registry import ...` | `from backend.orchestrator.adapters import ...`; `from backend.orchestrator.action_registry import ...` |

### 3.2 External imports (tests)

| File | Current | New |
|------|---------|-----|
| `tests/test_modify_grievance_flow.py` | `from orchestrator.session_store import ...`; `from orchestrator.state_machine import ...` | `from backend.orchestrator.session_store import ...`; `from backend.orchestrator.state_machine import ...` |
| `tests/orchestrator/test_form_loop.py` | `from orchestrator.form_loop import ...` | `from backend.orchestrator.form_loop import ...` |
| `tests/orchestrator/test_action_registry.py` | `from orchestrator.adapters import ...`; `from orchestrator.action_registry import ...` | `from backend.orchestrator.adapters import ...`; `from backend.orchestrator.action_registry import ...` |
| `tests/orchestrator/test_adapters.py` | `from orchestrator.adapters import ...` | `from backend.orchestrator.adapters import ...` |
| `tests/orchestrator/conftest.py` | `from orchestrator.adapters import ...`; `from orchestrator.session_store import ...`; `from orchestrator.main import app` | `from backend.orchestrator.adapters import ...`; `from backend.orchestrator.session_store import ...`; `from backend.orchestrator.main import app` |

### 3.3 Entry points (launch scripts)

Update the module used to run the orchestrator FastAPI app:

| File | Current | New |
|------|---------|-----|
| `scripts/rest_api/launch_servers_celery.sh` | `uvicorn orchestrator.main:app` | `uvicorn backend.orchestrator.main:app` |
| `scripts/rest_api/launch_servers.sh` | `uvicorn orchestrator.main:app` | `uvicorn backend.orchestrator.main:app` |

Keep `PYTHONPATH="$BASE_DIR"` (repo root) so that `backend` is on the path. No other script changes required unless other scripts invoke the orchestrator by module name.

---

## 4. Tests (actions imports)

| File | Current | New |
|------|---------|-----|
| `tests/test_modify_contact_helpers.py` | `from rasa_chatbot.actions.forms.modify_contact_helpers import (...)` | `from backend.actions.forms.modify_contact_helpers import (...)` |
| `tests/orchestrator/test_form_loop.py` | `from rasa_chatbot.actions.forms.form_grievance import ValidateFormGrievance`; `from rasa_chatbot.actions.forms.form_status_check import ValidateFormStatusCheck1` | `from backend.actions.forms.form_grievance import ValidateFormGrievance`; `from backend.actions.forms.form_status_check import ValidateFormStatusCheck1` |
| `tests/test_select_grievances_function.py` | `from rasa_chatbot.actions.form_status_check import ValidateFormStatusCheck` | `from backend.actions.forms.form_status_check import ValidateFormStatusCheck`. **Done:** Added alias `ValidateFormStatusCheck = ValidateFormStatusCheck1` at end of `form_status_check.py` so this test continues to work. |

---

## 5. Path and Startup

- **Repo root** must be on `sys.path` (or `PYTHONPATH`) so that `backend` is importable. Then `backend.actions` and `backend.orchestrator` both resolve.
- **Orchestrator code** (now under `backend/orchestrator/`): Remove or repurpose `_RASA_DIR` for actions; keep `_RASA_DIR` only if domain.yml or other Rasa config is still loaded from `rasa_chatbot/`.
- **Launch scripts:** Use `uvicorn backend.orchestrator.main:app` with `PYTHONPATH` set to repo root (see §3.3).
- **Tests:** Run with repo root in `sys.path` (e.g. `pytest` from repo root).

---

## 6. Execution Checklist (summary)

*All steps below were completed during implementation.*

1. **Move actions:** Copy or move `rasa_chatbot/actions/` → `backend/actions/` (preserve structure: `base_classes/`, `forms/`, `utils/`). ✅
2. **Move orchestrator:** Move `orchestrator/` → `backend/orchestrator/` (preserve structure: `adapters/`, `scripts/`, config, etc.). ✅
3. **Inside `backend/actions/`:** Replace every `rasa_chatbot.actions` with `backend.actions` (see §1). Fix `utils/export_*.py` as needed. ✅
4. **Inside `backend/orchestrator/`:** Replace every `rasa_chatbot.actions` with `backend.actions` (see §2). Replace every `orchestrator.` with `backend.orchestrator.` (see §3.1). Set `_REPO_ROOT` to three levels up. ✅
5. **Tests:** Update actions imports to `backend.actions` (see §4) and orchestrator imports to `backend.orchestrator` (see §3.2). ✅
6. **Launch scripts:** Update uvicorn to `backend.orchestrator.main:app` (see §3.3). ✅
7. **Optional:** Remove or archive `rasa_chatbot/actions/` and the old `orchestrator/` directory once everything passes.
8. **Smoke test:** Start orchestrator via launch script, run POST /message for a short flow; run relevant tests (form_loop, adapters, action_registry, modify_contact_helpers, etc.). ✅

---

## 8. Post-implementation notes (done)

- **Repo root depth:** Files under `backend/orchestrator/` use `_REPO_ROOT = ... parents[2]` (or three/four `dirname`s for scripts) so repo root is on path. Files under `backend/actions/` use three levels up in `__init__.py` for the same reason.
- **backend/actions/__init__.py:** `get_action_classes()` now uses `module_name = f"backend.actions.{file_path.stem}"` so `import_module` resolves when run from repo root. The optional `custom_policy` import is guarded with `if "rasa" in str(e)` so REST-only envs without Rasa don’t fail.
- **Export scripts:** `utils/export_utterances_to_csv.py` and `export_buttons_to_csv.py` now use `from backend.actions.utils.utterance_mapping_rasa import UTTERANCE_MAPPING` (no `sys.path.insert`).
- **Logger names:** `utils/logging_config.py` logger names were updated from `rasa_chatbot.actions` to `backend.actions`.
- **Optional cleanup:** Remove `rasa_chatbot/actions/` and `orchestrator/` at repo root once you are satisfied everything runs from `backend/actions` and `backend/orchestrator`.

---

## 7. Files to Touch (quick reference)

| Area | Files |
|------|--------|
| **Actions (internal)** | `backend/actions/`: `base_classes/base_classes.py`, `base_classes/base_mixins.py`, all `forms/form_*.py` in §1, `action_ask_commons.py`, `action_submit_grievance.py`, `generic_actions.py`, `__init__.py`, `utils/export_utterances_to_csv.py`, `utils/export_buttons_to_csv.py` |
| **Orchestrator (internal)** | `backend/orchestrator/`: `action_registry.py`, `state_machine.py`, `form_loop.py`, `main.py`, `socket_server.py`, `scripts/verify_form_loop.py`, `scripts/verify_action_layer.py`; comment updates in `adapters/tracker.py`, `adapters/dispatcher.py` |
| **Tests** | `tests/test_modify_contact_helpers.py`, `tests/test_modify_grievance_flow.py`, `tests/test_select_grievances_function.py`, `tests/orchestrator/test_form_loop.py`, `tests/orchestrator/test_action_registry.py`, `tests/orchestrator/test_adapters.py`, `tests/orchestrator/conftest.py` |
| **Scripts** | `scripts/rest_api/launch_servers_celery.sh`, `scripts/rest_api/launch_servers.sh` |

---

All import and entry-point updates for the combined move are captured above. The migration is complete; this doc is kept as the reference for what was done and for any future consumers that need to import `backend.actions` or `backend.orchestrator`.
