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


def _tracked_shell_scripts() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "--", "*.sh"], cwd=REPO_ROOT, capture_output=True, text=True
    ).stdout
    return [l for l in out.splitlines() if l.strip()]


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


def test_every_script_with_a_shebang_is_executable() -> None:
    """`GRM-139` — the test above scoped itself to Make targets, and the gap was cron.

    ⚠ **Measured 2026-09-16 on the DOR production host**, by being the first person to try:
    `sudo scripts/ops/backup_db.sh /opt/grms` answered `command not found`. The file was mode
    100644, as it had been since it was added on 2026-06-23. `15_host_hardening.md` installs it as
    `15 2 * * *` — so **the nightly backup had never executed, on any host**, and neither had the
    weekly `restore_drill.sh` nor the five-minute `host_watchdog.sh`. `GRM-114` had recorded
    production's backups as *unverified*; they were absent.

    ⭐ **The scope was the defect.** `GRM-094` fixed exactly the scripts whose failure someone
    would see immediately — a Make target dying in front of you — and left the ones that fail at
    02:15 with nobody watching. A script run by cron has no one to report `Permission denied` to.

    So the rule is not "what a Make target runs" but **what declares itself runnable**: a shebang
    is that declaration, and git's one permission bit should agree with it.
    """
    wrong = []
    for rel in _tracked_shell_scripts():
        if not (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace").startswith("#!"):
            continue
        mode = _git_mode(rel)
        if mode and mode != "100755":
            wrong.append(f"{rel} is {mode}")

    assert not wrong, (
        "These scripts start with a shebang — they declare themselves runnable — but git records "
        f"them as non-executable: {wrong}. Anything invoking them by path (cron, a runbook, a "
        "deploy host) gets `Permission denied`, and cron has nobody to tell. "
        "Fix with: git update-index --chmod=+x <path>"
    )
