"""
Single source of truth for orchestrator config paths (domain, stories, rules, extract_config inputs).

Repo root must be on PYTHONPATH so `backend.*` imports resolve.
"""

from pathlib import Path

# backend/orchestrator/paths.py -> parents[2] = repository root
REPO_ROOT: Path = Path(__file__).resolve().parents[2]

ORCHESTRATOR_CONFIG_DIR: Path = Path(__file__).resolve().parent / "config"

DOMAIN_YAML_PATH: Path = ORCHESTRATOR_CONFIG_DIR / "domain.yml"

# YAML used by extract_config and kept for tooling / reference (not loaded by REST runtime except as noted)
SOURCE_DIR: Path = ORCHESTRATOR_CONFIG_DIR / "source"
STORIES_DIR: Path = SOURCE_DIR / "stories"
STORIES_YAML_PATH: Path = STORIES_DIR / "stories.yml"
RULES_YAML_PATH: Path = SOURCE_DIR / "rules" / "rules.yml"
