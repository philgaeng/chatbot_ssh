#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Enforce Rule 6.1 — every live spec carries a dated Status header, and no commit
changes a spec's body without touching that header.

    python scripts/ops/doc_headers.py --check        # report only, exit 1 on violations
    python scripts/ops/doc_headers.py --stamp        # add missing headers (writes)
    python scripts/ops/doc_headers.py --provenance   # doc -> the commit that last changed it

WHY THIS EXISTS. `docs/engineering/06_documentation_lifecycle.md` §6 has required a dated
Status header on every document since 2026-08-03. Measured on 2026-09-04: **40 of 80 live
specs had no header at all**, and only 3 of 98 had a date at least as recent as their last
commit. The rule was obeyed in `docs/engineering/` (7 of 7) — the folder the rule lives in —
and essentially nowhere else. That is Rule 5.2 turned on itself: *a rule that isn't enforced
isn't a rule*.

⭐ THE COMMIT-HASH PROBLEM, AND WHY THE HEADER DOES NOT CARRY A HASH.
The obvious header field is "which commit does this doc describe" — and it cannot be written,
because the hash does not exist until after the content is committed. Every workaround is
worse than the gap: a post-commit hook that amends rewrites published history; a hash written
by the *next* commit is permanently one commit stale and silently wrong at exactly the moment
someone trusts it.

So the header carries **only what git cannot infer** — the tier, the scope, and the date a
human last reviewed the content. The hash is *derived on demand* by `--provenance`, which is
exact, free and can never drift:

    git log -1 --format='%h %ad %s' -- <doc>

⚠ WHAT --check DOES NOT DO, DELIBERATELY. It does not compare the header date against the
file's last-commit date. That check sounds right and is a trap: it would have failed on 95 of
98 documents the day it shipped, and a permanently red gate teaches people to walk past gates
(D-26, and the `make help` banner retracted on 2026-09-03). Instead the header date means
*"when the content was last reviewed"* and stays hand-set and truthful, while rule 3 below —
which is forward-only — makes it impossible to change a spec without confronting it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Tier 1 (live specification) and tier 1b (engineering standards), per 06_documentation_lifecycle.md §1.
# Sprint folders, reviews and archive are deliberately OUT: a sprint doc is a dated record of
# in-flight work, and stamping it on every edit would be churn with no reader.
SPEC_DIRS = (
    "docs/ticketing_system",
    "docs/services",
    "docs/rest_chatbot",
    "docs/seah",
    "docs/deployment",
    "docs/engineering",
    "docs/dpg",
)
ROOT_DOCS = ("docs/README.md",)

EXCLUDE_PARTS = {"archive", "_starter_kit"}

# `**Status:** authoritative (2026-09-04)` — also accepts `Last updated:` for docs that
# already used that wording, so this rule does not force a pointless rewording pass.
STATUS_RE = re.compile(
    r"^\s*[>*\-\s]*\*\*(?:Status|Last updated)\b.*?(\d{4}-\d{2}-\d{2})", re.M | re.I
)
STATUS_LINE_RE = re.compile(r"\*\*(?:Status|Last updated)\b", re.I)
HEAD_LINES = 15

# Forward-only. Commits before this date are grandfathered: the rule ships green and only
# governs what happens next. Introducing a lint retroactively is how you get a red build
# nobody can fix and everybody learns to ignore.
CUTOFF = "2026-09-04"


def spec_files() -> list[Path]:
    out: list[Path] = []
    for d in SPEC_DIRS:
        base = REPO_ROOT / d
        if not base.exists():
            continue
        for f in sorted(base.rglob("*.md")):
            if EXCLUDE_PARTS & set(f.parts):
                continue
            out.append(f)
    for r in ROOT_DOCS:
        p = REPO_ROOT / r
        if p.exists():
            out.append(p)
    return out


class GitUnavailable(RuntimeError):
    """git is missing, or the clone is shallow — history checks cannot be trusted."""


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True
        ).stdout.strip()
    except FileNotFoundError:
        return ""


