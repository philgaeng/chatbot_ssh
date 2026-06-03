# Spec 21: Remove `rasa_chatbot/` and colocate domain + YAML sources under `backend/orchestrator`

**Status:** ✅ Completed  
**Depends on:** [15_actions_move_to_backend.md](15_actions_move_to_backend.md) (actions and orchestrator already under `backend/`; this spec finishes the migration)

---

## Mission

Eliminate the legacy **`rasa_chatbot/`** directory from the repository by:

1. Moving **runtime** and **tooling** YAML assets into a single home under **`backend/orchestrator/config/`** (and optional subfolders for “source” files used only by `extract_config.py`).
2. Updating **all** path constants, imports, tests, and docs so nothing references `rasa_chatbot`.
3. Removing obsolete **`sys.path`** manipulation that inserted `rasa_chatbot` for imports (actions already import as **`backend.actions`** in `backend/orchestrator/action_registry.py`).
4. Optionally **deleting the duplicate** top-level **`orchestrator/`** tree if it is still present and redundant with `backend/orchestrator/` (see §7).

**Non-goals (out of scope for this spec):**

- Removing **`rasa-sdk`** from `requirements.txt` or rewriting action classes off Rasa SDK types.
- Changing **`flow.yaml` / `slots.yaml`** schema or merging them with `domain.yml` (keep formats; only paths move).
- Re-training NLU or running `rasa train` (no Rasa server in production architecture).

---

## Background: canonical packages (do not confuse)

| Area | Canonical location | Notes |
|------|-------------------|--------|
| Orchestrator app (FastAPI, uvicorn) | **`backend.orchestrator`** | `docker-compose.yml` uses `uvicorn backend.orchestrator.main:app`; launch scripts use the same. |
| Action classes (Rasa SDK–style) | **`backend.actions`** | Already moved per Spec 15. |
| Flow + slots config | **`backend/orchestrator/config/flow.yaml`**, **`slots.yaml`** | Loaded by `backend/orchestrator/config_loader.py`. |
| Legacy duplicate | **`orchestrator/`** at repo root | If still present: old layout; **not** the Compose entrypoint unless someone runs it manually. Prefer deletion after parity check (§7). |

---

## Target layout after refactor

Use one predictable tree so Docker and local runs resolve paths the same way (repo root on `PYTHONPATH`).

```
backend/orchestrator/config/
  domain.yml                 # moved from rasa_chatbot/domain.yml — canonical for runtime
  flow.yaml                  # existing
  slots.yaml                 # existing
  source/                    # NEW optional folder: YAML only needed for extract_config / human reference
    stories/
      stories.yml
      ...                    # other story files as needed
    rules/
      rules.yml              # if present today under rasa_chatbot/data/
    nlu/                     # only if you still want NLU YAML in-repo for docs or future tooling
      ...
```

**Naming:** Prefer **`source/`** (or `legacy_yaml/`) over keeping the name `rasa_chatbot` in any path — the goal is to remove the *folder name* `rasa_chatbot` from the repo.

**Alternative (acceptable):** If the team prefers flatter paths, **`backend/orchestrator/config/stories/`** and **`backend/orchestrator/config/rules/`** at the same level as `domain.yml` instead of nesting under `source/`. Pick one convention and apply it everywhere (extract script, tests, docs).

**Do not copy:** `rasa_chatbot/.rasa/` (training cache) — exclude from git if reintroduced; add to `.gitignore` / `.dockerignore` under any new cache path.

**Low-value files:** `rasa_chatbot/config.yml`, `endpoints.yml`, `credentials.yml`, `rasa/global.yml` — not used by the REST orchestrator at runtime. Either move to **`docs/`** as archival reference, delete, or place under `config/source/` with a short README explaining they are **not** loaded by production. Do not leave ambiguous copies at repo root without documentation.

---

## Step 1 — Inventory and move files

1. List everything under **`rasa_chatbot/`** (excluding `.rasa/` cache).
2. **Must move for production parity:**
   - **`domain.yml`** → `backend/orchestrator/config/domain.yml`
3. **Move for `extract_config.py` and parity with Spec 1 inputs:**
   - **`data/stories/*.yml`** → under the chosen `config/source/...` or `config/stories/...`
   - **`data/rules/rules.yml`** (or equivalent path) → same
4. **Optional:** NLU YAML under `data/nlu/` — move only if still referenced by tooling or docs; otherwise archive or drop with team sign-off.
5. **Data files** (e.g. `data/grievance_counter.txt`): move next to stories or under `backend/orchestrator/config/source/data/` if any code references them by path; grep for `grievance_counter` and `rasa_chatbot` before deciding.

---

## Step 2 — Single module for “where is domain.yml?”

Introduce **one** helper (recommended) so path logic is not duplicated:

- e.g. **`backend/orchestrator/paths.py`** (or constants in `config_loader.py` if minimal) exporting:
  - `ORCHESTRATOR_CONFIG_DIR: Path`
  - `DOMAIN_YAML_PATH: Path` → `.../config/domain.yml`

Use this helper from:

- `backend/orchestrator/main.py` — `_load_domain` / domain path
- `backend/orchestrator/socket_server.py` — same
- Any script under `backend/orchestrator/scripts/` that loads `domain.yml`

Remove any **`Path(..., "rasa_chatbot", "domain.yml")`** string.

---

