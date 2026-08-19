# SPDX-License-Identifier: Apache-2.0

"""
A closure document reaches the complainant even when the model does not — D-36.

**The defect.** `generate_resolved_case_summary` notified the complainant only when
`generation_status == "complete"`, and the public closure route served the document only under the
same condition. When the model returned nothing, both gates closed: the person was told their case
was resolved (that notification comes from the resolve action) and then never received the outcome
— and nothing retried the document, so it stayed unbuilt permanently.

**Why that is the wrong question.** `build_public_summary_json` produces the entire deterministic
record without any model: the reference number, the filing and resolution dates, how long it took,
who resolved it, the original complaint, the resolution category, and — the part that says what was
actually decided — **the officer's own resolution text**. Only the AI-written investigation
narrative is missing. Withholding all of that because a model was unavailable is a worse outcome
than publishing a document with one section absent.

So publishability became a property of the **document**: is there a resolution the person can read?

Spec: docs/sprints/2026-08-llm/followups/llm-failed-is-unreachable-and-the-closure-doc-never-retries.md
"""
from __future__ import annotations

import inspect

from ticketing.api.routers import public_closure
from ticketing.services import resolved_summary_builder as builder


class _Row:
    def __init__(self, payload, status="llm_failed"):
        self.summary_public_json = payload
        self.generation_status = status


def test_a_document_with_a_resolution_is_publishable_whatever_the_model_did():
    """⭐ The fix, in one assertion: the gate reads the document, not the generation status."""
    assert public_closure._is_publishable(
        _Row({"resolution_text_public": "The contractor must wet-spray twice daily."})
    )
    # …and the same document is publishable when the AI narrative did arrive.
    assert public_closure._is_publishable(
        _Row({"resolution_text_public": "…", "findings_summary_public": "…"}, status="complete")
    )


def test_a_document_with_nothing_to_read_is_still_withheld():
    """The gate loosened; it did not disappear. An empty record is not a closure document."""
    assert not public_closure._is_publishable(_Row({}, status="complete"))
    assert not public_closure._is_publishable(_Row({"resolution_text_public": ""}))
    assert not public_closure._is_publishable(_Row(None, status="complete"))


def test_neither_public_route_gates_on_the_generation_status_any_more():
    """
    Both routes — the JSON one the complainant's page calls, and the PDF one — asked
    `generation_status != "complete"`. Either one left behind reintroduces the 404.
    """
    for route in (public_closure.get_public_closure, public_closure.get_public_closure_pdf):
        source = inspect.getsource(route)
        assert "_is_publishable(row)" in source
        assert 'generation_status != "complete"' not in source


def test_the_public_document_falls_back_to_the_officers_own_resolution_text():
    """
    The property the whole fix rests on: with no LLM output, the public record still carries what
    the officer decided. If this regressed, publishing without the model would mean publishing a
    document with an empty outcome — worse than the 404 it replaced.
    """
    summary_json = {
        "complaint": {"filed_at": "2026-07-01T00:00:00+00:00", "original_complaint": "धुलो"},
        "resolution": {
            "resolved_at": "2026-07-21T00:00:00+00:00",
            "resolved_by_display_name": "Officer A",
            "category_label": "Contractor instructed",
            "text": "Contractor instructed to wet-spray the road twice daily.",
        },
        "complainant": {"name": "Ram", "address_full": "Ward 4"},
    }

    class _Ticket:
        grievance_id = "GR-1"
        is_seah = False

    public = builder.build_public_summary_json(
        {"ticket": _Ticket(), "primary_language": "ne", "project": {"project_name": "KL Road"}},
        summary_json,
        None,                      # ← the model produced nothing
    )

    assert public["resolution_text_public"] == summary_json["resolution"]["text"]
    assert public["findings_summary_public"] == "", "only the AI narrative is missing"
    assert public["grievance_id"] and public["resolved_at"] and public["resolution_category_label"]
    assert public_closure._is_publishable(_Row(public))


def test_the_task_retries_a_missing_narrative_before_settling_for_less():
    """
    A missing narrative is usually transient, and nobody is waiting on this task — so it is worth
    two more attempts before the document is published without one.
    """
    from ticketing.tasks import llm as llm_tasks

    source = inspect.getsource(llm_tasks.generate_resolved_case_summary)
    assert "if llm_out is None and self.request.retries < 2:" in source
    assert "raise self.retry(countdown=" in source
    # …and the notification no longer waits on the model succeeding.
    assert 'if status == "complete" and row.closure_public_url:' not in source
    assert "publishable and row.closure_public_url" in source