def git_history_available() -> str | None:
    """Return None if history is usable, else why it is not.

    ⚠ Two ways this silently under-enforces, and both were real here:
    the app containers have **no git binary** (`sh: 1: git: not found`), and
    `actions/checkout` defaults to **`fetch-depth: 1`** — a shallow clone where
    `git log -- <file>` sees at most the tip commit. Either would let rule 6.1a
    report success while checking nothing, which is the failure mode this project
    has now hit twice in monitoring (`ops` blind on staging, `health_rows=0`).
    So the caller must skip **loudly**, never pass quietly.
    """
    if not _git("rev-parse", "--is-inside-work-tree"):
        return "git is unavailable (no binary, or not a work tree)"
    if _git("rev-parse", "--is-shallow-repository") == "true":
        return "the clone is shallow — set `fetch-depth: 0` on actions/checkout"
    return None


def header_of(path: Path) -> tuple[str | None, str]:
    """Return (iso_date_or_None, the head text searched)."""
    head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:HEAD_LINES])
    m = STATUS_RE.search(head)
    return (m.group(1) if m else None), head


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def commits_touching_body_without_header(path: Path) -> list[tuple[str, str]]:
    """Commits on/after CUTOFF that changed this doc's body but not its Status line.

    This is the enforcement of "specs are updated before each commit": you cannot change
    what a spec says and leave its header claiming an older review date, because the same
    commit has to touch that line.
    """
    log = _git(
        "log", f"--since={CUTOFF}", "--no-merges", "--format=%H%x00%h %ad %s",
        "--date=short", "--", rel(path),
    )
    bad: list[tuple[str, str]] = []
    for line in filter(None, log.splitlines()):
        sha, _, pretty = line.partition("\x00")
        diff = _git("show", "--format=", "--unified=0", sha, "--", rel(path))
        changed = [
            ln for ln in diff.splitlines()
            if (ln.startswith("+") or ln.startswith("-"))
            and not ln.startswith(("+++", "---"))
        ]
        if not changed:
            continue  # pure rename / mode change
        if not any(STATUS_LINE_RE.search(ln) for ln in changed):
            bad.append((pretty, rel(path)))
    return bad


def check() -> int:
    today = dt.date.today().isoformat()
    missing: list[str] = []
    future: list[str] = []
    unstamped: list[tuple[str, str]] = []

    why = git_history_available()
    for f in spec_files():
        date, _ = header_of(f)
        if date is None:
            missing.append(rel(f))
            continue
        if date > today:
            future.append(f"{rel(f)} (header says {date}, today is {today})")
        if why is None:
            unstamped.extend(commits_touching_body_without_header(f))

    fail = False
    if missing:
        fail = True
        print(f"✖ {len(missing)} live spec(s) have no dated Status header (Rule 6.1):")
        for m in missing:
            print(f"    {m}")
        print("  Fix: python scripts/ops/doc_headers.py --stamp\n")
    if future:
        fail = True
        print(f"✖ {len(future)} doc(s) carry a Status date in the future:")
        for m in future:
            print(f"    {m}")
        print()
    if unstamped:
        fail = True
        print(
            f"✖ {len(unstamped)} commit(s) since {CUTOFF} changed a spec's body without "
            "touching its Status header:"
        )
        for pretty, path in unstamped:
            print(f"    {path}  ←  {pretty}")
        print(
            "  A spec edit and its date belong in the same commit. Bump the Status line.\n"
        )

    if not fail:
        print(f"✔ {len(spec_files())} live specs: all carry a dated Status header, "
              f"and no commit since {CUTOFF} changed one without it.")
    return 1 if fail else 0


BACKFILL_MARK = "backfilled from git"
TIER = {
    "docs/engineering": "engineering standard (tier 1b) — binding on every change",
    "docs/dpg": "evidence pack — cited by the DPG assessment",
}
DEFAULT_TIER = "live specification (tier 1) — authoritative for what the system does today"


def _tier_of(path: Path) -> str:
    if path.name.lower() in {"readme.md", "00_services_index.md", "00_rest_chatbot_index.md",
                             "00_engineering_index.md"}:
        return "index — the map of this folder, not a spec in itself"
    r = rel(path)
    for prefix, label in TIER.items():
        if r.startswith(prefix):
            return label
    return DEFAULT_TIER


