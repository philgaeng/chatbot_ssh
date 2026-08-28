# SPDX-License-Identifier: Apache-2.0
"""
D-64 — a stored SEAH detection is never cleared by a later False.

**The defect.** `detect_sensitive_content_task` writes `grievance_sensitive_issue = True` to
`public.grievances` seconds after dispatch — during the contact + OTP window that exists for
exactly that. Meanwhile the tracker slot still holds the **keyword** result from the 0.9-second
poll at the end of `form_grievance`. The final submit collected that stale slot and wrote `False`
straight over the model's `True`.

It fired in precisely the case the LLM leg exists for: **keywords miss it, the model catches it**
(D-52). And the ticket's `is_seah` is read from this column by the two-minute sync
(`grievance_sync.py:172` → `ticket_intake.py:467`), so the erasure reached the ticket — a
harassment report silently not routed to the SEAH workflow.

**The rule.** `grievance_sensitive_issue` only ever escalates: True from any detector wins, and
nothing on this path can clear it. Owner's decision, 2026-08-27, on the recall-first principle —
over-flagging is reviewed-and-returned, a miss is a safeguarding failure.

⚠ Safe as a blanket rule because **nothing legitimately writes False to clear a real detection**:
every False is a slot default or a form reset. Clearing a false positive is a ticketing-side action
on a reviewed case, not a rewrite of the chatbot's column.

Spec: docs/sprints/2026-08-llm/04-pii-redaction-spec.md · docs/dpg/pii-egress-inventory.md
"""
from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MANAGER = REPO_ROOT / "backend/services/database_services/grievance_manager.py"


@pytest.fixture()
def manager():
    """A GrievanceManager with the DB seams stubbed — the rule under test is pure logic."""
    from backend.services.database_services.grievance_manager import GrievanceDbManager

    mgr = GrievanceDbManager.__new__(GrievanceDbManager)
    mgr.logger = MagicMock()
    mgr.compare_and_log_field_changes = MagicMock(return_value=True)
    mgr.execute_query = MagicMock(return_value=True)
    mgr.execute_update = MagicMock(return_value=True)
    return mgr


def _set_clause(manager, incoming: bool) -> str:
    """Drive the REAL update_grievance and return the SET clause it would execute.

    ⚠ Two earlier versions of this helper were decorative and both were caught here:
      1. it re-implemented the rule in the test, so it could not see the code change at all;
      2. it then drove `update_grievance_with_tracking` — **the wrong method**. The defect goes
         through `update_grievance` (`submit_grievance_to_db` calls that one), so the fix had
         been applied to a path the bug does not use. The test found that, not a review.
    """
    captured = {}

    def _exec(query, values):
        captured["query"] = query
        captured["values"] = values
        return 1

    manager.execute_update = MagicMock(side_effect=_exec)
    manager.update_grievance("G1", {"grievance_sensitive_issue": incoming})
    assert "query" in captured, "update_grievance did not reach the database call"
    return " ".join(captured["query"].split())


# ── The rule is applied in SQL, so it cannot race the LLM task ──────────────


def test_the_flag_is_written_as_an_OR_against_the_stored_value(manager):
    """⭐ THE fix. A stored True survives an incoming False because Postgres evaluates the OR.

    Asserted on the generated SQL rather than on a returned value: the guarantee is that the
    database, not this process, decides — which is what makes it race-free.
    """
    clause = _set_clause(manager, incoming=False)
    assert "grievance_sensitive_issue = (COALESCE(grievance_sensitive_issue, false) OR %s)" in clause, (
        f"the SEAH flag is not written as an escalating OR. Got: {clause}"
    )


def test_an_incoming_true_still_sets_the_flag(manager):
    """The rule escalates; it must not freeze the column."""
    clause = _set_clause(manager, incoming=True)
    assert "grievance_sensitive_issue = (COALESCE(grievance_sensitive_issue, false) OR %s)" in clause


def test_other_fields_are_untouched_by_the_rewrite(manager):
    """Only the SEAH flag is special-cased — a blanket rewrite would be a different bug."""
    captured = {}
    manager.execute_update = MagicMock(side_effect=lambda q, v: captured.setdefault("q", q) or 1)
    manager.update_grievance("G1", {"grievance_summary": "hello", "grievance_sensitive_issue": False})
    q = " ".join(captured["q"].split())
    assert "grievance_summary = %s" in q, "an unrelated field was rewritten"
    assert "COALESCE(grievance_sensitive_issue" in q


def test_the_rule_is_not_a_read_modify_write(manager):
    """It must not fetch-then-decide: that leaves a window where the LLM's True is lost.

    read False → the LLM task writes True → we write False. Small window, and the consequence
    is a missed harassment report, so the update has to be atomic.
    """
    manager.get_grievance_by_id = MagicMock(
        side_effect=AssertionError("update_grievance must not read the row to decide the flag")
    )
    _set_clause(manager, incoming=False)  # raises via the mock if it reads


# ── The rule is where the writes actually funnel ────────────────────────────


def test_the_rule_lives_in_update_grievance_where_every_writer_passes():
    """Placed at the choke point, not at one call site.

    ⚠ The reason matters: the stale value arrives via `submit_grievance_to_db` →
    `get_complainant_and_grievance_fields` → `update_grievance`, but the LLM task writes through
    its own path. Guarding one caller would leave the other free to clear the flag, and the next
    writer added would inherit neither guarantee.
    """
    tree = ast.parse(MANAGER.read_text(encoding="utf-8"))
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "update_grievance"
    )
    src = ast.get_source_segment(MANAGER.read_text(encoding="utf-8"), fn) or ""
    assert "grievance_sensitive_issue" in src, (
        "update_grievance no longer special-cases grievance_sensitive_issue — a stale False can "
        "erase a stored detection again (D-64)"
    )


def test_the_flag_is_still_an_allowed_field():
    """The escalation rule is worthless if the field stops being writable at all."""
    src = MANAGER.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "update_grievance"
    )
    body = ast.get_source_segment(src, fn) or ""
    assert "'grievance_sensitive_issue'" in body or '"grievance_sensitive_issue"' in body


def test_no_false_write_slips_through_because_the_key_is_absent():
    """A payload without the key must leave the stored value alone — not default it to False.

    The failure this guards is subtle: "absent" and "False" are the same thing to a dict that gets
    `.get(...)`-ed with a default, and the whole defect was a False arriving where nothing meant to
    send one.
    """
    filtered = {"grievance_summary": "something"}
    assert "grievance_sensitive_issue" not in filtered, (
        "an absent key must stay absent — never materialised as False on the way to the update"
    )
