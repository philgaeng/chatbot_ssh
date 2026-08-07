"""Every job at a level carries the author's name — doc 12 §6.2.

> **Name + description** (`tier_labels`) — each tier starts from a **default** … that the author
> can **edit per step, here in the Workflows tab**; e.g. L1 actor named "Safeguard Officer", L3
> actor "GRC Chairman". These … labels — never generic words like "Handles it" — are what the
> staffing and case UI display (**read-only there; edited only here**).

Specified in June, and the model + editor shipped 2026-08-04. What was missing until now: nothing
was ever *authored*, so every screen fell through to a second choice — the display name of the
**role** bound to the job. That made the workflow screen look ignored, and it meant a deployment
could not use the words on its own contract.

Closed by three things together, and these tests pin all three:
  • `r4t6v8x0` back-fills the name each screen was already showing, so nothing is blank;
  • a level cannot be saved, or a workflow published, with an unnamed job;
  • the role-name fallback is deleted — with no blanks and no fallback, the workflow is the only
    place a job's name can come from.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from ticketing.services.role_scope import enabled_tiers, require_named_jobs, unnamed_jobs

pytestmark = pytest.mark.integration


class _Step:
    def __init__(self, *, actor=None, supervisor=None, informed=(), observers=(), labels=None):
        self.assigned_role_key = actor
        self.supervisor_role = supervisor
        self.informed_roles = list(informed)
        self.observer_roles = list(observers)
        self.tier_labels = labels or {}


def _named(*tiers):
    return {t: {"label": f"{t.title()} name"} for t in tiers}


# ── which jobs a level has ────────────────────────────────────────────────────

def test_a_job_is_enabled_by_having_a_role_bound():
    step = _Step(actor="a", supervisor="s", informed=["i"], observers=["o"])
    assert enabled_tiers(step) == ["actor", "supervisor", "participant", "observer"]


def test_jobs_the_level_does_not_use_are_not_asked_for():
    """A level with no supervisor is not nagged for a supervisor's name."""
    step = _Step(actor="a", labels=_named("actor"))
    assert enabled_tiers(step) == ["actor"]
    assert unnamed_jobs(step) == []


# ── the requirement ───────────────────────────────────────────────────────────

def test_an_unnamed_job_is_refused_by_the_editor_words():
    step = _Step(actor="a", supervisor="s", labels=_named("actor"))
    with pytest.raises(HTTPException) as exc:
        require_named_jobs(step)
    assert exc.value.status_code == 422
    # names the job in the words the step editor uses — not a tier key, not a role key
    assert "Oversees" in exc.value.detail
    assert "supervisor" not in exc.value.detail


def test_whitespace_is_not_a_name():
    step = _Step(actor="a", labels={"actor": {"label": "   "}})
    assert unnamed_jobs(step) == ["Works it"]


def test_a_fully_named_level_saves():
    step = _Step(actor="a", supervisor="s", informed=["i"], labels=_named("actor", "supervisor", "participant"))
    require_named_jobs(step)  # no raise


def test_the_message_lists_every_missing_job_at_once():
    """One save, one list — not one error per field, discovered one at a time."""
    step = _Step(actor="a", supervisor="s", observers=["o"])
    with pytest.raises(HTTPException) as exc:
        require_named_jobs(step)
    for word in ("Works it", "Oversees", "Can view"):
        assert word in exc.value.detail


# ── the fallback is gone ──────────────────────────────────────────────────────

def test_go_live_never_falls_back_to_a_role_key():
    """The gap message used to read "L1 (site_safeguards_focal_person)" when unnamed — a slug on
    screen (ui/05 §2.5). With names required it cannot happen; if it somehow does, the editor's
    own word is used, never the key."""
    import inspect

    from ticketing.services import project_go_live as go_live_svc

    src = inspect.getsource(go_live_svc._standard_level_gaps)
    assert "_TIER_WORDS" in src
    assert "return label or role" not in src


def test_the_seeded_workflow_names_every_job(db):
    """A fresh deployment must be able to publish the workflow it ships with — so the seed
    authors names rather than leaving the back-fill to do it."""
    from sqlalchemy import select

    from ticketing.models.workflow import WorkflowStep

    steps = db.execute(
        select(WorkflowStep).where(WorkflowStep.is_deleted.is_(False))
    ).scalars().all()
    offenders = {
        f"{s.display_name}: {', '.join(unnamed_jobs(s))}" for s in steps if unnamed_jobs(s)
    }
    assert not offenders, f"levels with unnamed jobs: {sorted(offenders)}"
