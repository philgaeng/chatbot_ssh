# SPDX-License-Identifier: Apache-2.0

"""Re-run the repository's hand-authored mutation checks.

A mutation check is the answer to *"can this test go red?"* — the specific edit to production
code that a test must catch. This repository has been making them by hand since Sprint 3 and
recording them as prose in `docs/sprints/2026-08-llm/TESTS.md`, which meant nobody could re-run
one, a test that STOPPED catching its mutation went unnoticed, and a reviewer could not verify
any of them. This script turns the record into data and the claim into a command.

    python scripts/ops/run_mutations.py                    # every record
    python scripts/ops/run_mutations.py --module test_pii_service
    python scripts/ops/run_mutations.py --id T-31-e-global-counter
    python scripts/ops/run_mutations.py --list             # no edits, no test runs

Records live in `tests/mutations/*.yml`, one file per test module::

    - id: T-31-e-global-counter
      target: backend/services/pii_service.py
      find: "    counters: dict[str, int] = {}"
      replace: '    counters: dict[str, int] = globals().setdefault("_MUTANT_COUNTERS", {})'
      tests: tests/backend/test_pii_service.py
      expect: kills            # `survives` is equally valid and MUST carry a `why`
      min_failures: 3          # optional — the ledger's "3 red", asserted
      why: >
        Two concurrent grievances must not share <PERSON_1>.

⭐ ``expect: survives`` is a first-class outcome, not an exception. Some mutations *should*
survive — T-31-a is the worked example: the dual-script digit class is redundant because
`find_pii` normalises centrally, so removing it changes no behaviour. A runner that demanded
every mutation kill would force someone to delete a useful safety net or fake the record. So the
runner asserts the RECORDED EXPECTATION, and a `survives` record without a `why` explaining what
*does* kill is rejected before anything runs.

⚠ **NOT wired into CI, deliberately.** Every mutation is a full suite run, and a slow gate is the
gate nobody watches — this repository learned that expensively under D-26, when CI was red for ten
days and indistinguishable from a build nobody was looking at. Run this before a release, or when
touching a pinned invariant. Revisit CI only once the runtime is known and only for the host
records; the container ones need a live Compose stack, which CI does not have.

⚠ **Restores with git, never with a copy in /tmp.** A runner that dies mid-run must not leave the
tree mutated, so host targets are restored with `git checkout --` in a `finally` and the restore
is verified. That is only safe while the target file has no uncommitted work, hence the clean-tree
refusal below: `--allow-dirty` tolerates unrelated edits but still refuses when a file a record
mutates is itself dirty, because there the restore would destroy work.

⚠ **Some suites only run in a container.** `backend/services/llm_client.py` and
`ticketing/clients/llm_client.py` import the OpenAI SDK at module level and `openai` is not
installed on the host. Those records carry `runner: container` plus a `container:` name; the file
is copied in with `docker cp`, pytest runs inside, and the container's ORIGINAL bytes — snapshotted
before the mutation, not assumed equal to the host's — are copied back. This avoids a ~90 s image
rebuild per mutation, which would make a 25-mutation run unusable.
"""

from __future__ import annotations

import argparse
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RECORDS_DIR = REPO_ROOT / "tests" / "mutations"

KILLS = "kills"
SURVIVES = "survives"
VALID_EXPECT = {KILLS, SURVIVES}

# pytest's documented exit codes. Anything outside 0/1 means the mutation did not produce a test
# result at all — a syntax error, a collection failure, an empty selection — and that is a
# BROKEN RECORD, never a kill. Counting a collection error as "the test caught it" is exactly the
# false confidence this script exists to remove.
PYTEST_ALL_PASSED = 0
PYTEST_TESTS_FAILED = 1


class RecordError(Exception):
    """A record is malformed, or its `find` does not address the target exactly once."""


@dataclass
class Record:
    id: str
    target: str
    find: str
    replace: str
    tests: str
    expect: str
    why: str
    source_file: Path
    runner: str = "host"
    container: Optional[str] = None
    min_failures: Optional[int] = None
    note: Optional[str] = None


