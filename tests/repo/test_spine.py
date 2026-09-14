# SPDX-License-Identifier: Apache-2.0
"""
The register's pin — `docs/SPINE.md`.

**Why this exists, and why it shipped in the same sprint as the register.**
`docs/engineering/07_work_items.md` defines kinds, profiles and two state fields. None of that is
worth anything unenforced, and this repository has measured the cost twice: rule 6.1 (a dated header
on every doc) was honoured **7 of 7** inside the folder where it was written and **40 of 80**
everywhere else until `scripts/ops/doc_headers.py` existed; and `tests/repo/test_doc_code_refs.py`
exists because an SPDX pass shifted ~80 line citations and nobody noticed for a day.

A register nobody validates becomes the *sixth* competing answer to "what is next" — and the one that
looks most authoritative. That is strictly worse than the seven-file mess it replaced.

⚠ **WHAT THIS DOES NOT CHECK, DELIBERATELY.** It does not judge whether the plan is *good*, whether an
estimate is honest, or whether an item should exist. It checks that the register is **well-formed and
internally consistent** — the same floor `test_doc_code_refs.py` sets for citations. A checker that
tried to judge content would be wrong often enough to get muted, and a muted gate is decoration.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SPINE = REPO_ROOT / "docs" / "SPINE.md"

# The five kinds of 07 §2.1. There is no sixth — a security finding is a bug, a deviation, a debt or
# a chore, carrying the `+SENSITIVE` modifier (§4.2). This tuple is the pin that catches the drift:
# the register's own first build generated `kind: security` and this list is what would have caught it.
KINDS = ("feature", "bug", "deviation", "debt", "chore")

# 07 §7.1 — scheduling state and verification level are separate fields, never one.
STATES = ("proposed", "ready", "current", "merged", "done", "blocked", "dropped")
VERIFICATION = ("planned", "implemented", "tested", "applied locally", "deployed", "verified")

ID_RE = re.compile(r"GRM-\d{3}")   # full id, no capture group — callers compare against row ids
# A row is any table line whose first cell OPENS with a backticked id. The Register carries the id
# and the title in one cell ("`GRM-065` — the orchestrator port…"); the Backlog gives it a cell of
# its own. Requiring a pipe straight after the id silently skipped every Register row.
ROW_RE = re.compile(r"^\|\s*`(GRM-\d{3})`(.*)$")


@pytest.fixture(scope="module")
def spine() -> str:
    assert SPINE.exists(), "docs/SPINE.md is the register — it may not be deleted, only superseded"
    return SPINE.read_text(encoding="utf-8")


def _sections(text: str) -> dict[str, str]:
    out, cur, buf = {}, "«preamble»", []
    for line in text.split("\n"):
        if line.startswith("## ") or line.startswith("### "):
            out[cur] = "\n".join(buf)
            cur, buf = line.lstrip("# ").strip(), []
        else:
            buf.append(line)
    out[cur] = "\n".join(buf)
    return out


def _id_rows(text: str) -> list[tuple[str, str]]:
    """Rows carrying a `GRM-###` id. Used only by the identity checks."""
    return [(m.group(1), m.group(2)) for m in (ROW_RE.match(l) for l in text.split("\n")) if m]


# Only these sections carry work items. "How to read this" and "What this replaced" are prose tables
# about the register, not rows in it — a checker that cannot tell the difference fails on its own
# documentation, which is how a gate gets muted.
ITEM_SECTIONS = ("Register", "Carrying", "Debt", "Done")


def _item_text(text: str) -> str:
    return "\n".join(v for k, v in _sections(text).items() if k.startswith(ITEM_SECTIONS))


def _data_rows(text: str) -> list[tuple[str, list[str]]]:
    """EVERY table data row, whatever its id shape.

    ⚠ The field checks used to run through `_id_rows`, which matches only `GRM-###`. That made the
    whole sprint-ticket half of the Register — `OM-*`, `QA-*`, `HR-*` — invisible to them: a `blocked`
    row with no named blocker passed because nothing was looking at it. Found by the mutation sweep.
    """
    out = []
    for line in text.split("\n"):
        if not line.startswith("| ") or set(line) <= set("|-: "):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or cells[0].lower() in ("id", "item", "lane", "source", ""):
            continue
        out.append((cells[0][:60], cells))
    return out


# ── 1. identity ──────────────────────────────────────────────────────────────

def test_ids_are_unique_in_the_source_tables(spine):
    """An id is a claim to one piece of work. Two rows claiming it is the ambiguity ids exist to remove.

    Source tables only: *Open security findings* is a derived view (test 2 pins it instead).
    """
    secs = _sections(spine)
    source = "\n".join(v for k, v in secs.items() if k not in ("Open security findings",))
    seen: dict[str, int] = {}
    for rid, _ in _id_rows(source):
        seen[rid] = seen.get(rid, 0) + 1
    dupes = {k: v for k, v in seen.items() if v > 1}
    assert not dupes, f"duplicate ids in the register's source tables: {dupes}"


def test_the_security_view_only_cites_ids_that_exist(spine):
    """The view is a *view*. If it can name an item the register does not hold, it can drift silently —
    which is the failure `dpg/02_questions.md` is generated to avoid."""
    secs = _sections(spine)
    view = secs.get("Open security findings", "")
    assert view.strip(), "the security view is missing — it is what stops a +SENSITIVE row reading as routine"
    source = "\n".join(v for k, v in secs.items() if k != "Open security findings")
    known = {rid for rid, _ in _id_rows(source)}
    cited = set(ID_RE.findall(view))
    assert cited, "the security view cites no ids at all"
    assert cited <= known, (
        f"the security view cites ids the register does not hold: {sorted(cited - known)}"
    )


def test_the_next_free_id_line_is_accurate(spine):
    """A stale allocator hands out an id that is already taken. Per Q-07 this file IS the allocator,
    so the line has to be true or the mechanism is a trap."""
    m = re.search(r"`GRM-(\d{3})` is the next free id", spine)
    assert m, "the register must state its next free id — it is the allocator (Q-07)"
    declared = int(m.group(1))
    # from ROWS only — the next-free-id line names an id that is by definition not in use yet,
    # and counting it would make the check permanently off by one.
    highest = max(int(rid[4:]) for rid, _ in _id_rows(spine))
    assert declared == highest + 1, (
        f"next-free-id says GRM-{declared:03d} but the highest id in use is GRM-{highest:03d}"
    )


# ── 2. the vocabulary ────────────────────────────────────────────────────────

def test_every_kind_is_one_of_the_five(spine):
    """07 §2.1. The register's own first build produced `kind: security`; there is no such kind."""
    bad = []
    for label, cells in _data_rows(_item_text(spine)):
        # EXACT match, never startswith: a profile cell reading `chore+SENSITIVE` starts with a kind
        # and was masking the column next to it. Caught by the mutation sweep, not by review.
        if not any(c in KINDS for c in cells[:4]):
            bad.append((label, cells[:4]))
    assert not bad, (
        "rows whose kind is not one of feature/bug/deviation/debt/chore "
        f"(a security finding is one of those + `+SENSITIVE`, never a sixth kind): {bad}"
    )


