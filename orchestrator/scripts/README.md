# Orchestrator Scripts

## extract_config.py

Extracts orchestrator config from Rasa YAMLs into our format.

**Input**:
- `rasa_chatbot/domain.yml`
- `rasa_chatbot/data/stories/stories.yml`

**Output**:
- `orchestrator/config/flow.yaml`
- `orchestrator/config/slots.yaml`

**Run** (from project root):
```bash
python orchestrator/scripts/extract_config.py
```

Requires: PyYAML (or use system Python with `pip install pyyaml`).