## Step 3 — Update `backend/orchestrator` Python files

Execute against **`backend/orchestrator/`** only (canonical). For each file:

| Task | Files / pattern |
|------|-----------------|
| Point domain loading to **`backend/orchestrator/config/domain.yml`** | `main.py`, `socket_server.py` |
| Replace **`_RASA_DIR`** / `rasa_chatbot` on `sys.path` | Remove inserting `rasa_chatbot`; repo root is enough for `backend.*`. **`action_registry.py`**: delete lines that add `_RASA_DIR` if actions are only `backend.actions`. |
| Replace **`from rasa_chatbot.actions...`** with **`from backend.actions...`** | `form_loop.py`, `state_machine.py`, `scripts/verify_form_loop.py` — grep `rasa_chatbot` under `backend/orchestrator/` |
| Logging namespaces | If `main.py` configures loggers named `"rasa_chatbot"`, rename to **`backend.actions`** or **`dialogue`** for clarity (optional cosmetic). |

**Note:** `backend/orchestrator/action_registry.py` may still contain dead `_RASA_DIR` entries left from migration — remove them if imports are exclusively `backend.actions`.

---

## Step 4 — Update `extract_config.py`

File: **`backend/orchestrator/scripts/extract_config.py`** (and duplicate under root `orchestrator/scripts/` if kept — prefer **one** copy; see §7).

- Set **`DOMAIN_PATH`**, **`STORIES_PATH`**, **`RULES_PATH`** to the new locations under `backend/orchestrator/config/` (and `source/` subtree if used).
- Update module docstring and **`backend/orchestrator/scripts/README.md`**.
- Run the script once from repo root; confirm **`flow.yaml`** and **`slots.yaml`** regenerate as expected; commit if diffs are intentional.

---

## Step 5 — Tests

| Location | Change |
|----------|--------|
| `tests/orchestrator/conftest.py` | Remove “rasa_chatbot on path” comments; set **`domain.yml`** path to `backend/orchestrator/config/domain.yml` (or use shared helper). |
| `tests/test_modify_grievance_flow.py` | Same domain path. |
| Grep **`tests/`** for `rasa_chatbot` | Zero results after refactor. |

Run:

```bash
pytest tests/orchestrator -q
pytest tests/test_modify_grievance_flow.py -q
```

(Adjust if your CI runs a broader subset.)

---

## Step 6 — Docs and repo hygiene

- **`requirements.txt`**: Update the comment that mentions `rasa_chatbot.actions` → describe **`backend.actions`**.
- **`docs/BACKEND.md`**, **`docs/deployment refactor/*`**: Replace paths like `rasa_chatbot/endpoints.yml` with “deprecated / removed” or point to env-driven config only.
- **`docs/Refactor specs/March 5/new_decision_engine_migration.md`**: Update references from `rasa_chatbot/actions/utils/...` to **`backend/actions/utils/...`**.
- **`.dockerignore`**: Ensure no reliance on `rasa_chatbot/`; add rules for any new cache folders if needed.

---

## Step 7 — Delete `rasa_chatbot/` and optional root `orchestrator/`

1. **`git grep rasa_chatbot`** from repo root must return **no** matches (or only historical mentions inside **this** spec file — prefer rephrase to past tense in other docs so grep is clean).
2. Delete directory **`rasa_chatbot/`** entirely.
3. **Root `orchestrator/`:** If it still exists alongside `backend/orchestrator/`:
   - Compare whether it is a stale duplicate. If **yes**, delete it and update any remaining docs/README that say `uvicorn orchestrator.main:app` to **`uvicorn backend.orchestrator.main:app`**.
   - If something still imports top-level `orchestrator`, fix those imports to **`backend.orchestrator`** first, then delete.

---

## Step 8 — Verification checklist

- [x] `python -c "from backend.orchestrator.main import app"` succeeds with `PYTHONPATH` = repo root.
- [ ] `docker compose config` and **`docker compose build`** succeed (same `Dockerfile` context).
- [x] `pytest tests/orchestrator` (and related) pass.
- [x] `rg rasa_chatbot` returns nothing in code or active docs (historical refactor specs may still mention the old path by name).
- [ ] Manual smoke: start orchestrator, hit a health or minimal endpoint that loads domain (if applicable).

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Missed string path to old `rasa_chatbot` | Use repo-wide grep before and after; add CI grep if desired. |
| `extract_config` inputs moved but script not run | Run script and review `flow.yaml` / `slots.yaml` diff. |
| Duplicate `orchestrator/` vs `backend/orchestrator` confusion | Delete duplicate only after entrypoints and docs list a single module path. |

---

## Reference: related specs

- [15_actions_move_to_backend.md](15_actions_move_to_backend.md) — actions → `backend/actions`, orchestrator → `backend/orchestrator`.
- [05_agent_specs_spike.md](05_agent_specs_spike.md) — Agent 1 config extraction inputs/outputs.
- [01_orchestrator.md](01_orchestrator.md) — orchestrator config dependency overview.

---

## Agent execution notes

- Prefer **small, mechanical commits**: (1) move files + add `paths.py`, (2) update imports/paths, (3) tests, (4) delete legacy dirs, (5) docs.
- Do **not** reformat unrelated code; match existing import and logging style in `backend/orchestrator/`.
- If a path is ambiguous, **search for consumers** (`grep -r`) before deleting a moved file.