def test_blocked_rows_name_their_blocker(spine):
    """07 §7.1 — `blocked` without a named blocker and unblock condition is just a stalled row, and
    nobody can tell whether it is waiting on a person, a decision, or nothing at all."""
    bad = [label for label, cells in _data_rows(spine)
           if any(c == "`blocked`" for c in cells)
           and not re.search(r"[Bb]locker|[Bb]locked on|waiting on", " | ".join(cells))]
    assert not bad, f"`blocked` rows that do not name a blocker: {bad}"


# ── 3. structure ─────────────────────────────────────────────────────────────

def test_at_most_one_current_per_lane(spine):
    """07 §7.3 — one `current` PER LANE, not per project. This repository runs parallel agent streams;
    a single global `current` would make that either impossible or a lie."""
    secs = _sections(spine)
    cur = secs.get("Current", "")
    assert cur.strip(), "the register must have a Current section"
    lanes: dict[str, int] = {}
    for line in cur.split("\n"):
        if not line.startswith("| ") or line.startswith("| Lane") or set(line) <= set("|- "):
            continue
        lane = line.strip().strip("|").split("|")[0].strip()
        if lane and not lane.startswith("*"):
            lanes[lane] = lanes.get(lane, 0) + 1
    over = {k: v for k, v in lanes.items() if v > 1}
    assert not over, f"lanes with more than one `current` item: {over}"


