"""T3-01 — every utterance key a call site passes must actually resolve.

This walks the **call sites**, not the mapping dict. That asymmetry is the whole point:
`test_seah_utterance_integrity.py` (H2-08) walks `UTTERANCE_MAPPING` and asserts every
entry it finds is well-formed — so it can only see keys that *exist*. The T3-01 bug class
is the opposite shape: a call site derives a key that exists nowhere, and
`get_utterance_base` raises `ValueError` at runtime. No dict walk can catch that.

Two lookup implementations exist; only one is in scope here (resolved by MRO, never by
grep — `ValidateFormOtp` has multiple bases and the leftmost wins):

  * `ActionHelpersMixin.get_utterance` (base_mixins.py) — keys off `self.name()`, already
    explicit, serves 196 of the 200 call sites. Not in scope.
  * `BaseFormValidationAction.get_utterance` (base_classes.py) — the 4 sites T3-01 fixes.

`BaseFormValidationAction.get_buttons` was deleted by T3-01: AST+MRO showed 0 of the 200
call sites reached it. If someone re-adds an introspecting `get_buttons`, extend
`_METHODS_IN_SCOPE` rather than letting it re-seed the bug class silently.
"""
import ast
from pathlib import Path

import pytest

from backend.actions.utils.utterance_mapping_rasa import (
    UTTERANCE_MAPPING,
    get_utterance_base,
)

ACTIONS_ROOT = Path(__file__).resolve().parents[2] / "backend" / "actions"

# Which base class provides which lookup. Only the introspecting one is in scope.
_INTROSPECTION_BASE = "BaseFormValidationAction"
_EXPLICIT_BASE = "ActionHelpersMixin"
_METHODS_IN_SCOPE = {"get_utterance"}


def _parse_actions_tree():
    """Return (classes, call_sites) for every .py under backend/actions/.

    classes:    name -> list of base names (source order; leftmost wins under Python MRO)
    call_sites: dicts describing each `self.get_utterance(...)` / `self.get_buttons(...)`
    """
    classes = {}
    call_sites = []

    for path in sorted(ACTIONS_ROOT.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - would fail the import suite first
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            classes[node.name] = [
                b.id if isinstance(b, ast.Name)
                else b.attr if isinstance(b, ast.Attribute)
                else "?"
                for b in node.bases
            ]
            # Walk each method so we can recover the *enclosing function name* — that is
            # exactly what the introspection derives via f_back.f_code.co_name, so it is
            # the correct fallback key for a call site that passes no explicit key=.
            for fn in ast.walk(node):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for call in ast.walk(fn):
                    if not (
                        isinstance(call, ast.Call)
                        and isinstance(call.func, ast.Attribute)
                        and isinstance(call.func.value, ast.Name)
                        and call.func.value.id == "self"
                        and call.func.attr in ("get_utterance", "get_buttons")
                    ):
                        continue
                    call_sites.append(
                        {
                            "path": path,
                            "lineno": call.lineno,
                            "cls": node.name,
                            "method": call.func.attr,
                            "enclosing_fn": fn.name,
                            "explicit_key": _explicit_key(call),
                            "index": _index_arg(call),
                            # file_name derives from the module name (base_mixins.py:63).
                            "file_name": path.stem,
                        }
                    )
    return classes, call_sites


def _explicit_key(call: ast.Call):
    """The `key="..."` keyword, if the call passes one."""
    for kw in call.keywords:
        if kw.arg == "key" and isinstance(kw.value, ast.Constant):
            return kw.value.value
    return None


def _index_arg(call: ast.Call) -> int:
    """The utterance index: first positional, or `utterance_index=`, else the default 1."""
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, int):
        return call.args[0].value
    for kw in call.keywords:
        if kw.arg in ("utterance_index", "button_index") and isinstance(kw.value, ast.Constant):
            return kw.value.value
    return 1


def _resolve_lookup(cls: str, classes: dict, _seen=None):
    """Which lookup implementation this class inherits, by MRO (leftmost base wins)."""
    _seen = _seen or set()
    if cls in _seen or cls not in classes:
        return None
    _seen.add(cls)
    bases = classes[cls]
    for base in bases:
        if base == _INTROSPECTION_BASE:
            return "introspection"
        if base == _EXPLICIT_BASE:
            return "explicit"
    for base in bases:
        found = _resolve_lookup(base, classes, _seen)
        if found:
            return found
    return None