def _tidy_blanks(lines: list[str]) -> list[str]:
    """Collapse runs of blank lines in the head. Re-running the stamp must not accrete them."""
    out: list[str] = []
    for i, ln in enumerate(lines):
        if i < HEAD_LINES and not ln.strip() and out and not out[-1].strip():
            continue
        out.append(ln)
    return out


def stamp() -> int:
    """Give every live spec a dated header, taking the date from git — never from today.

    ⚠ **Two fields, on purpose.** `Status:` says what the document *is*; `Last updated:`
    says *when*. Folding them into one line is what produced 32 duplicated headers on the
    first attempt: a doc whose `Status:` was prose with no date ("Operational policy.
    Companion to …") could not be dated without either mangling its sentence or adding a
    second Status line.

    ⚠ **The date is the file's last-commit date, not the date of this run**, and the marker
    says so. Stamping 81 documents "reviewed today" would be 81 claims nobody made
    (Rule 4.1). And `Status:` is filled from the doc's **folder**, which is a fact from
    §1's tier table — never "authoritative", which would assert a review that did not happen.
    """
    today = dt.date.today().isoformat()
    added = 0
    for f in spec_files():
        lines = f.read_text(encoding="utf-8").splitlines()
        # Drop any header a previous run of this script inserted, so it is re-runnable.
        # Both fields: the dated line, and a Status line whose text this script generated.
        generated = {f"**Status:** {t}." for t in
                     (*TIER.values(), DEFAULT_TIER,
                      "index — the map of this folder, not a spec in itself")}
        lines = [ln for ln in lines
                 if BACKFILL_MARK not in ln and ln.strip() not in generated]
        while len(lines) > 1 and not lines[0].strip():
            lines.pop(0)

        head = "\n".join(lines[:HEAD_LINES])
        if STATUS_RE.search(head):
            f.write_text("\n".join(lines) + "\n", encoding="utf-8")
            continue  # already carries a dated header — leave it alone

        git_date = _git("log", "-1", "--format=%ad", "--date=short", "--", rel(f)) or today
        stamp_line = (
            f"**Last updated:** {git_date} · ⚠ {BACKFILL_MARK} {today}; "
            f"not re-verified against the code"
        )

        # Prefer to sit directly under an existing Status line; else under the H1 title.
        insert_at, needs_blank = None, False
        for i, ln in enumerate(lines[:HEAD_LINES]):
            if STATUS_LINE_RE.search(ln):
                insert_at = i + 1
                break
        if insert_at is None:
            for i, ln in enumerate(lines[:5]):
                if ln.startswith("# "):
                    insert_at, needs_blank = i + 1, True
                    break
        if insert_at is None:
            insert_at, needs_blank = 0, True

        block = ["", f"**Status:** {_tier_of(f)}.", stamp_line] if needs_blank else [stamp_line]
        lines[insert_at:insert_at] = block
        f.write_text("\n".join(_tidy_blanks(lines)) + "\n", encoding="utf-8")
        added += 1
        print(f"  stamped {rel(f)}  ({git_date})")
    print(f"\n{added} document(s) stamped.")
    return 0


def provenance() -> int:
    """doc → the commit that last changed it. The answer to 'which commit is this spec?'.

    Never stored in the file: at write time the hash does not exist yet, and any copy of it
    is stale the moment the doc changes again. Derived here instead, where it is always exact.
    """
    print(f"{'document':<62} {'commit':<9} {'date':<11} subject")
    print("-" * 120)
    for f in spec_files():
        # `%x00` is git's escape, expanded by git. A literal NUL here would be rejected by
        # subprocess ("embedded null byte") — which is exactly how this line first failed.
        line = _git("log", "-1", "--format=%h%x00%ad%x00%s", "--date=short", "--", rel(f))
        if not line:
            print(f"{rel(f):<62} {'—':<9} {'uncommitted':<11}")
            continue
        h, d, s = (line.split("\x00") + ["", "", ""])[:3]
        print(f"{rel(f):<62} {h:<9} {d:<11} {s[:44]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="report only; exit 1 on violations")
    g.add_argument("--stamp", action="store_true", help="add missing headers (writes files)")
    g.add_argument("--provenance", action="store_true", help="doc → last commit, from git")
    a = ap.parse_args()
    if a.check:
        return check()
    if a.stamp:
        return stamp()
    return provenance()


if __name__ == "__main__":
    sys.exit(main())
