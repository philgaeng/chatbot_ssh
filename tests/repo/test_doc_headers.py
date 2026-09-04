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
    why = dh.git_history_available()
    if why is not None:
        # ⚠ SKIP, never pass. The app containers have no git binary and `actions/checkout`
        # defaults to a shallow clone; either would let this "succeed" having checked nothing.
        # A green tick that inspected zero commits is the `health_rows=0` failure in test form.
        pytest.skip(f"cannot verify rule 6.1a: {why}")

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


# ═════════════════════════════════════════════════════════════════════════════
# Rule 10 — audience. What may appear in a document that will be published.
# ═════════════════════════════════════════════════════════════════════════════


def test_no_public_spec_links_into_a_sprint_or_review_folder(dh):
    """Rule 10.1. A published spec must not depend on a folder the public repo does not have.

    ⚠ **The link is the symptom; the reason is the thing.** Removing a citation without folding
    its reason into the spec leaves a rule with no justification — the decay §5.1 exists to
    prevent, and worse than the broken link. Folds happened first; this pins the result.

    Measured before the fold pass on 2026-09-04: **28 of 99 documents carried 93 such links**,
    51 of them in `ticketing_system/` alone. Twenty-one pointed at four `DECISION-*` documents,
    which is why `docs/DECISIONS.md` exists: provenance belongs in a public decision log, not in
    a sprint folder a reader cannot open.

    A document may opt out by declaring `**Audience:** internal` — used by
    `deployment/18_sops_migration_handover.md`, which is a handover carrying a live credential.
    """
    import os
    import re
    from urllib.parse import unquote

    PRUNE = ("docs/sprints/", "docs/reviews/")
    offenders: list[str] = []
    for f in dh.spec_files():
        if dh.audience_of(f) == "internal":
            continue
        text = f.read_text(encoding="utf-8")
        for m in re.finditer(r"\]\(([^)#\s]+)\)", text):
            target = unquote(m.group(1)).split("#")[0]
            if target.startswith(("http", "mailto:")):
                continue
            resolved = os.path.normpath(os.path.join(os.path.dirname(dh.rel(f)), target))
            if resolved.startswith(PRUNE):
                offenders.append(f"{dh.rel(f)} → {target}")

    assert not offenders, (
        f"{len(offenders)} link(s) from a public spec into an internal folder (Rule 10.1).\n"
        "Fold the reason into the spec, or record the fork in docs/DECISIONS.md — do not just "
        "delete the link:\n  " + "\n  ".join(offenders)
    )


def test_no_public_spec_carries_internal_only_content(dh):
    """Rule 10.5 — host addresses, instance ids, ssh logins and credential literals.

    ⚠ **Publishing is a one-way door**, so this guards the direction that cannot be undone. It
    caught `deployment/18_sops_migration_handover.md`, which sits in a tier-1 folder and carries
    the staging host's address, an `ssh` login for it, and `POSTGRES_PASSWORD=password` — **the
    live pre-rotation credential on staging and DOR production, not a stale example.**

    Those facts are load-bearing in that document: its whole argument is that the credential is
    real and must be rotated rather than deleted. **Redacting them would destroy the document, so
    the control is not publishing it** — hence the audience opt-out rather than a scrub.

    The IPv4 pattern only fires on host-ish lines, deliberately: `click-plugins | 1.1.1.2` is a
    version, and a scanner that flags it is one people learn to mute.
    """
    offenders = [
        finding
        for f in dh.spec_files()
        if dh.audience_of(f) != "internal"
        for finding in dh.internal_content(f)
    ]
    assert not offenders, (
        f"{len(offenders)} piece(s) of internal-only content in documents that would be "
        "published (Rule 10.5). Remove it, or declare `**Audience:** internal`:\n  "
        + "\n  ".join(offenders)
    )


def test_a_stamped_header_is_never_spliced_into_a_blockquote(dh):
    """Regression: the stamp split a wrapped sentence in six documents.

    `--stamp` inserts its dated line directly under an existing `Status:` line. When that line was
    *inside a blockquote* — `> **Written:** 2026-08-20. **Status:** 🟨 steps 0–5 done…` — the
    insertion landed between two lines of one wrapped sentence, breaking both the sentence and the
    quote. Caught by reading the output rather than by the checker, which was happy: the header
    existed and carried a date, so every assertion passed while the document was damaged.
    """
    import re

    spliced = []
    for f in dh.spec_files():
        lines = f.read_text(encoding="utf-8").splitlines()
        for i, ln in enumerate(lines[: dh.HEAD_LINES + 15]):
            if not re.match(r"^\*\*Last updated:\*\*", ln):
                continue
            # ⚠ The signal is the line BEFORE, not the line after. A header legitimately
            # precedes a blockquote (`03_admin_setup_flow_evaluation.md` does); it never
            # legitimately follows one, because that means it was inserted into the quote.
            # The first version of this assertion checked both and produced a false positive
            # on a correctly-formatted document — a check that cries wolf gets muted.
            if i and lines[i - 1].startswith(">"):
                spliced.append(f"{dh.rel(f)}:{i + 1}")
    assert not spliced, (
        "a dated header sits inside a blockquote, splitting it:\n  " + "\n  ".join(spliced)
    )
