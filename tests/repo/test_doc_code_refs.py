# SPDX-License-Identifier: Apache-2.0
"""
Documentation `file.py:line` reference pin.

**The finding this exists for.** Sprint 0's SPDX pass added a two-line header to 585 source files,
which shifted every line number in the repository by +2 — and with it roughly eighty `file.py:NNN`
references across the sprint specs and the DPG evidence pack. Nobody noticed for a day, and one
stale number was then *copied into* `docs/dpg/privacy-assessment.md` — a document whose whole claim
is that every leg was verified against the code at the line cited.

That is the failure this pins: **a reference that names a line is a claim about that line**, and a
claim nobody re-checks decays the moment anything above it moves. A reviewer who clicks
`LLM_services.py:230` and lands on a closing brace stops trusting the surrounding paragraph, which
is exactly the trust the evidence pack is made of.

Three properties, in increasing strength:

1. Every referenced file exists (catches renames and deletions).
2. Every referenced line is within that file (catches truncation).
3. **A curated set of load-bearing references lands on code containing an expected token.** This is
   the only one of the three that catches a *shift*, and it is therefore the one that earns its keep.

⚠ **What this does NOT catch.** A reference that moved but stayed in range, and is not in ANCHORS,
passes silently. This is a floor, not a guarantee — the honest reading is "the citations a reviewer
is most likely to click are checked, and the rest are at least not dangling". Widening ANCHORS is
cheap; do it whenever a reference becomes load-bearing.

**When ANCHORS goes red, that is usually correct.** Sprint 1 moves all nine LLM call sites out of
`LLM_services.py`. The red is the reminder that the docs citing them must move in the same commit —
which is precisely the discipline `docs/dpg/privacy-assessment.md` §2.2 needs and would otherwise
only get from DPG-30, months later.

⚠ **Writing about this pin.** A document describing it must not spell an example in citation form —
`somefile.py:99999` in prose is indistinguishable from a real citation and this test will flag it, as it
did to its own ledger entry on the day it landed. Write "line 99999 of `somefile.py`" instead. That is
deliberate: the alternative is an ignore-marker, and an ignore-marker in a pin like this one is a
suppression hatch waiting to be used on a real finding.

Spec: docs/sprints/2026-08-llm/02-llm-agnostic-spec.md §0.5a
"""
from __future__ import annotations

import re
import subprocess
from collections import defaultdict
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "docs"

# `archive/` is history: it describes the code as it was, and correcting it would be falsifying a
# record. Live docs are the ones a reviewer reads and the ones this pin governs.
SKIP_DIR_MARKER = "archive"

# Fallback skip list, used only when `git ls-files` is unavailable. ⚠ `.claude/` matters more than it
# looks: agent worktrees there hold **whole gitignored copies of the repository at older commits**, so a
# filesystem walk resolves a dangling reference against a ghost. That is not hypothetical — it is how this
# test passed locally and failed in CI on the day it landed, over `tickets.py`, which H2-02 split into a
# package months ago. Prefer git; it is the only index that matches what CI checks out.
SKIP_SCAN = {".git", ".claude", "node_modules", "__pycache__", "uploads", ".pytest_cache", ".keras", "logs"}

REF_RE = re.compile(r"`?([A-Za-z0-9_./-]+\.py):(\d+)")

# References to files that are deliberately gone, with the reason. ⚠ A contract, not a suppression
# list: an entry is a claim that the *document* is right and the file's absence is the expected
# outcome. If you cannot state that, fix the reference instead.
# Keyed as the documents write them — a doc may cite a bare basename.
KNOWN_ABSENT: dict[str, str] = {
    "gsheet.py": (
        "Retired by CL-02 (July 2026) with the Google Sheets monitoring channel. The reference "
        "lives in sprints/2026-07_schema_and_legacy_cleanup/AUDIT_FINDINGS.md, which is the "
        "document that *recommended deleting it*. The file being gone is that document being "
        "correct, not stale."
    ),
    "tickets.py": (
        "Split into the package `ticketing/api/routers/tickets/` by H2-02 (July 2026) — the module was "
        "2,100+ lines. The citations are in July sprint documents that describe the code as it was, and "
        "one of them is the review that *recommended the split*. ⚠ This entry is also the reason this "
        "test indexes from `git ls-files` rather than walking the filesystem: agent worktrees under "
        "`.claude/` still hold pre-split copies, so a walk resolved these citations against a ghost and "
        "the test passed locally while failing in CI."
    ),
    "gsheet_monitoring_api.py": (
        "Same retirement, same document, same reasoning — a Flask blueprint wired only into a dead "
        "app module, enumerated by the audit that removed it."
    ),
}

