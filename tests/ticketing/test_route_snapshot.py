"""Route-surface invariant (H2-02).

The URL surface of the API must not change when `tickets.py` is split into a
router package. This test dumps every (method, path) from the live app and
compares it to a committed snapshot taken *before* the refactor.

This backend's FastAPI keeps included routers as nested `_IncludedRouter`
objects rather than flattening them into `app.routes`, so we read the surface
from `app.openapi()["paths"]` (full, prefixed paths) — do NOT iterate
`app.routes` for this.

Regenerate the snapshot ONLY on an intentional, reviewed surface change:

    docker compose ... exec -T ticketing_api python -c "
    from ticketing.api.main import app
    schema = app.openapi()
    lines = set()
    for path, ops in schema['paths'].items():
        for m in ops:
            if m.lower() in ('parameters','summary','description'): continue
            lines.add(f'{m.upper()} {path}')
    print(chr(10).join(sorted(lines)))
    " > tests/ticketing/route_snapshot.txt
"""
import os

from ticketing.api.main import app

SNAPSHOT = os.path.join(os.path.dirname(__file__), "route_snapshot.txt")

_IGNORED_KEYS = {"parameters", "summary", "description"}


def _current_surface() -> list[str]:
    schema = app.openapi()
    lines: set[str] = set()
    for path, ops in schema.get("paths", {}).items():
        for method in ops:
            if method.lower() in _IGNORED_KEYS:
                continue
            lines.add(f"{method.upper()} {path}")
    return sorted(lines)


def test_route_surface_matches_snapshot() -> None:
    with open(SNAPSHOT, encoding="utf-8") as f:
        expected = sorted({ln.strip() for ln in f if ln.strip()})
    actual = _current_surface()
    missing = sorted(set(expected) - set(actual))
    added = sorted(set(actual) - set(expected))
    assert not missing and not added, (
        "Route surface drifted from the committed snapshot.\n"
        f"Removed: {missing}\n"
        f"Added:   {added}\n"
        "If this change is intentional, regenerate tests/ticketing/route_snapshot.txt "
        "(see this file's docstring)."
    )
