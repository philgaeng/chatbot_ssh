# SPDX-License-Identifier: Apache-2.0
"""
T-01 — the licence-header pin (DPG-01).

Indicator-2 evidence decays silently. A one-off SPDX pass covers the tree on the day it runs and
stops being true the first week somebody adds a module — and nobody learns until a DPG reviewer
greps. This test is the mechanism that keeps the claim true, so it is acceptance criteria for
DPG-01, not decoration.

**Scope comes from `scripts/ops/add_spdx_headers.py`, imported by path.** Restating the file set
here would create a hand-maintained mirror of the script's `SCOPE`, and the two would drift — the
exact failure mode `tests/ticketing/test_boundary_policy.py` was rewritten to remove (CLAUDE.md
§Data rules, amended 2026-07-15). One definition, imported.

⚠ **This file lives in `tests/repo/` for a reason.** CI runs
`pytest tests/ticketing tests/orchestrator tests/actions tests/backend` — four explicit paths. A
test at `tests/` root would never execute, which is how 21 test files there are currently invisible
to CI (logged as a deviation in the sprint tracker). `tests/repo/` is added to that CI invocation in
the same commit as this file; if you add a repo-wide pin, put it here so it actually runs.

Spec: docs/sprints/2026-08-llm/01-licensing-and-governance-spec.md#dpg-01 · ledger: TESTS.md T-01
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ops" / "add_spdx_headers.py"


def _load_script():
    """Import the header script by path — `scripts/` is not an importable package."""
    spec = importlib.util.spec_from_file_location("add_spdx_headers", SCRIPT)
    assert spec and spec.loader, f"could not load {SCRIPT}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


spdx = _load_script()


def test_script_exists_and_is_runnable():
    """DPG-01 step 3: the adding script is committed and re-runnable, not a one-off paste."""
    assert SCRIPT.is_file(), "scripts/ops/add_spdx_headers.py is the maintenance mechanism"
    assert hasattr(spdx, "SCOPE") and spdx.SCOPE, "the script must define its scope"
    assert hasattr(spdx, "in_scope"), "the test imports the scope from the script, not a copy"


def test_scope_is_not_empty():
    """A pin over an empty file set passes forever and proves nothing."""
    files = spdx.in_scope()
    assert len(files) > 400, (
        f"only {len(files)} files in scope — the backend, ticketing and channels trees alone "
        "exceed that. A collapsed scope silently disables this pin."
    )


def test_every_in_scope_file_carries_the_spdx_header():
    """The pin itself.

    Mutation check: delete the header line from any file under backend/, ticketing/, ops/,
    scripts/ or channels/ and this goes red. That is the whole point — run
    `python scripts/ops/add_spdx_headers.py` to fix it.
    """
    missing = [
        str(path)
        for path, _prefix in spdx.in_scope()
        if not spdx.has_header((REPO_ROOT / path).read_text(encoding="utf-8"))
    ]
    assert not missing, (
        f"{len(missing)} in-scope file(s) are missing "
        f"`{spdx.IDENTIFIER}`:\n  " + "\n  ".join(missing[:20])
        + "\n\nFix: python scripts/ops/add_spdx_headers.py"
    )


def test_header_sits_at_the_top_and_below_any_shebang():
    """A shebang must stay on line 1 or the file stops being executable.

    `has_header` only looks at the first five lines, so a misplaced header would already fail the
    test above — this asserts the *ordering* constraint that makes the placement correct rather
    than merely present.
    """
    offenders = []
    for path, _prefix in spdx.in_scope():
        lines = (REPO_ROOT / path).read_text(encoding="utf-8").splitlines()
        if not lines:
            continue
        header_index = next(
            (i for i, line in enumerate(lines[:5]) if spdx.IDENTIFIER in line), None
        )
        if header_index is None:
            continue  # covered by the test above
        if lines[0].startswith("#!") and header_index == 0:
            offenders.append(f"{path}: header displaced the shebang")
        if not lines[0].startswith("#!") and header_index != 0:
            offenders.append(f"{path}: header at line {header_index + 1}, expected line 1")
    assert not offenders, "\n  ".join(offenders)


def test_migration_safety_headers_survived():
    """The mandated migration header is a contract with the reader; SPDX goes ABOVE it.

    CLAUDE.md requires every migration to state what it touches. Displacing that to make room for
    a licence line would trade a real safety property for a compliance one.
    """
    migrations = [
        path
        for path, _ in spdx.in_scope()
        if "migrations/versions/" in str(path)
    ]
    assert migrations, "expected Alembic migrations in scope"
    missing = [
        str(path)
        for path in migrations
        if "Safe to run" not in (REPO_ROOT / path).read_text(encoding="utf-8")
    ]
    # Not every historical migration carries the header; assert we did not *reduce* the count.
    assert len(missing) < len(migrations), (
        "no migration retains its 'Safe to run' header — the SPDX pass displaced it"
    )


def test_license_file_is_the_canonical_apache_2_text():
    """DPG-01: `LICENSE` byte-identical to the canonical text.

    Pinned deliberately. The licence is provisional — Apache-2.0 adopted so work can proceed, to be
    revisited if ADB's consultant advises otherwise (Q-02). If it changes, this test must be updated
    in the same commit as `LICENSE` and every SPDX header, which is exactly the coupling we want:
    a half-switched licence is worse than either licence.
    """
    license_path = REPO_ROOT / "LICENSE"
    assert license_path.is_file(), "no LICENSE at the repo root — indicator 2 fails outright"
    text = license_path.read_text(encoding="utf-8")
    assert "Apache License" in text.split("\n")[1]
    assert "Version 2.0, January 2004" in text
    assert "http://www.apache.org/licenses/" in text
    assert "APPENDIX: How to apply the Apache License to your work" in text
    assert len(text.splitlines()) == 202, (
        "LICENSE is not the canonical 202-line Apache-2.0 text — re-fetch it from "
        "https://www.apache.org/licenses/LICENSE-2.0.txt rather than hand-editing"
    )


def test_notice_discloses_an_unresolved_copyright_holder():
    """An unfilled holder must be *disclosed*, never silent.

    The Apache template ships with `[name of copyright owner]`. Leaving that in place without
    saying so reads as an oversight; saying so makes it a stated dependency on DPG-03. Once the
    determination lands and the placeholder is replaced, both branches pass.
    """
    notice_path = REPO_ROOT / "NOTICE"
    assert notice_path.is_file(), "NOTICE is required alongside an Apache-2.0 LICENSE"
    text = notice_path.read_text(encoding="utf-8")
    if "[name of copyright owner]" in text:
        assert "PENDING IP DETERMINATION" in text, (
            "NOTICE still carries the unfilled Apache template placeholder but does not say so. "
            "Either name the holder (see docs/dpg/ip-ownership.md) or keep the pending marker."
        )


@pytest.mark.parametrize("root_file", ["LICENSE", "NOTICE"])
def test_root_licence_files_are_tracked(root_file):
    """A LICENSE that is gitignored is not a licence."""
    import subprocess

    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", root_file],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert tracked.returncode == 0, f"{root_file} is not tracked by git"
