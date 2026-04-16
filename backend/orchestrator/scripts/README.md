# Orchestrator scripts

## extract_config.py

Extracts orchestrator config from Rasa-format YAMLs into our format.

**Input**

- `backend/orchestrator/config/domain.yml`
- `backend/orchestrator/config/source/stories/stories.yml`

**Output**

- `backend/orchestrator/config/flow.yaml`
- `backend/orchestrator/config/slots.yaml`

**Run** (from repository root, with `PYTHONPATH` including the repo root):

```bash
python backend/orchestrator/scripts/extract_config.py
```

Requires: PyYAML.
