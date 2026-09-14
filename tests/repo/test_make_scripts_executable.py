# SPDX-License-Identifier: Apache-2.0
"""
`GRM-094` — every script a Make target runs directly is executable in git.

**The defect.** `make env-local` is documented in three places — the Makefile's own help,
`13_security.md` §5.2, and `18_sops_migration_handover.md` — and its recipe is a bare
`scripts/ops/gen_env_local.sh`. The file is mode **100644** in git, so on any fresh clone that
target dies with `Permission denied` before it does anything. Measured 2026-09-14 on the staging
deploy path, by a human following the runbook.

⭐ **The tell was already in the Makefile, one target away.** `aws_to_prod_db_sync` runs
`@chmod +x` on its script *before* invoking it — somebody hit exactly this, fixed it for the one
target in front of them, and left the cause in place. That workaround is why nobody noticed the
other two.

⚠ **Git tracks one permission bit and nothing else** (`100644` vs `100755`), so this is checked
against the index rather than the working tree: a local `chmod +x` makes the symptom vanish on
one machine and changes nothing for the next clone, the CI runner, or the deploy host — which is
precisely where it hurts.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = REPO_ROOT / "Makefile"

# A recipe line that runs a script directly: a leading TAB, an optional @ or ./, then the path.
DIRECT_INVOCATION = re.compile(r"^\t@?\s*(?:\./)?(scripts/[\w./-]+\.sh)\b", re.M)


def _git_mode(path: str) -> str | None:
    out = subprocess.run(
        ["git", "ls-files", "-s", "--", path],
        cwd=REPO_ROOT, capture_output=True, text=True,
    ).stdout.strip()
    return out.split()[0] if out else None


def test_every_directly_invoked_script_is_executable() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")
    invoked = sorted(set(DIRECT_INVOCATION.findall(text)))
    assert invoked, "found no directly-invoked scripts — the Makefile or this regex moved"

    not_executable = []
    for rel in invoked:
        mode = _git_mode(rel)
        if mode is None:
            continue  # not tracked; a missing script is a different test's problem
        if mode != "100755":
            not_executable.append(f"{rel} is {mode}")

    assert not not_executable, (
        "Make targets invoke these scripts directly, but git records them as non-executable, so "
        "the target fails with `Permission denied` on every fresh clone — including the deploy "
        f"host: {not_executable}. Fix with: git update-index --chmod=+x <path>"
    )
