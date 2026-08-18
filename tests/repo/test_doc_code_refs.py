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
from collections import defaultdict
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "docs"

# `archive/` is history: it describes the code as it was, and correcting it would be falsifying a
# record. Live docs are the ones a reviewer reads and the ones this pin governs.
SKIP_DIR_MARKER = "archive"

# Directories with no source code to reference.
SKIP_SCAN = {".git", "node_modules", "__pycache__", "uploads", ".pytest_cache", ".keras", "logs"}

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
    ("backend/services/LLM_services.py", 47, "whisper-1"),
    ("backend/services/LLM_services.py", 79, "gpt-3.5-turbo"),
    ("backend/services/LLM_services.py", 116, "gpt-3.5-turbo"),
    ("backend/services/LLM_services.py", 232, "gpt-5-nano"),
    ("backend/services/LLM_services.py", 324, "gpt-4"),
    ("backend/services/LLM_services.py", 385, "gpt-3.5-turbo"),
    ("ticketing/clients/llm_client.py", 90, "gpt-4"),
    ("ticketing/clients/llm_client.py", 141, "_MODEL_STANDARD"),
    ("ticketing/clients/llm_client.py", 142, "_MODEL_SEAH"),
    # The duplicated model names DPG-17 collapses. The last two are invisible to `grep "gpt-"` —
    # one imports the client's privates, one is an OpenAPI endpoint description.
    ("ticketing/services/resolved_summary_builder.py", 301, "_MODEL_SEAH"),
    ("ticketing/tasks/llm.py", 251, "_MODEL_SEAH"),
    ("ticketing/api/routers/tickets/summary.py", 113, "gpt-4"),
    # The privacy assessment's load-bearing citations (indicators 7, 9a).
    ("backend/services/database_services/base_manager.py", 243, "_encrypt_field"),
    ("backend/services/database_services/base_manager.py", 255, "_decrypt_field"),
    ("backend/services/database_services/base_manager.py", 502, "_hash_value"),
    ("backend/services/database_services/grievance_manager.py", 190, "_decrypt_sensitive_data"),
    ("backend/shared_functions/keyword_detector.py", 259, "detect_sensitive_content"),
    ("ticketing/api/routers/public_closure.py", 19, "public/closure"),
    # Dead code that reads as live config — DPG-11 deletes it, and the docs say so.
    ("backend/services/LLM_services.py", 27, "load_dotenv"),
)


def _python_index() -> dict[str, list[str]]:
    """{basename: [repo-relative paths]} for every tracked-ish .py file."""
    index: dict[str, list[str]] = defaultdict(list)
    for path in REPO_ROOT.rglob("*.py"):
        rel = path.relative_to(REPO_ROOT)
        if any(part in SKIP_SCAN for part in rel.parts):
            continue
        index[path.name].append(rel.as_posix())
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
