# SPDX-License-Identifier: Apache-2.0
"""
`GRM-099` — the migration step runs the SAME image the deploy just pulled, or refuses.

**The defect, found on the first real pulling deploy (2026-09-14).** `REMOTE_DEPLOY_CORE` prefixes
`up -d` with `$(REMOTE_IMAGE_ENV)` but **not** its three `compose run --rm backend … alembic
upgrade head` lines. So on a pulling deploy those resolved `IMAGE_TAG=local`, found no such image
in the registry, and compose **fell back to `build:`** — a 350 MB backend build on the host, in
the middle of a deploy whose whole promise is that it builds nothing there.

⛔ **Both success signals lied.** `make` exited 0 and `aws-deploy OK` printed. The only trace was
one `not found` line in a long log. That is why this is a test and not a note: nothing at runtime
reports it, and it was only seen because someone read the log.

**Two consequences, the second worse than the first:**

1. It is `GRM-008`'s OOM trigger again. Swap added an hour earlier absorbed 486 MB of it.
2. The migrations ran the **host checkout's** code instead of the image's. Harmless on that deploy
   only because the two trees happened to be identical. A rollback — `IMAGE_TAG=<older>` — would
   have migrated with `integration/stage` HEAD's code against containers running older code.

⚠ **What this does not check:** that the migrations succeed, or that a rollback across a migration
boundary is safe. The second is not — alembic cannot downgrade from a revision the older image does
not know — and that is recorded as its own item rather than papered over here.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TAG = "abc1234"


def _dry_run(target: str, *extra: str) -> str:
    return subprocess.run(
        ["make", "-n", target, *extra], cwd=REPO_ROOT, capture_output=True, text=True,
    ).stdout


@pytest.fixture(scope="module")
def pulling() -> str:
    out = _dry_run("aws-deploy", f"IMAGE_TAG={TAG}")
    assert out.strip(), "make -n aws-deploy produced nothing — the target or the Makefile moved"
    return out


def _segments(cmd: str) -> list[str]:
    """Split one long remote command into its `&&`-chained steps."""
    return [s.strip() for s in cmd.split(" && ")]


def test_every_migration_runs_the_pulled_image(pulling: str) -> None:
    """The regression itself. Each alembic invocation must carry the same IMAGE_TAG as `up -d`."""
    migrations = [s for s in _segments(pulling) if "alembic" in s and " run " in s]
    assert len(migrations) == 3, (
        f"expected the three migration streams (ticketing, public, ops), found {len(migrations)}"
    )
    untagged = [m[-90:] for m in migrations if f"IMAGE_TAG={TAG}" not in m]
    assert not untagged, (
        "a migration step does not receive IMAGE_TAG, so it resolves `app:local`, cannot pull it, "
        f"and compose silently BUILDS it on the host (GRM-099): {untagged}"
    )


def test_the_migration_image_is_asserted_present_before_it_can_be_built(pulling: str) -> None:
    """⭐ The half that turns a silent build into a loud refusal.

    `docker compose run` has **no `--no-build` flag** — only `--build` and `--pull` — so compose's
    fall-back-to-build cannot be switched off from the command line. The only reliable guard is to
    resolve the exact image `run` will use and refuse if it is not already on the host.
    """
    assert "config --images backend" in pulling, (
        "no pre-migration check resolves the backend image; a missing tag would build silently"
    )
    assert "docker image inspect" in pulling, "the resolved migration image is never checked"
    guard_at = pulling.index("config --images backend")
    first_migration = pulling.index("alembic")
    assert guard_at < first_migration, "the image guard runs AFTER a migration has already started"


def test_the_guard_resolves_with_the_same_image_env(pulling: str) -> None:
    """A guard that resolves the image WITHOUT IMAGE_TAG would check `app:local` and wave through
    exactly the case it exists to catch."""
    guard = next(s for s in _segments(pulling) if "config --images backend" in s)
    assert f"IMAGE_TAG={TAG}" in guard, (
        "the image guard resolves without IMAGE_TAG, so it would inspect app:local — the wrong image"
    )


def test_the_guard_does_not_break_the_and_chain(pulling: str) -> None:
    """`set -e` does NOT fire for a failed command inside an `a && b` list — the chain itself is the
    control. A guard spliced in with a bare `;` would let a failed `up -d` fall through to the
    migrations. So the guard must be one brace-grouped command in the chain."""
    assert re.search(r"&& \{ MIG_IMG=", pulling), (
        "the migration-image guard is not brace-grouped, so a `;` inside it breaks the && chain "
        "and a failed earlier step could fall through to the migrations"
    )


# ── All three copies, not just the one the deploy happened to use ──────────────

@pytest.mark.parametrize(
    "target, streams",
    [("aws-deploy", 3), ("aws-deploy-full", 3), ("aws-deploy-ops", 1)],
)
def test_every_deploy_path_migrates_on_the_deployed_image(target: str, streams: int) -> None:
    """⚠ The defect was not in one macro — it was in THREE: REMOTE_DEPLOY_CORE, REMOTE_DEPLOY_FULL
    and REMOTE_DEPLOY_OPS, which between them back all six deploy targets on staging and
    production. Fixing the copy the failing deploy used left the other two broken, and a test that
    only exercised `aws-deploy` would have gone green over them. Each path is checked here."""
    out = _dry_run(target, f"IMAGE_TAG={TAG}")
    assert out.strip(), f"make -n {target} produced nothing"
    migrations = [s for s in _segments(out) if "alembic" in s and " run " in s]
    assert len(migrations) == streams, f"{target}: expected {streams} migration(s), found {len(migrations)}"
    assert all(f"IMAGE_TAG={TAG}" in m for m in migrations), (
        f"{target}: a migration does not receive IMAGE_TAG and would build on the host (GRM-099)"
    )
    assert out.index("config --images backend") < out.index("alembic"), (
        f"{target}: the migration-image guard does not run before the first migration"
    )


def test_the_remote_migration_command_exists_exactly_once() -> None:
    """The structural half. The defect survived because the same block was pasted three times, so a
    fix to one copy could never reach the others. This pins that there is ONE definition — the
    `REMOTE_MIGRATE_ONE` body — and that every deploy goes through it."""
    text = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    remote = [l for l in text.splitlines() if "$(REMOTE_COMPOSE) run" in l and "alembic" in l]
    assert len(remote) == 1, (
        f"found {len(remote)} remote alembic invocations; there must be exactly one "
        f"(REMOTE_MIGRATE_ONE), or copies can drift apart again: {remote}"
    )
    assert "$(REMOTE_IMAGE_ENV)" in remote[0], "the single remote migration line lost its image env"