@dataclass
class Outcome:
    record: Record
    observed: str                 # "kills" | "survives" | "broken"
    failures: Optional[int]
    exit_code: int
    detail: str = ""
    tail: str = ""

    @property
    def diverged(self) -> bool:
        if self.observed == "broken":
            return True
        if self.observed != self.record.expect:
            return True
        if (
            self.record.expect == KILLS
            and self.record.min_failures is not None
            and (self.failures is None or self.failures < self.record.min_failures)
        ):
            return True
        return False


# ── Loading and validation ───────────────────────────────────────────────────


def load_records(paths: list[Path]) -> list[Record]:
    records: list[Record] = []
    seen: dict[str, Path] = {}
    for path in sorted(paths):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        if not isinstance(raw, list):
            raise RecordError(f"{path.name}: expected a list of records, got {type(raw).__name__}")
        for index, entry in enumerate(raw):
            record = _validate(entry, path, index)
            if record.id in seen:
                raise RecordError(
                    f"duplicate record id {record.id!r} in {path.name} and {seen[record.id].name} "
                    "— ids are how TESTS.md cross-references a record, so they must be unique"
                )
            seen[record.id] = path
            records.append(record)
    return records


def _validate(entry: Any, path: Path, index: int) -> Record:
    where = f"{path.name}[{index}]"
    if not isinstance(entry, dict):
        raise RecordError(f"{where}: expected a mapping, got {type(entry).__name__}")

    required = ("id", "target", "find", "replace", "tests", "expect", "why")
    missing = [k for k in required if not str(entry.get(k, "")).strip()]
    if missing:
        raise RecordError(f"{where}: missing or empty field(s): {', '.join(missing)}")

    expect = str(entry["expect"]).strip()
    if expect not in VALID_EXPECT:
        raise RecordError(
            f"{where} ({entry['id']}): expect must be one of {sorted(VALID_EXPECT)}, got {expect!r}"
        )

    # ⭐ The rule that keeps a documented non-kill honest rather than decorative. A `survives`
    # record is a claim that a test SHOULD NOT catch this edit, which is only meaningful with the
    # reason attached — and the reason has to name what does kill, or the record is an excuse.
    why = str(entry["why"]).strip()
    if expect == SURVIVES and len(why) < 40:
        raise RecordError(
            f"{where} ({entry['id']}): `expect: survives` needs a `why` that explains what DOES "
            "kill. A non-kill with no explanation is indistinguishable from a test that quietly "
            "stopped working."
        )

    runner = str(entry.get("runner", "host")).strip()
    if runner not in {"host", "container"}:
        raise RecordError(f"{where} ({entry['id']}): runner must be 'host' or 'container'")
    container = entry.get("container")
    if runner == "container" and not container:
        raise RecordError(
            f"{where} ({entry['id']}): runner: container needs a `container:` name — the record "
            "has to say WHERE it ran, or it cannot be reproduced"
        )

    min_failures = entry.get("min_failures")
    if min_failures is not None:
        if expect != KILLS:
            raise RecordError(f"{where} ({entry['id']}): min_failures only applies to expect: kills")
        min_failures = int(min_failures)

    target = REPO_ROOT / str(entry["target"])
    if not target.is_file():
        raise RecordError(f"{where} ({entry['id']}): target does not exist: {entry['target']}")

    return Record(
        id=str(entry["id"]).strip(),
        target=str(entry["target"]).strip(),
        find=str(entry["find"]),
        replace=str(entry["replace"]),
        tests=str(entry["tests"]).strip(),
        expect=expect,
        why=why,
        source_file=path,
        runner=runner,
        container=str(container).strip() if container else None,
        min_failures=min_failures,
        note=(str(entry["note"]).strip() if entry.get("note") else None),
    )


def apply_once(content: str, record: Record) -> str:
    """Substitute `find` → `replace`, asserting the anchor addresses exactly one place.

    ⚠ An ambiguous anchor is the trap this repository already hit from the other side: a
    source-level pin flagged its own explanatory COMMENT, because the comment spelled the banned
    string. A `find` can just as easily match a docstring, a second call site, or the record's own
    prose — and a mutation applied in two places is testing something nobody wrote down.
    """
    occurrences = content.count(record.find)
    if occurrences != 1:
        raise RecordError(
            f"{record.id}: `find` occurs {occurrences} times in {record.target} (need exactly 1). "
            + (
                "The anchor is stale — the code moved or was rewritten, which is itself a finding: "
                "re-derive it from the current source rather than loosening it."
                if occurrences == 0
                else "The anchor is ambiguous. Extend it with indentation and surrounding syntax "
                "until it addresses one place; it may also be matching a comment or a docstring."
            )
        )
    return content.replace(record.find, record.replace, 1)


