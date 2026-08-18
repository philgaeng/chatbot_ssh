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
import re
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

# ═════════════════════════════════════════════════════════════════════════════
# T-11-d — no client construction and no model literal outside the registry
# ═════════════════════════════════════════════════════════════════════════════

MODEL_LITERAL = re.compile(r"\b(gpt-[\w.]+|whisper-[\w.]+|o[13]-mini|text-embedding-\w+)")

# The two files allowed to say these things, and what each is allowed to say.
CLIENT_FACTORIES = {
    "backend/services/llm_client.py",       # DPG-11 — the chatbot surface's only constructor
    "ticketing/clients/llm_client.py",      # DPG-12 — the ticketing surface's only constructor
}
MODEL_REGISTRY = "backend/config/llm_config.py"

# Widened to `ticketing/` by DPG-12, in the commit that removed that surface's literals — not
# before, because a pin that is red on the day it lands teaches the next reader that red is normal
# here. `ops/` carries no model call and is not walked; add it the day it does.
PINNED_TREES = ("backend", "ticketing")


def _python_files(tree: str) -> list[Path]:
    return sorted(
        p for p in (REPO_ROOT / tree).rglob("*.py")
        if "__pycache__" not in p.parts and "migrations" not in p.parts
    )


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """id() of every string node that is a module/class/function docstring — documentation."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                if isinstance(body[0].value.value, str):
                    out.add(id(body[0].value))
    return out


def test_no_model_name_is_written_outside_the_registry():
    """
    **T-11-d / T-17-c (backend half).** A model name in a call site is how the indicator-4 claim
    decays: the next feature adds one, nothing fails, and nobody learns until a DPG reviewer
    greps. It is also how the same product ended up with four copies of one ternary.

    Comments and docstrings are exempt — they are documentation, and documentation that names the
    current default is useful. Executable string literals are not.
    """
    offenders: list[str] = []
    for tree_name in PINNED_TREES:
        for path in _python_files(tree_name):
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel == MODEL_REGISTRY:
                continue
            tree = ast.parse(path.read_text(), filename=str(path))
            docstrings = _docstring_nodes(tree)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and id(node) not in docstrings
                    and MODEL_LITERAL.search(node.value)
                ):
                    offenders.append(f"{rel}:{node.lineno} → {node.value[:60]!r}")

    assert not offenders, (
        "Model names must be declared once, in backend/config/llm_config.py, and resolved with "
        "model_for(\"<task>\"). Found:\n  " + "\n  ".join(offenders)
    )


def test_the_openai_client_is_constructed_in_one_place_per_surface():
    """
    **T-11-d.** Two factories is the design (two surfaces, two lifecycles). Three is drift, and
    the third one always carries its own timeout and its own key handling — which is precisely
    what the classification shadow client did until DPG-11 deleted it.
    """
    offenders: list[str] = []
    for tree_name in PINNED_TREES:
        for path in _python_files(tree_name):
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel in CLIENT_FACTORIES:
                continue
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    name = getattr(func, "id", None) or getattr(func, "attr", None)
                    if name in ("OpenAI", "AsyncOpenAI"):
                        offenders.append(f"{rel}:{node.lineno}")

    assert not offenders, (
        "OpenAI clients are constructed only by the two factories "
        f"({', '.join(sorted(CLIENT_FACTORIES))}). Found: {offenders}"
    )

def test_the_seah_model_ternary_exists_in_exactly_one_place():
    """
    **T-17-c.** `findings_task(is_seah)` is the only SEAH model selection in the repository.

    ⚠ This is the pin with the most history behind it. That ternary had been written out **four**
    times before DPG-17: in the ticketing client, in a log line, in `resolved_summary_builder` —
    whose copy was written into a **persisted provenance field**, so drift there publishes a model
    name that never ran — and once as `_llm._MODEL_SEAH if ticket.is_seah else _llm._MODEL_STANDARD`,
    reaching into the client module's privates. That last one is why this test does not stop at
    grepping for `gpt-`: **the fourth copy contained no model name at all.**
    """
    offenders: list[str] = []
    for tree_name in PINNED_TREES:
        for path in _python_files(tree_name):
            rel = path.relative_to(REPO_ROOT).as_posix()
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                # a) any reference to the retired private model constants, however it is reached
                if isinstance(node, ast.Name) and node.id in ("_MODEL_SEAH", "_MODEL_STANDARD"):
                    offenders.append(f"{rel}:{node.lineno} → {node.id}")
                elif isinstance(node, ast.Attribute) and node.attr in ("_MODEL_SEAH", "_MODEL_STANDARD"):
                    offenders.append(f"{rel}:{node.lineno} → .{node.attr}")
                # b) an is_seah ternary picking between two **model-looking** literals.
                #    ⚠ Deliberately narrow: `is_seah` ternaries are ordinary in this codebase —
                #    workflow keys, labels, queue names — and flagging all of them would make this
                #    pin noise, which is how a pin gets deleted. Only a model name is the concern.
                elif isinstance(node, ast.IfExp) and rel != MODEL_REGISTRY:
                    if "is_seah" in ast.dump(node.test).lower() or "seah" in ast.dump(node.test).lower():
                        branches = [node.body, node.orelse]
                        if all(
                            isinstance(b, ast.Constant) and isinstance(b.value, str) for b in branches
                        ) and any(MODEL_LITERAL.search(b.value) for b in branches):
                            offenders.append(f"{rel}:{node.lineno} → is_seah ternary picking a model")

    assert not offenders, (
        "The SEAH model choice is findings_task(is_seah) in backend/config/llm_config.py, and "
        "nothing else. Found:\n  " + "\n  ".join(offenders)
    )
