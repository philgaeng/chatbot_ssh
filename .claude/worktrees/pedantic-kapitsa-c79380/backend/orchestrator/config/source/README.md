# Source YAML (tooling / reference)

Files under **`source/`** are **not** loaded by the REST orchestrator at runtime, except indirectly when you run **`scripts/extract_config.py`** to regenerate `flow.yaml` / `slots.yaml`.

- **`stories/`** — Rasa story YAML used as input to `extract_config.py`.
- **`rules/`** — `rules.yml` (migrated from the legacy layout).
- **`nlu/`** — NLU YAML kept for documentation or future tooling; production does not run Rasa NLU.
- **`data/`** — e.g. grievance counter and other small data files referenced by training/tooling.
- **`legacy_rasa_config/`** — Archived `config.yml`, `endpoints.yml`, `credentials.yml`, and `rasa/global.yml`. **Not** used by `backend.orchestrator` at runtime; prefer env-driven configuration for deployments.

Runtime **`domain.yml`** for the orchestrator lives one level up: **`backend/orchestrator/config/domain.yml`**.
