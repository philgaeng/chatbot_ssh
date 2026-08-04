"""Author-named jobs per level: `workflow_steps.tier_labels` + `required_tiers`.

DECISION-author-defined-slots §3.2. Both columns were documented in doc 12 §2 and depended
on by doc 13 §5A for months while existing nowhere in the code, so these tests pin the two
things that made them worth building:

  1. `required_tiers` rejects "actor" — the actor is always required, so listing it is a
     silent no-op that would make a workflow look configured when it isn't.
  2. Go-live's level-staffing gate reads `required_tiers`, and reports the gap using the
     AUTHOR'S name for the job, so the checklist and the staffing screen say the same words.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from ticketing.api.schemas.workflow import REQUIRABLE_TIERS, WorkflowStepCreate, WorkflowStepUpdate
from ticketing.services.project_go_live import _standard_level_gaps


# ── schema ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("tier", REQUIRABLE_TIERS)
def test_required_tiers_accepts_non_actor_tiers(tier):
    assert WorkflowStepCreate(display_name="L1", required_tiers=[tier]).required_tiers == [tier]


@pytest.mark.parametrize("schema", [WorkflowStepCreate, WorkflowStepUpdate])
def test_required_tiers_rejects_actor(schema):
    """The actor is always required. Accepting it here would let an author believe they had
    marked something mandatory when the value changes nothing."""
    kwargs = {"display_name": "L1"} if schema is WorkflowStepCreate else {}
    with pytest.raises(ValidationError, match="actor is always required"):
        schema(**kwargs, required_tiers=["actor"])


def test_required_tiers_deduplicates():
    step = WorkflowStepCreate(display_name="L1", required_tiers=["supervisor", "supervisor"])
    assert step.required_tiers == ["supervisor"]


def test_tier_labels_carry_label_and_description():
    step = WorkflowStepCreate(
        display_name="L2",
        tier_labels={"supervisor": {"label": "Escalation Lead", "description": "oversees"}},
    )
    assert step.tier_labels["supervisor"].label == "Escalation Lead"


def test_tier_labels_reject_a_missing_label():
    with pytest.raises(ValidationError):
        WorkflowStepCreate(display_name="L2", tier_labels={"supervisor": {"description": "x"}})


# ── go-live gate ──────────────────────────────────────────────────────────────

class _Step:
    """Minimal stand-in — `_standard_level_gaps` only reads these attributes."""

    def __init__(self, order, actor, *, supervisor=None, required=(), labels=None):
        self.step_order = order
        self.assigned_role_key = actor
        self.supervisor_role = supervisor
        self.informed_roles: list[str] = []
        self.observer_roles: list[str] = []
        self.required_tiers = list(required)
        self.tier_labels = labels or {}


def _gaps(monkeypatch, steps, staffed: set[str]):
    """Run the gap finder with a fixed set of staffed role keys."""
    import ticketing.services.project_go_live as gl

    monkeypatch.setattr(gl, "_has_officer_on_project_wide",
                        lambda db, *, project, grm_role_key: grm_role_key in staffed)
    monkeypatch.setattr(gl, "_packages_missing_role",
                        lambda db, **kw: [])

    class _P:
        standard_workflow_id = "wf-1"

    class _DB:
        def execute(self, *_a, **_k):
            class _R:
                def scalars(self_inner):
                    class _S:
                        def all(self_s):
                            return steps
                    return _S()
            return _R()

    return _standard_level_gaps(_DB(), project=_P(), packages=[])


def test_unstaffed_actor_is_a_gap(monkeypatch):
    steps = [_Step(1, "site_focal")]
    assert _gaps(monkeypatch, steps, staffed=set()) == ["L1 (site_focal)"]
    assert _gaps(monkeypatch, steps, staffed={"site_focal"}) == []


def test_supervisor_only_gates_when_the_author_marked_it_required(monkeypatch):
    """The whole point of the column: an unstaffed supervisor is fine unless the workflow
    says otherwise."""
    optional = [_Step(1, "site_focal", supervisor="piu_focal")]
    assert _gaps(monkeypatch, optional, staffed={"site_focal"}) == []

    required = [_Step(1, "site_focal", supervisor="piu_focal", required=["supervisor"])]
    assert _gaps(monkeypatch, required, staffed={"site_focal"}) == ["L1 (piu_focal)"]
    assert _gaps(monkeypatch, required, staffed={"site_focal", "piu_focal"}) == []


def test_gap_uses_the_authors_name_for_the_job(monkeypatch):
    steps = [_Step(
        2, "piu_focal", supervisor="pd_focal", required=["supervisor"],
        labels={"supervisor": {"label": "Escalation Lead", "description": "oversees"}},
    )]
    assert _gaps(monkeypatch, steps, staffed={"piu_focal"}) == ["L2 (Escalation Lead)"]


def test_required_tier_with_no_role_bound_blames_the_workflow(monkeypatch):
    """Marked mandatory but nothing bound: the project cannot fix this by staffing, so the
    message must point at the workflow instead of naming a phantom role."""
    steps = [_Step(1, "site_focal", supervisor=None, required=["supervisor"])]
    gaps = _gaps(monkeypatch, steps, staffed={"site_focal"})
    assert gaps == ["L1 (supervisor: no role on the workflow)"]