# Load-bearing references: (path, line, token that must appear on that line).
#
# Chosen because a reviewer or an agent is likely to click them, and because being wrong changes a
# conclusion rather than costing a scroll. Keep this list SHORT and current — a long list nobody
# updates becomes noise, and noise is what the CI-red finding (D-26) is about.
ANCHORS: tuple[tuple[str, int, str], ...] = (
    # The nine model call sites — the indicator-4 inventory, cited in four documents.
    # The six chatbot call sites — what the privacy assessment's leg L4 cites. ⚠ **Five of them are
    # now `call_llm(` rather than `.create(`**: DPG-18 moved request construction into the layer, so
    # the anchor token changed as well as the line. The sixth is ASR, which is a different API
    # surface (multipart audio, no messages) and keeps its own three lines.
    ("backend/services/LLM_services.py", 82, "audio.transcriptions.create"),
    ("backend/services/LLM_services.py", 89, "language=language_code"),
    ("backend/services/LLM_services.py", 138, "call_llm"),
    ("backend/services/LLM_services.py", 169, "call_llm"),
    ("backend/services/LLM_services.py", 312, "call_llm"),
    ("backend/services/LLM_services.py", 558, "call_llm"),
    ("backend/services/LLM_services.py", 618, "call_llm"),
    # Where an off-catalogue category is repaired or dropped (D-51). Cited by the benchmark
    # evidence and by TODO/PROGRESS as the place the boundary is enforced.
    ("backend/services/LLM_services.py", 373, "resolve_categories"),
    ("backend/services/category_resolution.py", 94, "def resolve_categories"),
    # Where every model name is declared — one file, one line each (DPG-17).
    ("backend/config/llm_config.py", 114, "gpt-5-nano"),
    # The three ticketing call sites — leg L5.
    ("ticketing/clients/llm_client.py", 197, "call_llm"),
    ("ticketing/clients/llm_client.py", 275, "call_llm"),
    ("ticketing/clients/llm_client.py", 354, "call_llm"),
    ("ticketing/api/routers/tickets/summary.py", 113, "the configured LLM"),
    # The privacy assessment's load-bearing citations (indicators 7, 9a).
    ("backend/services/database_services/base_manager.py", 266, "_encrypt_field"),
    ("backend/services/database_services/base_manager.py", 302, "_decrypt_field"),
    ("backend/services/database_services/base_manager.py", 559, "_hash_value"),
    ("backend/services/database_services/grievance_manager.py", 227, "_decrypt_sensitive_data"),
    ("backend/shared_functions/keyword_detector.py", 259, "detect_sensitive_content"),
    ("ticketing/api/routers/public_closure.py", 38, "public/closure"),
    # ✅ Removed by DPG-11 (2026-08-18): the `load_dotenv('/home/ubuntu/...')` anchor is gone
    # because the line is gone, and the two documents that cited it now say so rather than
    # pointing at whatever moved into line 27. An anchor for deleted code is not a stale anchor
    # to fix; it is an anchor to retire, with the citing prose retired alongside it.
)