# ── Git guards ───────────────────────────────────────────────────────────────


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )


def dirty_paths() -> tuple[set[str], set[str]]:
    """(tracked-but-modified, untracked) working-tree paths.

    ⚠ The two are separated because only the first can be DESTROYED by the restore. `git checkout
    -- <path>` overwrites a modified tracked file and ignores everything else, so untracked files
    are reported but never block a run. Blocking on them would fire on this script's own record
    files before they are committed, and a guard that always fires is a guard people learn to pass
    `--allow-dirty` to — which is D-26's lesson in miniature.
    """
    out = _git("status", "--porcelain")
    if out.returncode != 0:
        raise RecordError(f"git status failed — is this a git checkout?\n{out.stderr}")
    modified: set[str] = set()
    untracked: set[str] = set()
    for line in out.stdout.splitlines():
        if not line.strip():
            continue
        status, entry = line[:2], line[3:]
        # Renames read "old -> new"; both sides matter for a restore.
        parts = {p.strip().strip('"') for p in entry.split(" -> ")}
        (untracked if status == "??" else modified).update(parts)
    return modified, untracked


def restore_host_file(target: str) -> None:
    """Put a mutated file back, and prove it went back.

    `git checkout --` rather than a copy in /tmp: the copy is what the by-hand method used, and a
    run killed between the edit and the copy-back leaves the tree silently mutated.
    """
    result = _git("checkout", "--", target)
    if result.returncode != 0:
        raise RecordError(
            f"COULD NOT RESTORE {target} — the working tree is left mutated. "
            f"Run `git checkout -- {target}` by hand.\n{result.stderr}"
        )
    modified, _ = dirty_paths()
    if target in modified:
        raise RecordError(f"restore of {target} did not clean it — the tree is left mutated")


# ── Running ──────────────────────────────────────────────────────────────────


def _summarise(stdout: str) -> tuple[Optional[int], str]:
    """(failure count, last non-empty line) from a `pytest -q` run."""
    lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
    tail = lines[-1] if lines else ""
    failures = None
    # "3 failed, 35 passed in 0.31s" — read the number in front of `failed`, wherever it sits.
    words = tail.replace(",", " ").split()
    for i, word in enumerate(words):
        if word.startswith("failed") and i > 0 and words[i - 1].isdigit():
            failures = int(words[i - 1])
    return failures, tail


def _classify(exit_code: int, stdout: str) -> tuple[str, Optional[int], str]:
    failures, tail = _summarise(stdout)
    if exit_code == PYTEST_ALL_PASSED:
        return SURVIVES, failures, tail
    if exit_code == PYTEST_TESTS_FAILED:
        return KILLS, failures, tail
    return "broken", failures, tail


def run_host(record: Record, verbose: bool) -> Outcome:
    target = REPO_ROOT / record.target
    original = target.read_text(encoding="utf-8")
    mutated = apply_once(original, record)   # raises before anything is written

    try:
        target.write_text(mutated, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", record.tests, "-q", "--no-header", "-p", "no:cacheprovider"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=False,
        )
    finally:
        restore_host_file(record.target)

    observed, failures, tail = _classify(proc.returncode, proc.stdout)
    detail = "" if observed != "broken" else _broken_detail(proc)
    return Outcome(record, observed, failures, proc.returncode, detail, tail)


def _docker(*args: str, **kwargs: Any) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=False, **kwargs)


