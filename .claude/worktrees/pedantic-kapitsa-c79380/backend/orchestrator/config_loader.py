"""
Load orchestrator config from flow.yaml and slots.yaml.
"""

import yaml
from typing import Any, Dict

from backend.orchestrator.paths import ORCHESTRATOR_CONFIG_DIR as _CONFIG_DIR


def load_config() -> Dict[str, Any]:
    """Load flow.yaml and slots.yaml, return combined config."""
    config: Dict[str, Any] = {"slot_defaults": {}}

    flow_path = _CONFIG_DIR / "flow.yaml"
    if flow_path.exists():
        with open(flow_path) as f:
            config["flow"] = yaml.safe_load(f) or {}

    slots_path = _CONFIG_DIR / "slots.yaml"
    if slots_path.exists():
        with open(slots_path) as f:
            slots_config = yaml.safe_load(f) or {}
        slots = slots_config.get("slots", {})
        for name, meta in slots.items():
            if isinstance(meta, dict) and "default" in meta:
                config["slot_defaults"][name] = meta["default"]

    return config