def _tracked_python_files() -> list[str]:
    """Repo-relative .py paths, from git — the same set CI checks out.

    A filesystem walk is the wrong index here: gitignored trees (agent worktrees under `.claude/`,
    virtualenvs, stray clones) contain older copies of this repository, and resolving a citation
    against one of those validates a file that no longer exists. Git is exact.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "--", "*.py"],
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout
        files = [line for line in out.splitlines() if line.strip()]
        if files:
            return files
    except (OSError, subprocess.SubprocessError):
        pass
    # Fallback: no git (a source tarball). Less exact, so the skip list has to carry the weight.
    return [
        p.relative_to(REPO_ROOT).as_posix()
        for p in REPO_ROOT.rglob("*.py")
        if not any(part in SKIP_SCAN for part in p.relative_to(REPO_ROOT).parts)
    ]


def _python_index() -> dict[str, list[str]]:
    """{basename: [repo-relative paths]} for every .py file git knows about."""
    index: dict[str, list[str]] = defaultdict(list)
    for rel in _tracked_python_files():
        index[Path(rel).name].append(rel)
    return index


def _live_docs() -> list[Path]:
    return [
        p
        for p in DOCS_ROOT.rglob("*.md")
        if SKIP_DIR_MARKER not in p.relative_to(REPO_ROOT).as_posix()
    ]


def _references() -> list[tuple[str, str, int]]:
    """[(doc, referenced path, line)] — deduplicated on (path, line), first doc wins."""
    out: list[tuple[str, str, int]] = []
    seen: set[tuple[str, int]] = set()
    for doc in _live_docs():
        for match in REF_RE.finditer(doc.read_text(encoding="utf-8")):
            ref, line = match.group(1), int(match.group(2))
            if (ref, line) in seen:
                continue
            seen.add((ref, line))
            out.append((doc.relative_to(REPO_ROOT).as_posix(), ref, line))
    return out


def _resolve(ref: str, index: dict[str, list[str]]) -> list[str]:
    """Candidate real paths for a reference, which may be bare (`base_manager.py`)."""
    if (REPO_ROOT / ref).is_file():
        return [ref]
    by_name = index.get(Path(ref).name, [])
    exact = [p for p in by_name if p.endswith(ref)]
    return exact or by_name


def test_the_reference_regex_finds_something():
    """A regex that silently matched nothing would make every assertion below vacuous."""
    refs = _references()
    assert len(refs) >= 100, (
        f"expected the docs' file:line citations, found {len(refs)}. If references were "
        "deliberately removed, lower this floor deliberately."
    )


def test_every_referenced_source_file_exists():
    """Catches a rename or deletion that leaves a dangling citation."""
    index = _python_index()
    dangling = [
        f"{doc} -> {ref}:{line}"
        for doc, ref, line in _references()
        if ref not in KNOWN_ABSENT and not _resolve(ref, index)
    ]
    assert not dangling, (
        "documentation cites source files that do not exist:\n  "
        + "\n  ".join(dangling)
        + "\n\nFix the reference, or — if the file was deliberately removed and the document is "
        "the record of removing it — add it to KNOWN_ABSENT with that reason."
    )


def test_known_absent_entries_are_still_absent():
    """An exception that stopped being true is worse than no exception."""
    index = _python_index()
    resurrected = [ref for ref in KNOWN_ABSENT if _resolve(ref, index)]
    assert not resurrected, (
        f"KNOWN_ABSENT claims these are gone, but they exist: {resurrected}. "
        "Remove the entry — the reference is live again."
    )


def test_every_referenced_line_is_within_its_file():
    """Catches truncation: a citation pointing past the end of the file it names."""
    index = _python_index()
    beyond = []
    for doc, ref, line in _references():
        candidates = _resolve(ref, index)
        if not candidates:
            continue  # covered by the dangling-file test
        lengths = {c: len((REPO_ROOT / c).read_text(encoding="utf-8", errors="ignore").splitlines()) for c in candidates}
        if all(line > n for n in lengths.values()):
            beyond.append(f"{doc} -> {ref}:{line} (file has {max(lengths.values())} lines)")
    assert not beyond, (
        "documentation cites lines past the end of the file:\n  " + "\n  ".join(beyond)
    )


@pytest.mark.parametrize("ref,line,token", ANCHORS, ids=[f"{r}:{n}" for r, n, _ in ANCHORS])
def test_load_bearing_reference_still_points_at_the_right_code(ref: str, line: int, token: str):
    """
    The only check here that catches a *shift* rather than a dangle.

    Mutation check: change any ANCHORS line number by one and this goes red.

    ⚠ **If this fails because you moved the code, the fix is not to update this table alone.**
    Update the documents that cite the line as well — `grep -rn "<file>:<line>" docs/` finds them.
    A green test with stale docs is the exact outcome this file exists to prevent.
    """
    path = REPO_ROOT / ref
    assert path.is_file(), f"{ref} is missing — ANCHORS is stale"
    lines = path.read_text(encoding="utf-8").splitlines()
    assert line <= len(lines), f"{ref} has {len(lines)} lines; ANCHORS names :{line}"
    actual = lines[line - 1]
    assert token in actual, (
        f"{ref}:{line} should contain {token!r} but is:\n    {actual.strip()!r}\n\n"
        f"The code moved. Re-point the documents that cite it (grep -rn '{Path(ref).name}:{line}' docs/) "
        "and then update ANCHORS — in the same commit."
    )
