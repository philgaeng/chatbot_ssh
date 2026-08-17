# SPDX-License-Identifier: Apache-2.0
"""
Add (or verify) the SPDX licence header on every in-scope source file.

DPG indicator 2 needs the licence to be discoverable per file, not only at the repo root — and it
needs to *stay* that way. A one-off pass rots the first week someone adds a module, so this script
is re-runnable and idempotent, and `tests/repo/test_spdx_headers.py` imports SCOPE from here and
fails CI when a file drifts out of coverage. The test and this script therefore cannot disagree:
there is one definition of "in scope", and it is below.

    python scripts/ops/add_spdx_headers.py            # write missing headers
    python scripts/ops/add_spdx_headers.py --check     # report only, exit 1 if any are missing

Scope, per docs/sprints/2026-08-llm/01-licensing-and-governance-spec.md#dpg-01 step 3:

  * tracked *.py under backend/ ticketing/ ops/ scripts/
  * tracked *.ts, *.tsx under channels/

"Tracked" is load-bearing: the file list comes from `git ls-files`, so generated output
(.next/, node_modules/, __pycache__/) and untracked scratch files are excluded by construction
rather than by an exclusion list somebody has to maintain.

Excluded deliberately:

  * docs/ — prose, not source.
  * tests/ — not distributed; the licence applies via the repo root. (Revisit if the DPGA asks
    for per-file coverage of test code; it is a one-line change to SCOPE.)
  * Alembic migrations keep their mandated safety header ("Safe to run: only creates/modifies
    ticketing.* tables"). The SPDX line goes ABOVE it — that header is a *contract with the
    reader* about what the migration touches, and displacing it would be worse than having no
    SPDX line at all. Inserting at the top achieves this for free; there is no special case.

What this script does NOT add: a copyright line. `SPDX-FileCopyrightText` needs a holder, and the
holder is undetermined (DPG-03 / Q-01). Stamping a placeholder into ~580 files would create ~580
places to edit when the determination lands. The holder lives in NOTICE, in one place. Add
copyright headers only if ADB's determination requires per-file attribution.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

IDENTIFIER = "SPDX-License-Identifier: Apache-2.0"

# (directory, suffixes, comment prefix) — the single definition of scope.
SCOPE: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("backend", (".py",), "#"),
    ("ticketing", (".py",), "#"),
    ("ops", (".py",), "#"),
    ("scripts", (".py",), "#"),
    ("channels", (".ts", ".tsx"), "//"),
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def tracked_files(directory: str, suffixes: tuple[str, ...]) -> list[Path]:
    """Tracked files under *directory* with one of *suffixes*, sorted, repo-relative."""
    out = subprocess.run(
        ["git", "ls-files", "--", directory],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return sorted(
        Path(line) for line in out.splitlines() if line.endswith(suffixes)
    )


def in_scope() -> list[tuple[Path, str]]:
    """Every in-scope file with the comment prefix its language uses."""
    files: list[tuple[Path, str]] = []
    for directory, suffixes, prefix in SCOPE:
        files.extend((path, prefix) for path in tracked_files(directory, suffixes))
    return files


def has_header(text: str) -> bool:
    """True if the identifier appears in the first few lines.

    Scoped to the top of the file on purpose: the point is a header, and a stray mention in a
    docstring further down should not satisfy the check. Five lines allows for a shebang, an
    encoding declaration, and a blank line before it.
    """
    return any(IDENTIFIER in line for line in text.splitlines()[:5])


def insertion_line(lines: list[str]) -> int:
    """Index to insert at: after a shebang, and after a PEP 263 encoding declaration.

    Both must stay on lines 1-2 to keep working, so the header goes below them. Everything else —
    module docstrings included — may follow a comment line, so index 0 is correct otherwise.
    """
    index = 0
    if lines and lines[0].startswith("#!"):
        index = 1
    if len(lines) > index and "coding" in lines[index] and lines[index].lstrip().startswith("#"):
        index += 1
    return index


def add_header(path: Path, prefix: str) -> bool:
    """Insert the header. Returns False if it was already present."""
    absolute = REPO_ROOT / path
    text = absolute.read_text(encoding="utf-8")
    if has_header(text):
        return False

    lines = text.splitlines(keepends=True)
    index = insertion_line(lines)
    header = f"{prefix} {IDENTIFIER}\n"
    # A blank line after the header, unless the next line is already blank — keeps the diff
    # visually honest and does not accumulate blank lines when re-run on an edited file.
    if index < len(lines) and lines[index].strip():
        header += "\n"
    lines.insert(index, header)
    absolute.write_text("".join(lines), encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument(
        "--check",
        action="store_true",
        help="report files missing the header and exit 1; write nothing",
    )
    args = parser.parse_args()

    files = in_scope()
    missing = [
        (path, prefix)
        for path, prefix in files
        if not has_header((REPO_ROOT / path).read_text(encoding="utf-8"))
    ]

    if args.check:
        for path, _ in missing:
            print(f"missing header: {path}")
        print(f"\n{len(files) - len(missing)}/{len(files)} in-scope files carry the header.")
        return 1 if missing else 0

    changed = [path for path, prefix in missing if add_header(path, prefix)]
    for path in changed:
        print(f"added: {path}")
    print(f"\n{len(changed)} file(s) updated; {len(files)} in scope.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