def run_container(record: Record, verbose: bool) -> Outcome:
    """Mutate a file INSIDE a container, run the suite there, put the original back.

    The host tree is never touched by a container record — the mutation is built from the bytes
    the container is actually running, which are snapshotted first rather than assumed equal to
    the host's. If the image is stale the `find` will not match, and that mismatch is a finding
    ("rebuild before trusting this run"), not something to paper over.
    """
    name = record.container or ""
    if _docker("inspect", "-f", "{{.State.Running}}", name).stdout.strip() != "true":
        return Outcome(
            record, "broken", None, -1,
            detail=(f"container {name!r} is not running. Start the stack (`make wsl-up`) or run "
                    f"with --skip-container."),
        )

    remote = f"/app/{record.target}"
    with tempfile.TemporaryDirectory() as tmp:
        pristine = Path(tmp) / "pristine"
        mutant = Path(tmp) / "mutant"

        got = _docker("cp", f"{name}:{remote}", str(pristine))
        if got.returncode != 0:
            return Outcome(record, "broken", None, -1,
                           detail=f"could not read {remote} from {name}: {got.stderr.strip()}")

        original = pristine.read_text(encoding="utf-8")
        mutant.write_text(apply_once(original, record), encoding="utf-8")   # raises before any cp

        try:
            put = _docker("cp", str(mutant), f"{name}:{remote}")
            if put.returncode != 0:
                return Outcome(record, "broken", None, -1,
                               detail=f"could not write {remote} to {name}: {put.stderr.strip()}")
            proc = _docker(
                "exec", name, "python", "-m", "pytest", record.tests,
                "-q", "--no-header", "-p", "no:cacheprovider",
            )
        finally:
            back = _docker("cp", str(pristine), f"{name}:{remote}")
            if back.returncode != 0:
                raise RecordError(
                    f"COULD NOT RESTORE {remote} in {name} — the container is left mutated. "
                    f"Recreate it (`docker compose up -d --force-recreate {name}`).\n{back.stderr}"
                )

    observed, failures, tail = _classify(proc.returncode, proc.stdout)
    detail = "" if observed != "broken" else _broken_detail(proc)
    return Outcome(record, observed, failures, proc.returncode, detail, tail)


def _broken_detail(proc: subprocess.CompletedProcess) -> str:
    body = (proc.stdout or "") + (proc.stderr or "")
    lines = [ln for ln in body.splitlines() if ln.strip()]
    return "\n".join(f"      | {ln}" for ln in lines[-12:])


# ── CLI ──────────────────────────────────────────────────────────────────────