def test_ready_rows_carry_a_profile(spine):
    """07 §6 + OM-04 — an item cannot reach `ready` without a profile.

    The profile is what selects the model, the reviewer, the tests and the gates (§4.3), and it is
    derived at intake from six questions — `docs/items/TEMPLATE.md` §3. A `ready` row with an empty
    profile cell is an item nobody has sized the blast radius of, sitting in the list of things
    somebody could pick up today. **`+SENSITIVE` is never waived by kind or by size (§4.2)**, so the
    one row this is most likely to catch is exactly the one it most matters for.

    ⚠ Column-indexed, not pattern-matched. `chore` is both a kind and a profile, and `bug` and
    `deviation` are both — so a substring search passes a row that has a kind and no profile at all.
    The header row is the only unambiguous way to tell the two columns apart.
    """
    bad = []
    profile_idx: int | None = None
    for line in spine.split("\n"):
        stripped = line.strip()
        if not stripped.startswith("|"):
            profile_idx = None          # a table ends at the first non-table line
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        lowered = [c.lower() for c in cells]
        if "profile" in lowered:        # header row — remember where the column is
            profile_idx = lowered.index("profile")
            continue
        if profile_idx is None or set(stripped) <= set("|-: "):
            continue
        if not any(c in ("`ready`", "`current`") or c.startswith(("`ready`", "`current`")) for c in cells):
            continue
        if profile_idx >= len(cells) or cells[profile_idx] in ("", "—", "-", "–", "TBD", "?"):
            bad.append(cells[0][:60])
    assert not bad, (
        "`ready`/`current` rows with no profile — the profile is what selects the model, the "
        f"reviewer, the tests and the gates (07 §4.3): {bad}"
    )


def test_the_register_declares_its_own_governing_standard(spine):
    """A register that does not say which rules it follows cannot be checked against them."""
    assert "07_work_items.md" in spine, "the register must name the standard that governs it"


def test_followup_links_resolve(spine):
    """The standing deferral rule writes a `followups/` doc AND a register row. A row pointing at a
    document that does not exist is the debt going quiet, which is what the rule exists to prevent."""
    missing = []
    for m in re.finditer(r"\((\.{0,2}/?[\w./-]*followups/[\w.-]+\.md)\)", spine):
        target = (SPINE.parent / m.group(1)).resolve()
        if not target.exists():
            missing.append(m.group(1))
    assert not missing, f"register rows link to follow-up documents that do not exist: {missing}"


# ── 4. the honesty rule ──────────────────────────────────────────────────────

def test_done_rows_carry_a_verification_level(spine):
    """07 §7.2 — an item is `done` only when its verification level meets what its profile requires.
    A Done row with no verification is the exact claim the honesty markers exist to prevent: it reads
    as finished and says nothing about whether anyone looked."""
    secs = _sections(spine)
    done = next((v for k, v in secs.items() if k.startswith("Done")), "")
    assert done.strip(), "the register must have a Done section"
    bad = []
    for line in done.split("\n"):
        if not line.startswith("| ") or set(line) <= set("|- ") or line.startswith("| Item"):
            continue
        if not any(f"`{v}`" in line for v in VERIFICATION):
            bad.append(line.strip()[:80])
    assert not bad, f"Done rows with no verification level: {bad}"
