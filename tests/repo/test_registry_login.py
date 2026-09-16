# SPDX-License-Identifier: Apache-2.0
"""
`GRM-093` — a pulling deploy authenticates to the registry before it pulls.

**The defect this pins.** `docs/deployment/03_operations.md` §6a says *"Staging pulls images that
CI already built"*, and `make aws-deploy` sets `DEPLOY_BUILD=0` accordingly. But `D-010` made the
repository private on 2026-09-04, so its GHCR packages are private — and `REMOTE_ACQUIRE_IMAGES`
went straight to `compose pull` with no `docker login` anywhere in the Makefile. The documented
capability could not work; it would fail on the host with `denied`.

⚠ **Why a test and not just the fix.** The failure is invisible from here: it needs a private
registry, a remote host, and a deploy window. Nothing in CI pulls a private package, so nothing
in CI would ever notice the login being dropped again — which is exactly the shape of defect this
repository keeps finding (a guard that cannot fail is decoration, and so is a step nobody checks).
`make -n` is the one place the whole remote command line is visible without running it.

⚠ **What this does NOT check:** that the credential is correct, that the host can reach
`ghcr.io`, or that the pull succeeds. Those need the host (`A-11`, and the unanswered
`curl -sI https://ghcr.io/v2/`). This checks the *shape* of the command, which is the half that
can regress silently in a refactor.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# `docker compose <many flags> pull <services>` — the flags are why a literal "compose pull"
# match is wrong.
PULL_RE = re.compile(r"docker compose[^;|&]*\spull\s")


def _dry_run(target: str, *extra: str) -> str:
    """Expand a Make target without running it."""
    proc = subprocess.run(
        ["make", "-n", target, *extra],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    # `make -n` can exit non-zero on an unrelated recipe; the expansion is what we read.
    return proc.stdout


@pytest.fixture(scope="module")
def aws_deploy() -> str:
    out = _dry_run("aws-deploy", "IMAGE_TAG=abc1234")
    assert out.strip(), "make -n aws-deploy produced nothing — the target or the Makefile moved"
    return out


def test_a_pulling_deploy_logs_in_before_it_pulls(aws_deploy: str) -> None:
    """The regression itself: no login, and every pull of a private package is `denied`."""
    assert "docker login" in aws_deploy, (
        "aws-deploy is a pulling deploy (DEPLOY_BUILD=0) against a PRIVATE registry and never "
        "authenticates. Every `compose pull` will fail with `denied`. See GRM-093 / A-11."
    )
    login_at = aws_deploy.index("docker login")
    pull = PULL_RE.search(aws_deploy)
    # ⚠ Not the literal "compose pull": the expansion is
    # `docker compose --env-file env.local -f … --profile auth pull <services>`, so a contiguous
    # substring never matches and the assertion would pass whatever the Makefile did. Found by
    # this very test failing open on the first run.
    assert pull, "aws-deploy does not pull at all — the target changed shape"
    assert login_at < pull.start(), (
        "docker login appears AFTER the pull — the pull runs unauthenticated and fails first"
    )


def test_the_token_is_never_passed_as_an_argument(aws_deploy: str) -> None:
    """A token in argv is readable by every process on the host via `ps`, and lands in shell
    history and in any command log. `--password-stdin` is the only acceptable form."""
    assert "--password-stdin" in aws_deploy, "docker login must read the token from stdin"
    assert not re.search(r"docker login[^|&;]*(-p|--password)\s", aws_deploy), (
        "docker login is being given the token as an argument — use --password-stdin"
    )


def test_the_token_value_is_never_echoed(aws_deploy: str) -> None:
    """The deploy prints a lot. It must never print this."""
    for bad in ('echo "$GHCR_READ_TOKEN"', "echo $GHCR_READ_TOKEN", 'echo "$$GHCR_READ_TOKEN"'):
        assert bad not in aws_deploy, f"the deploy echoes the registry token: {bad!r}"


def test_login_is_skipped_when_no_token_is_configured(aws_deploy: str) -> None:
    """⭐ The half that keeps this from breaking everyone else.

    `make wsl-up`, a `DEPLOY_BUILD=1` deploy, and any host whose registry is public must all keep
    working with no token present. A login step that is unconditional turns a missing optional
    secret into a failed deploy — which is a worse outcome than the one being fixed.
    """
    assert "GHCR_READ_TOKEN" in aws_deploy, "the login must be conditional on the token existing"
    # The guard reads the token out of env.local and only logs in when it is non-empty.
    assert re.search(r'if \[ -n "\$\$?GHCR_READ_TOKEN" \]', aws_deploy), (
        "expected a non-empty guard around docker login so an absent token skips it cleanly"
    )


def test_the_build_path_is_selected_by_deploy_build_and_needs_no_registry() -> None:
    """`DEPLOY_BUILD=1` is the documented fallback for "the registry is unreachable or
    uncredentialed", so the login must sit on the *pull* side of that branch and nowhere else.

    ⚠ **This cannot be asserted by absence, and finding that out is the point.** `make -n` prints
    the whole recipe — both arms of the shell `if` — whichever value `DEPLOY_BUILD` has. A
    `assert "docker login" not in out` here passes or fails for reasons unrelated to the branch
    actually taken, so what is checked is the *selector* and the *nesting*.
    """
    out = _dry_run("aws-deploy", "IMAGE_TAG=abc1234", "DEPLOY_BUILD=1")
    assert out.strip(), "make -n aws-deploy DEPLOY_BUILD=1 produced nothing"

    # The condition is expanded by Make, so the chosen arm is visible in the text.
    assert 'if [ "1" = "1" ]' in out, (
        "DEPLOY_BUILD=1 no longer selects the build arm — REMOTE_ACQUIRE_IMAGES changed shape"
    )

    # And in the default (pulling) expansion, the login is inside the else arm, after the guard
    # that refuses a deploy with no IMAGE_TAG — never before it.
    pulling = _dry_run("aws-deploy", "IMAGE_TAG=abc1234")
    assert 'if [ "0" = "1" ]' in pulling, "aws-deploy no longer defaults to a pulling deploy"
    guard_at = pulling.index("is a pulling deploy (DEPLOY_BUILD=0) but IMAGE_TAG is")
    assert guard_at < pulling.index("docker login"), (
        "the registry login runs before the no-IMAGE_TAG guard — a deploy with no tag would "
        "authenticate and then refuse, which is work done for a run that cannot proceed"
    )
