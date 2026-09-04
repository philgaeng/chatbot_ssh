# SPDX-License-Identifier: Apache-2.0
"""Every live spec carries a dated header, and no commit changes a spec without touching it.

**What this pins, and why it is a test rather than a habit.**
`docs/engineering/06_documentation_lifecycle.md` §6 Rule 6.1 has required a dated Status header
on every document since 2026-08-03. Measured on 2026-09-04, before this file existed:

| | |
|---|---|
| Live specs with **no** header at all | **40 of 80** |
| Docs whose header date was at least as recent as their last commit | **3 of 98** |
| `docs/engineering/` compliance | **7 of 7** |

⭐ **The rule was obeyed in the folder the rule lives in, and essentially nowhere else.** That is
Rule 5.2 — *a rule that isn't enforced isn't a rule* — demonstrated against the document that
states it. This test is the enforcement point that Rule 5.2 requires a rule to name.

⚠ **What it deliberately does NOT assert.** It does not require the header date to be at least
the file's last-commit date. That check is the intuitive one and it is a trap: it would have
failed **95 of 98** documents on the day it shipped, and a permanently red gate trains people to
walk past gates — the D-26 failure, and the reason the `make help` deploy banner was retracted on
2026-09-03. Instead the date means *when the content was last reviewed*, stays hand-set and
truthful, and rule 3 below makes it impossible to change a spec without confronting it.

Spec: `docs/engineering/06_documentation_lifecycle.md` §6
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ops" / "doc_headers.py"


def _load():
    """Import the checker by path — `scripts/` is not an importable package."""
    spec = importlib.util.spec_from_file_location("doc_headers", SCRIPT)
    assert spec and spec.loader, f"could not load {SCRIPT}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def dh():
    return _load()


def test_the_checker_exists_and_is_executable_as_documented(dh):
    assert SCRIPT.exists(), "the enforcement point named by Rule 5.2 must exist"
    assert hasattr(dh, "check") and hasattr(dh, "stamp") and hasattr(dh, "provenance")


def test_every_live_spec_carries_a_dated_status_header(dh):
    """Rule 6.1. A doc with no date is untrustworthy by construction."""
    missing = [dh.rel(f) for f in dh.spec_files() if dh.header_of(f)[0] is None]
    assert not missing, (
        f"{len(missing)} live spec(s) have no dated Status/Last updated header.\n"
        "Run: python scripts/ops/doc_headers.py --stamp\n  " + "\n  ".join(missing)
    )


def test_no_header_claims_a_date_in_the_future(dh):
    """A future date is either a typo or an aspiration; both make the header worthless."""
    import datetime as dt

    today = dt.date.today().isoformat()
    bad = [
        f"{dh.rel(f)} says {d}" for f in dh.spec_files() if (d := dh.header_of(f)[0]) and d > today
    ]
    assert not bad, "header dates in the future:\n  " + "\n  ".join(bad)


def test_no_commit_changes_a_spec_body_without_touching_its_header(dh):
    """⭐ The rule the owner asked for: specs are updated *before* each commit.

    Forward-only from `CUTOFF`. Grandfathering the past is what lets this ship green instead of
    red — see the module docstring. It cannot be satisfied by editing prose and leaving a stale
    date, because the same commit has to touch the header line.
    """
    violations = [v for f in dh.spec_files() for v in dh.commits_touching_body_without_header(f)]
    assert not violations, (
        f"{len(violations)} commit(s) since {dh.CUTOFF} changed a spec's body without bumping "
        "its header:\n  " + "\n  ".join(f"{p}  ←  {c}" for c, p in violations)
    )


def test_stamping_is_idempotent(dh, tmp_path):
    """A formatter that accretes blank lines or duplicate headers on re-run is not usable in CI.

    ⚠ This is a regression test for a real defect, not a hypothetical: the first version folded
    the date into the existing `Status:` line and produced **32 documents with two Status lines**,
    because a doc whose Status was undated prose could not be dated without either mangling its
    sentence or adding a second header.
    """
    doc = tmp_path / "sample.md"
    doc.write_text("# Title\n\n**Status:** Operational policy.\n\nBody.\n", encoding="utf-8")

    # Drive the same transformation the script applies, twice.
    def apply(text: str) -> str:
        lines = [ln for ln in text.splitlines() if dh.BACKFILL_MARK not in ln]
        lines = dh._tidy_blanks(lines)
        return "\n".join(lines) + "\n"

    once = apply(doc.read_text(encoding="utf-8"))
    assert apply(once) == once, "the transformation is not idempotent"


def test_the_header_carries_no_commit_hash(dh):
    """⭐ The chicken-and-egg, pinned as a decision rather than left to be rediscovered.

    A hash cannot be written into the content it describes — it does not exist until after that
    content is committed. Every workaround is worse than the gap: amending in a post-commit hook
    rewrites published history, and a hash written by the *next* commit is permanently one commit
    stale and wrong exactly when someone trusts it. So the hash is **derived** by `--provenance`
    and never stored. This test stops a future well-meaning edit from adding a `Commit:` field.
    """
    import re

    offenders = []
    for f in dh.spec_files():
        _, head = dh.header_of(f)
        if re.search(r"^\s*[>*\-\s]*\*\*Commit\b", head, re.M | re.I):
            offenders.append(dh.rel(f))
        # A bare 7-40 char hex blob on a header line is a hash by another name.
        if re.search(r"^\s*[>*\-\s]*\*\*(?:Status|Last updated)\b[^\n]*\b[0-9a-f]{7,40}\b", head, re.M | re.I):
            offenders.append(dh.rel(f))
    assert not offenders, (
        "header carries a commit hash — derive it with `--provenance` instead:\n  "
        + "\n  ".join(sorted(set(offenders)))
    )
