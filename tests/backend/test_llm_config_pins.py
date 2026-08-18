# SPDX-License-Identifier: Apache-2.0

"""
The pins that keep the indicator-4 claim true after this sprint ends.

Everything else in Sprint 1 is a migration: a one-off move of nine call sites onto a shared
registry. **These tests are what stops it decaying.** Without them the next feature adds a
hard-coded model name or a convenience import, nobody notices, and the DPG submission's central
claim — *"no provider and no model name is hard-coded anywhere"* — quietly stops being true.
That is not hypothetical: the standard/SEAH model pair had already been copied into four modules,
and two of those copies were invisible to the `grep "gpt-"` this sprint's own acceptance criteria
were written around.

Currently pinned:

* **T-17-b** — `backend/config/llm_config.py` imports nothing first-party.

Landing with their tickets:

* **T-17-c** (DPG-11/12) — no model name, base URL or timeout literal anywhere outside this file.
* **T-11-d** (DPG-11) — no `OpenAI(` outside the two client factories.
* **T-16-a** (DPG-16) — `.env.example` and `declared_env_vars()` agree, both ways.

Spec: docs/sprints/2026-08-llm/02-llm-agnostic-spec.md §DPG-17 · Ledger: TESTS.md T-17-b
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LLM_CONFIG = REPO_ROOT / "backend" / "config" / "llm_config.py"

# The three first-party package roots. An import from any of them captures the file.
FIRST_PARTY = ("backend", "ticketing", "ops", "channels", "scripts")


def _imported_modules(path: Path) -> set[str]:
    """Top-level module names imported by `path`, from the AST — including inside functions.

    Parsed, not grepped: a grep for `import backend` misses `from backend.config import x`
    written across two lines, and matches the word in a docstring. This file's whole purpose is
    to be harder to fool than a grep.
    """
    tree = ast.parse(path.read_text(), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # a relative import is first-party by construction
                modules.add(".")
            elif node.module:
                modules.add(node.module.split(".")[0])
    return modules


def test_the_shared_registry_imports_nothing_first_party():
    """
    **T-17-b — the portability pin.**

    `llm_config.py` lives under `backend/config/` for a reason with a precedent (`smtp_config.py`
    is imported by ticketing's live officer-invite path), but the location is only defensible
    while the file stays copy-portable: stdlib, `dataclasses`, `pydantic`, `pydantic-settings`.
    A single convenience import from `backend.config.constants` would turn a shared file into a
    backend-owned one, and ticketing would be importing the chatbot's service tree to learn a
    model name — the coupling this sprint exists to remove, reintroduced one layer down.

    If ticketing is ever extracted, this file moves with it and nothing else changes.
    """
    offenders = sorted(_imported_modules(LLM_CONFIG) & set(FIRST_PARTY + (".",)))

    assert not offenders, (
        f"backend/config/llm_config.py imports {offenders}, which captures it for that package. "
        "It must stay stdlib + pydantic only — both surfaces import it and neither owns it. "
        "See DPG-17 §Why backend/config/, and the module docstring."
    )


def test_the_registry_is_importable_without_any_first_party_package_on_the_path(tmp_path):
    """
    The stronger form of the same claim, and the one that cannot be argued with: copy the file
    somewhere with no repository on `sys.path` and import it. If it needs `backend/`, this fails.
    """
    import importlib.util
    import sys

    copied = tmp_path / "llm_config_copy.py"
    copied.write_text(LLM_CONFIG.read_text())

    spec = importlib.util.spec_from_file_location("llm_config_copy", copied)
    module = importlib.util.module_from_spec(spec)
    saved_path, sys.path = sys.path, [p for p in sys.path if Path(p).resolve() != REPO_ROOT]
    sys.modules["llm_config_copy"] = module  # @dataclass resolves annotations through this
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path = saved_path
        del sys.modules["llm_config_copy"]

    assert module.findings_task(is_seah=True) == "ticket_findings_seah"
    assert "MODEL_CLASSIFY" in module.declared_env_vars()