def _install_signal_restore() -> None:
    """Turn SIGTERM into an exception so the `finally` blocks above still run.

    SIGINT already raises KeyboardInterrupt. SIGKILL cannot be caught — a run killed with -9 can
    leave a mutation behind, which is why the next run refuses to start on a dirty tree.
    """
    def _raise(signum, _frame):
        raise SystemExit(f"interrupted by signal {signum}; restoring")

    signal.signal(signal.SIGTERM, _raise)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Re-run the repository's hand-authored mutation checks.",
        epilog="Exits non-zero ONLY when an outcome diverges from the record's `expect`.",
    )
    parser.add_argument("--module", action="append", default=[],
                        help="record file stem, e.g. test_pii_service (repeatable)")
    parser.add_argument("--id", action="append", default=[], help="single record id (repeatable)")
    parser.add_argument("--list", action="store_true", help="list records and exit; runs nothing")
    parser.add_argument("--skip-container", action="store_true",
                        help="skip records needing a running container")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="tolerate unrelated uncommitted work; still refuses when a file a "
                             "record MUTATES is dirty, because there the restore destroys it")
    parser.add_argument("-v", "--verbose", action="store_true", help="print each suite's tail")
    args = parser.parse_args(argv)

    files = sorted(RECORDS_DIR.glob("*.yml"))
    if args.module:
        wanted = {m.removesuffix(".yml") for m in args.module}
        files = [f for f in files if f.stem in wanted]
    if not files:
        print(f"no record files matched under {RECORDS_DIR.relative_to(REPO_ROOT)}", file=sys.stderr)
        return 4

    try:
        records = load_records(files)
    except RecordError as exc:
        print(f"✗ invalid record: {exc}", file=sys.stderr)
        return 4

    if args.id:
        wanted_ids = set(args.id)
        unknown = wanted_ids - {r.id for r in records}
        if unknown:
            print(f"✗ unknown record id(s): {', '.join(sorted(unknown))}", file=sys.stderr)
            return 4
        records = [r for r in records if r.id in wanted_ids]

    if args.list:
        for record in records:
            where = record.runner if record.runner == "host" else f"container:{record.container}"
            print(f"{record.id:<44} {record.expect:<9} {where:<28} {record.target}")
        print(f"\n{len(records)} record(s) in {len(files)} file(s)")
        return 0

    skipped_container = 0
    if args.skip_container:
        before = len(records)
        records = [r for r in records if r.runner == "host"]
        skipped_container = before - len(records)

    # ── The clean-tree refusal (see the module docstring) ─────────────────────
    modified, untracked = dirty_paths()
    mutated_targets = {r.target for r in records}
    at_risk = sorted((modified | untracked) & mutated_targets)
    if at_risk:
        print("✗ refusing to run: these files are mutated by a record AND have uncommitted work.\n"
              "  The restore is `git checkout --`, which would overwrite that work (or fail\n"
              "  outright on an untracked file, leaving the mutation in place):\n"
              + "".join(f"    {p}\n" for p in at_risk)
              + "  Commit or stash them, or select other records with --module/--id.",
              file=sys.stderr)
        return 4
    if modified and not args.allow_dirty:
        print(f"✗ refusing to run on a dirty tree — {len(modified)} tracked file(s) modified:\n"
              + "".join(f"    {p}\n" for p in sorted(modified)[:10])
              + "  Commit or stash first. No file a record mutates is among them, so\n"
              "  --allow-dirty is safe here; the restore cannot reach these.", file=sys.stderr)
        return 4

    _install_signal_restore()

    print(f"Running {len(records)} mutation(s)\n")
    outcomes: list[Outcome] = []
    try:
        for index, record in enumerate(records, 1):
            where = "host" if record.runner == "host" else f"in {record.container}"
            print(f"[{index}/{len(records)}] {record.id}  ({record.expect}, {where})", flush=True)
            try:
                run = run_host if record.runner == "host" else run_container
                outcome = run(record, args.verbose)
            except RecordError as exc:
                outcome = Outcome(record, "broken", None, -1, detail=f"      | {exc}")
            outcomes.append(outcome)

            mark = "✓" if not outcome.diverged else "✗"
            counted = f", {outcome.failures} failed" if outcome.failures else ""
            print(f"    {mark} {outcome.observed}{counted}"
                  + (f"   [{outcome.tail}]" if args.verbose and outcome.tail else ""))
            if outcome.detail:
                print(outcome.detail)
    except (KeyboardInterrupt, SystemExit) as exc:
        # The per-record `finally` has already restored; say so plainly rather than leaving the
        # operator to wonder whether the tree is clean.
        print(f"\n⚠ interrupted ({exc or 'KeyboardInterrupt'}). "
              f"{len(outcomes)} record(s) completed; the tree was restored after each.",
              file=sys.stderr)
        left = dirty_paths()[0] & mutated_targets
        print("  tree is clean." if not left else f"  ⚠ STILL MUTATED: {sorted(left)}",
              file=sys.stderr)
        return 130

    diverged = [o for o in outcomes if o.diverged]
    print(f"\n{'─' * 72}")
    print(f"{len(outcomes)} checked · {len(outcomes) - len(diverged)} as recorded · "
          f"{len(diverged)} diverged"
          + (f" · {skipped_container} container record(s) skipped" if skipped_container else ""))

    if diverged:
        print("\nDiverged from the record — each of these is a finding, not a nuisance:")
        for outcome in diverged:
            if outcome.observed == "broken":
                reason = "the record is broken — no test result was produced"
            elif outcome.observed != outcome.record.expect:
                reason = f"expected {outcome.record.expect}, observed {outcome.observed}"
            else:
                reason = (f"killed {outcome.failures} test(s), record says at least "
                          f"{outcome.record.min_failures}")
            print(f"  ✗ {outcome.record.id}  ({outcome.record.source_file.name})")
            print(f"      {reason}")
            print(f"      target: {outcome.record.target} · tests: {outcome.record.tests}")
        print("\nA record that no longer reproduces means one of two things, and both are worth "
              "knowing:\n  the test stopped catching its mutation, or the original claim was "
              "wrong. Write it up;\n  do not quietly adjust the record to match what you just saw.")
        return 1

    print("\nEvery mutation behaved as recorded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