def _in_scope_call_sites():
    classes, call_sites = _parse_actions_tree()
    rows = []
    for site in call_sites:
        if site["method"] not in _METHODS_IN_SCOPE:
            continue
        if _resolve_lookup(site["cls"], classes) != "introspection":
            continue
        # The key the lookup will actually use: the explicit one if given, else the
        # enclosing function's name (what the introspection would derive).
        site["key"] = site["explicit_key"] or site["enclosing_fn"]
        rows.append(site)
    return rows


_SITES = _in_scope_call_sites()
_IDS = [f"{s['file_name']}:{s['lineno']}:{s['key']}" for s in _SITES]


def test_call_sites_were_found():
    """Guard the guard: an AST/MRO change that silently finds nothing must fail loudly."""
    assert _SITES, (
        "No BaseFormValidationAction get_utterance call sites found — the resolver is "
        "broken, or the lookup moved. This test would otherwise vacuously pass."
    )


@pytest.mark.parametrize("site", _SITES, ids=_IDS)
def test_call_site_key_resolves(site):
    """The key each call site passes must resolve in EN and NE.

    This is the assertion that goes red on pre-T3-01 code for 3 of the 4 sites.
    """
    for lang in ("en", "ne"):
        try:
            value = get_utterance_base(site["file_name"], site["key"], site["index"], lang)
        except ValueError as exc:  # pragma: no cover - the failure path is the point
            pytest.fail(
                f"{site['path'].name}:{site['lineno']} ({site['cls']}) passes key "
                f"'{site['key']}' (index {site['index']}), which does not resolve for "
                f"'{lang}'. A user reaching this branch gets a ValueError, not a message. "
                f"Underlying: {exc}"
            )
        assert isinstance(value, str) and value.strip(), (
            f"{site['path'].name}:{site['lineno']}: key '{site['key']}' resolves to an "
            f"empty '{lang}' utterance"
        )


@pytest.mark.parametrize("site", _SITES, ids=_IDS)
def test_call_site_ne_is_translated(site):
    """NE must not be a copy of EN (the untranslated-placeholder smell)."""
    en = get_utterance_base(site["file_name"], site["key"], site["index"], "en")
    ne = get_utterance_base(site["file_name"], site["key"], site["index"], "ne")
    assert ne.strip() != en.strip(), (
        f"{site['path'].name}:{site['lineno']}: key '{site['key']}' has NE == EN — "
        f"untranslated placeholder"
    )


@pytest.mark.parametrize("site", _SITES, ids=_IDS)
def test_call_site_passes_an_explicit_key(site):
    """No call site may rely on stack introspection to derive its key.

    Once the `f_back` derivation is gone (T3-01 step 5) `key` is required, so this is
    what keeps the answer to "does this lookup resolve?" a *static* question. That it was
    ever unanswerable statically is the reason this ticket existed.
    """
    assert site["explicit_key"] is not None, (
        f"{site['path'].name}:{site['lineno']} ({site['cls']}.{site['enclosing_fn']}) "
        f"calls get_utterance() without an explicit key="
    )


def test_introspection_sites_are_the_known_four():
    """Pins the AST+MRO census (4 introspection / 196 explicit / 0 unresolved).

    If this count moves, the T3-01 analysis needs redoing rather than quietly widening.
    """
    assert len(_SITES) == 4, (
        f"expected 4 BaseFormValidationAction.get_utterance call sites, found "
        f"{len(_SITES)}: {_IDS}"
    )


def test_no_introspecting_get_buttons_call_sites():
    """`BaseFormValidationAction.get_buttons` was deleted as dead code (0 callers).

    All 76 get_buttons calls resolve through ActionHelpersMixin's explicit path. If this
    fails, someone re-introduced the introspecting variant *and* a caller for it.
    """
    classes, call_sites = _parse_actions_tree()
    offenders = [
        f"{s['file_name']}:{s['lineno']} ({s['cls']})"
        for s in call_sites
        if s["method"] == "get_buttons"
        and _resolve_lookup(s["cls"], classes) == "introspection"
    ]
    assert not offenders, f"introspecting get_buttons call sites reappeared: {offenders}"
