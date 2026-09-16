# SPDX-License-Identifier: Apache-2.0
"""
DPG-34 step 3 — the grievance narrative is not serialised into the broker.

**The finding this exists for (D-63).** `input_data["values"]["grievance_description"]` went into
Redis on every intake, and Redis turned out to persist: no volume, but RDB snapshotting on the
compiled-in defaults, writing `/data/dump.rdb` in the container's writable layer. Measured
2026-08-27 — a planted key survived `docker restart` with *"DB loaded from disk: keys loaded: 174"*.
So the broker held grievance narratives **at rest**, unencrypted, in a store nothing backs up and no
retention policy names.

**The fix removes the store rather than obscuring it.** The task receives `grievance_id` and reads
the text from Postgres. Safe because `create_or_update_grievance` in `intake_submit.py` is a hard
write on the submit path and runs *before* the trigger.

⚠ **Why this is a source-level pin.** The property is about what is *absent* from a dict that is
built and immediately handed to `.delay()`. A behavioural test would have to stand up a broker and
inspect a serialised message; this asserts the same thing where it is decided, and fails loudly if
someone re-adds the key to "save a query".

Spec: docs/sprints/2026-08-llm/04-pii-redaction-spec.md §DPG-34
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLASSIFICATION = REPO_ROOT / "backend/actions/grievance_intake/classification.py"
TASKS = REPO_ROOT / "backend/task_queue/registered_tasks.py"


def _dispatch_payload_keys() -> set[str]:
    """Keys of the dict literal that is passed to classify_and_summarize_grievance_task.delay()."""
    tree = ast.parse(CLASSIFICATION.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict)):
            continue
        targets = {t.id for t in node.targets if isinstance(t, ast.Name)}
        if "input_data" in targets:
            return {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
    raise AssertionError("no `input_data = {...}` literal found in classification.py")


def test_the_dispatch_payload_does_not_carry_the_narrative():
    keys = _dispatch_payload_keys()

    assert "values" not in keys, (
        "classification.py puts `values` back into the Celery payload. That is where the grievance "
        "narrative used to travel into Redis, which persists to disk (D-63). The task reads the "
        "text from Postgres by grievance_id — do not re-add it to save a query."
    )
    assert "grievance_description" not in keys, (
        "the narrative must not be sent to the broker under any key"
    )


def test_the_payload_still_carries_the_id_the_task_reads_by():
    """The other half: removing the text is only safe while the id travels."""
    keys = _dispatch_payload_keys()
    assert "grievance_id" in keys, (
        "without grievance_id the task cannot read the narrative from Postgres, and removing it "
        "from the payload would silently break classification rather than secure it"
    )


def test_the_task_reads_the_narrative_from_the_database():
    """The task must resolve the text from Postgres, not only from what it was handed."""
    src = TASKS.read_text(encoding="utf-8")
    tree = ast.parse(src)

    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "classify_and_summarize_grievance_task"
    )
    calls = {
        node.func.attr
        for node in ast.walk(fn)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "get_grievance_core_by_id" in calls, (
        "classify_and_summarize_grievance_task no longer reads the grievance from the database. "
        "If the narrative is not read, it must be being received — which is the leak this closed."
    )


def test_the_task_uses_the_core_accessor_not_the_pii_joining_one():
    """`get_grievance_core_by_id` reads `grievances` only.

    ⚠ Not a style preference. `get_grievance_by_id` JOINs `complainants` and decrypts the four
    contact fields, so using it here would pull complainant PII into a worker that has no use for
    it — trading one exposure for a wider one while looking like a fix.
    """
    src = TASKS.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "classify_and_summarize_grievance_task"
    )
    calls = {
        node.func.attr
        for node in ast.walk(fn)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "get_grievance_by_id" not in calls, (
        "use get_grievance_core_by_id: the PII-joining accessor decrypts complainant contact "
        "fields this task never needs"
    )


def test_no_task_error_path_interpolates_the_whole_payload():
    """Errors name the id and the key shape — never the payload, which held the narrative.

    Three sites in this task used to do it: a `print` of `input_data`, a missing-session_id
    ValueError, and a missing-text ValueError that dumped `input_data["values"]`. They fire exactly
    when something is already wrong, which is when logs get read, copied and pasted.
    """
    src = TASKS.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "classify_and_summarize_grievance_task"
    )

    offenders: list[int] = []
    for node in ast.walk(fn):
        # Any f-string or logging/raise argument that interpolates `input_data` wholesale.
        if isinstance(node, ast.JoinedStr):
            for value in node.values:
                if not isinstance(value, ast.FormattedValue):
                    continue
                inner = value.value
                if isinstance(inner, ast.Name) and inner.id == "input_data":
                    offenders.append(node.lineno)

    assert not offenders, (
        f"the whole input_data payload is interpolated into a message at line(s) {offenders}. "
        "Name grievance_id and sorted(input_data.keys()) instead."
    )


def test_registered_tasks_does_not_print_at_all():
    """`print` in a Celery task goes to stdout and into the container logs, unfiltered.

    Five were removed: one dumped the whole task payload (narrative included) on every intake, and
    **four identical copies** printed `db_result`, whose `values` carry `grievance_description` and
    `grievance_summary` — the narrative *and* the generated summary, on every success.

    ⚠ **Module-wide, not scoped to one task, and a mutation is why.** The first version of this test
    guarded only `classify_and_summarize_grievance_task`; restoring a print in one of the other three
    left it green. Three of those tasks are on parked paths (transcription, contact extraction,
    translation) and would leak identically the day they unpark — the defect is the shape, not the
    function.

    ⚠ And a `print` is invisible to any logging filter DPG-34 installs later, which is what makes it
    worth banning outright rather than fixing case by case.
    """
    tree = ast.parse(TASKS.read_text(encoding="utf-8"))
    prints = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print"
    ]
    assert not prints, (
        f"print() at line(s) {prints} in registered_tasks.py — use the module logger, which a "
        "logging filter can reach and a print cannot"
    )


# ═════════════════════════════════════════════════════════════════════════════
# The SEAH half — same fix, different risk, so a different failure mode
#
# Classification's pre-dispatch write is HARD (create_or_update_grievance in
# intake_submit.py raises). SEAH's is BEST-EFFORT: persist_grievance_description_for_detection
# returns early without grievance_id/complainant_id and swallows DB exceptions, while the
# dispatch happens regardless of either. So a missing row is REACHABLE here, and reading from
# the DB without handling it would convert a best-effort write into a silently skipped
# safeguarding check.
# ═════════════════════════════════════════════════════════════════════════════

SENSITIVE = REPO_ROOT / "backend/actions/grievance_intake/sensitive.py"


def _seah_task() -> ast.FunctionDef:
    tree = ast.parse(TASKS.read_text(encoding="utf-8"))
    return next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "detect_sensitive_content_task"
    )


def test_the_seah_dispatch_does_not_send_the_narrative():
    """`text=` must not be passed to .delay() — that is what put disclosures in Redis."""
    tree = ast.parse(SENSITIVE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "delay":
            continue
        kwargs = {kw.arg for kw in node.keywords}
        assert "text" not in kwargs, (
            "sensitive.py sends `text=` to the SEAH task again. That serialises the grievance "
            "narrative — harassment disclosures included — into Redis, which persists to disk "
            "(D-63). The task reads it from Postgres by grievance_id."
        )
        assert "grievance_id" in kwargs, (
            "the SEAH task cannot read the narrative without grievance_id"
        )
        return
    raise AssertionError("no .delay() call found in sensitive.py")


def test_the_seah_task_reads_the_narrative_from_the_database():
    calls = {
        n.func.attr for n in ast.walk(_seah_task())
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    }
    assert "get_grievance_core_by_id" in calls, (
        "detect_sensitive_content_task must read the narrative from Postgres"
    )
    assert "get_grievance_by_id" not in calls, (
        "use the core accessor — the PII-joining one decrypts contact fields this task never needs"
    )


def test_a_missing_row_retries_rather_than_skipping_the_check():
    """⭐ The property that makes reading-from-DB safe on a safeguarding path.

    The pre-dispatch write is best-effort, so "no row" is reachable. Retrying gives it time to
    land; skipping would drop the LLM SEAH signal with nothing anywhere recording that it
    happened.
    """
    fn = _seah_task()
    retries = [
        n for n in ast.walk(fn)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "retry"
    ]
    assert retries, (
        "detect_sensitive_content_task no longer retries. On this path a missing row is "
        "reachable (the pre-dispatch write is best-effort), so no retry means a silently "
        "skipped harassment check."
    )


def test_exhausted_retries_fail_LOUDLY_at_error_level():
    """A SEAH detection that never ran is invisible everywhere else — so it must be loud here.

    No flag is written, nothing shows a gap, and the ticket is simply not marked sensitive. This
    log line is the only artefact that the second signal did not run.
    """
    fn = _seah_task()
    error_logs = [
        n for n in ast.walk(fn)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "error"
    ]
    assert error_logs, (
        "the terminal no-text path must log at ERROR. At INFO or WARNING it is one line among "
        "thousands, and a missed safeguarding signal is the thing you most need to find later."
    )


def test_the_model_selected_excerpt_is_never_logged():
    """⭐ `message` is not free text under the 8-character rule, and the distinction matters.

    The prompt asks for *"a short excerpt of the relevant part of the text"* — so `message` is the
    fragment the model chose BECAUSE it is the harassment disclosure. A prefix of it is a prefix
    of the most sensitive string the system produces. `detected` and `level` carry the diagnostic
    signal; the excerpt adds nothing its length does not.
    """
    fn = _seah_task()
    for node in ast.walk(fn):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in {"info", "debug", "warning", "error"}:
            continue
        for arg in node.args:
            # `message` reaching a log call is only acceptable inside text_len_for_log(...)
            for sub in ast.walk(arg):
                if isinstance(sub, ast.Name) and sub.id == "message":
                    assert _inside_len_helper(arg, sub), (
                        f"line {node.lineno}: the model-selected excerpt `message` reaches a log "
                        "call. Log its LENGTH (text_len_for_log), never its content — not even a "
                        "prefix."
                    )


def _inside_len_helper(root: ast.AST, target: ast.Name) -> bool:
    for sub in ast.walk(root):
        if (
            isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Name)
            and sub.func.id in {"text_len_for_log", "len"}
            and any(n is target for n in ast.walk(sub))
        ):
            return True
    return False
