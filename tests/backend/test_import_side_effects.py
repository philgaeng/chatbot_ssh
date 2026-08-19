# SPDX-License-Identifier: Apache-2.0

"""
Importing a module must not write to the source tree — D-47.

⭐ **The bug this generalises from.** `backend/task_queue/config.py` ended with a bare
`update_shell_config()` at module scope, which wrote `backend/scripts/task_queue/config.sh` — a
file **tracked in git** — from whatever environment happened to be importing it. Inside the compose
stack that wrote `REDIS_HOST="redis"`; on the host, `"localhost"`.

The damage was not runtime. It was that **the working tree went dirty on its own** after every
containerised test run, and the committed value recorded whichever environment imported last. Its
entire git history is those two strings alternating, carried into three unrelated commits in one
sprint — including one this session that had to be pulled back out of a CI fix.

It was safe to delete outright rather than redirect: nothing sourced the file. Its consumers, the
legacy systemd/shell runtime scripts, went in `28508aec` when the stack moved to Docker, and the
generator and its output were left behind.

**This test does not pin that one deletion** — a test for "the function is gone" would be satisfied
by renaming it. It pins the property that made it a bug: **importing does not touch the disk.**
That catches the next one, wherever it is written.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Where source lives. Anything a test writes here is a defect by definition — build artefacts and
# caches belong outside the tree or in .gitignore, and __pycache__ is the one sanctioned exception.
WATCHED = ("backend", "ticketing", "scripts", "channels/shared")

# Modules whose import is known to be load-bearing at process start. Add to this list rather than
# widening the assertion — the point is that each one is a deliberate choice someone made.
IMPORTED_AT_STARTUP = [
    "backend.task_queue.config",
    "backend.config.llm_config",
    "backend.services.LLM_services",
]


def _snapshot() -> dict[str, tuple[int, int]]:
    """(size, mtime_ns) for every source file under the watched roots."""
    out: dict[str, tuple[int, int]] = {}
    for root in WATCHED:
        base = REPO_ROOT / root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            st = path.stat()
            out[str(path.relative_to(REPO_ROOT))] = (st.st_size, st.st_mtime_ns)
    return out


@pytest.mark.parametrize("module", IMPORTED_AT_STARTUP)
def test_importing_a_module_writes_nothing_to_the_source_tree(module):
    """⭐ Run in a **subprocess**, so this is a genuinely fresh import.

    In-process it would prove nothing: pytest has already imported most of these, and a
    module-scope write only happens once.
    """
    before = _snapshot()

    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"{module} failed to import:\n{result.stderr[-2000:]}"

    after = _snapshot()

    created = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(p for p in set(before) & set(after) if before[p] != after[p])

    assert not (created or removed or changed), (
        f"importing {module} touched the source tree — that is D-47's defect, whatever it writes.\n"
        f"  created: {created}\n  removed: {removed}\n  changed: {changed}\n"
        "Generate to an untracked path (and .gitignore it), or write only when explicitly asked."
    )


def test_the_generated_shell_config_is_gone_and_stays_gone():
    """The specific artefact, because a re-introduction would most likely restore the same path.

    ⚠ Asserted as *absence*, which is a weak shape of test — it passes for any reason the file is
    missing. It is here to make the intent legible at the path itself, not to carry the weight;
    the test above is what actually holds the property.
    """
    assert not (REPO_ROOT / "backend" / "scripts" / "task_queue" / "config.sh").exists(), (
        "backend/scripts/task_queue/config.sh is back. Nothing sourced it — its consumers went "
        "with the legacy shell runtime in 28508aec — and it was rewritten on every import."
    )
