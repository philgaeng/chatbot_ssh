# SPDX-License-Identifier: Apache-2.0
"""
QA-02 scope 4 — the guard that keeps the bypass UI image out of a real environment.

The officer UI inlines `NEXT_PUBLIC_AUTH_MODE` at build time, so one commit produces two
images: `ui:<sha>` (Keycloak) and `ui:<sha>-bypass`, which has **no login at all** — it reads
an identity from a cookie. Serving the second from staging or production would make every
visitor a seeded officer.

This pins the guard itself: that it exists, that CI runs it, and that it can actually go red.
A guard nobody runs is decoration, and this repository has been bitten by that twice.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARD = REPO_ROOT / "scripts" / "ci" / "check_no_bypass_image.sh"
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(GUARD), *args], cwd=REPO_ROOT, capture_output=True, text=True
    )


def test_the_guard_exists_and_is_executable():
    assert GUARD.is_file(), "the bypass guard is missing"


def test_ci_actually_runs_it():
    """⚠ The half that matters. A guard CI does not invoke protects nothing."""
    assert "check_no_bypass_image.sh" in CI.read_text(encoding="utf-8"), (
        "ci.yml does not run the bypass guard — it is decoration until it does"
    )


def test_the_tree_is_clean_today():
    assert _run().returncode == 0, "a deployable compose file references a -bypass image"


def test_it_fails_on_a_bypass_image_reference(tmp_path: Path):
    """Mutation check in the acceptance's own words: 'fails when deliberately given a bad file'."""
    bad = tmp_path / "bad.yml"
    bad.write_text("services:\n  grm_ui:\n    image: ghcr.io/x/ui:abc-bypass\n")
    result = _run(str(bad))
    assert result.returncode == 1
    assert "bypass UI image" in result.stdout


def test_it_fails_on_a_bypass_UI_IMAGE_TAG(tmp_path: Path):
    """⭐ The case a naive guard misses.

    After QA-02 the variant is selected by `UI_IMAGE_TAG`, not by the `image:` line — the
    `image:` line is a variable expression that looks identical either way. A guard that
    grepped only `image:` would pass while the stack pulled the bypass build.
    """
    bad = tmp_path / "bad.yml"
    bad.write_text("services:\n  grm_ui:\n    environment:\n      UI_IMAGE_TAG: abc1234-bypass\n")
    result = _run(str(bad))
    assert result.returncode == 1
    assert "UI_IMAGE_TAG" in result.stdout


@pytest.mark.parametrize("good", [
    "services:\n  grm_ui:\n    image: ghcr.io/x/ui:abc1234\n",
    "services:\n  grm_ui:\n    environment:\n      UI_IMAGE_TAG: abc1234\n",
])
def test_it_does_not_cry_wolf(tmp_path: Path, good: str):
    """A guard that fires on a clean file gets disabled, which is worse than not having one."""
    ok = tmp_path / "ok.yml"
    ok.write_text(good)
    assert _run(str(ok)).returncode == 0
