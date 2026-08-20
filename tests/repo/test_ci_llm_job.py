"""
The `live_llm` split is a dependency declaration, and these pins are what stop it rotting into a
quarantine.

DPG-24 puts real, paid, third-party calls behind a marker. That arrangement is only honest while
**something actually runs them**. T3-08 dismantled the previous instance of the same shape — an
`@integration` marker deselected in CI while the seeding cost was still paid — and
`test_officer_assignment.py` rotted unnoticed for months (D-44). The failure is quiet by
construction: a deselected suite is indistinguishable from a passing one in the summary line.

So: `backend-tests` must deselect `live_llm`, `dpg-platform-independence` must select it, and
neither may be true without the other.

Spec: docs/sprints/2026-08-llm/03-open-models-spec.md#dpg-24
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[2]
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PYTEST_INI = REPO_ROOT / "pytest.ini"
DPG_JOB = "dpg-platform-independence"


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(CI.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ci_text() -> str:
    return CI.read_text(encoding="utf-8")


def _steps(workflow: dict, job: str) -> list[dict]:
    return workflow["jobs"][job]["steps"]


def _run_commands(workflow: dict, job: str) -> str:
    return "\n".join(step.get("run", "") for step in _steps(workflow, job))


# ── The marker exists, and is strict ────────────────────────────────────────


def test_the_live_llm_marker_is_registered():
    """`--strict-markers` is on, so an unregistered marker fails collection rather than silently
    matching nothing — which is the failure mode where a typo'd `-m live_lm` selects zero tests
    and reports success."""
    assert "live_llm:" in PYTEST_INI.read_text(encoding="utf-8")


def test_strict_markers_is_actually_enabled_where_the_marker_is_used(workflow):
    for job in ("backend-tests", DPG_JOB):
        assert "--strict-markers" in _run_commands(workflow, job), (
            f"{job} runs pytest without --strict-markers, so a mistyped marker selects nothing "
            "and the job passes green having tested nothing"
        )


# ── The split, in both directions ───────────────────────────────────────────


def test_backend_tests_deselects_the_live_marker(workflow):
    """It must stay free, offline and blocking. Paid third-party calls do not belong in it."""
    assert '-m "not live_llm"' in _run_commands(workflow, "backend-tests")


def test_the_dpg_job_selects_the_live_marker(workflow):
    """⭐ The half that makes the deselection a dependency rather than a quarantine."""
    assert "-m live_llm" in _run_commands(workflow, DPG_JOB)


def test_the_marker_is_not_deselected_in_both_places(workflow):
    """
    The composite property, asserted directly rather than inferred from the two above — because
    the way this rots is somebody adding `not live_llm` to the DPG job to quiet an outage, and both
    tests above would still pass in the arrangement where nothing runs the tests at all.
    """
    dpg = _run_commands(workflow, DPG_JOB)
    assert "not live_llm" not in dpg, (
        "the DPG job now deselects live_llm too — nothing runs these tests. Delete them instead, "
        "so the absence is visible (pytest.ini carries the full note)."
    )


def test_the_dpg_job_runs_on_every_commit_not_on_a_schedule(workflow):
    """
    Q-17: every commit. A nightly cadence is the documented *degraded* fallback if cost forces it,
    and taking it requires saying so in the badge and the job header — so it must not happen by
    someone quietly adding a `schedule:` trigger.
    """
    triggers = workflow[True] if True in workflow else workflow.get("on", {})
    assert "schedule" not in (triggers or {}), (
        "a schedule trigger appeared. If the cadence was reduced for cost (Q-19), the badge and "
        "the job header must say so — see the acceptance criteria."
    )


# ── Both surfaces, or the green means half of what it claims ────────────────


def test_the_dpg_job_exercises_both_llm_surfaces(workflow):
    """
    ⚠ There are two independent LLM surfaces. Pointing only `backend/` at an open endpoint is the
    exact drift `backend/config/llm_config.py` exists to prevent — the complainant-facing resolved
    summary would still be on a closed model while the repository advertised otherwise.
    """
    commands = _run_commands(workflow, DPG_JOB)
    assert "tests/backend/test_llm_live.py" in commands, "the chatbot surface is not exercised"
    assert "tests/ticketing/test_ticketing_llm_live.py" in commands, "the ticketing surface is not exercised"


# ── Fork PRs skip, never fail ───────────────────────────────────────────────


def test_the_job_skips_cleanly_without_a_token(workflow):
    """
    A red X on every external contribution is the wrong signal for a public-good repository, and it
    is also simply untrue — the contributor's patch did not break anything.
    """
    steps = _steps(workflow, DPG_JOB)
    gate = next((s for s in steps if s.get("id") == "gate"), None)
    assert gate is not None, "no gate step deciding whether a token is present"
    assert "HF_TOKEN" in gate["run"]

    guarded = [s for s in steps if s is not gate and s.get("uses") != "actions/checkout@v4"]
    for step in guarded:
        assert "steps.gate.outputs.run == 'true'" in str(step.get("if", "")), (
            f"step {step.get('name', step.get('uses'))!r} is not gated on the token being present, "
            "so a fork PR would fail rather than skip"
        )


# ── No model name may live in the workflow ──────────────────────────────────


def test_the_workflow_names_no_model(ci_text):
    """
    DPG-17's rule reaches here too: a model id written into `ci.yml` is a second place a model name
    lives, and the whole point of the registry is that there is exactly one. Models come from repo
    VARIABLES, so a swap after DPG-23 reports is a settings change, not a commit.
    """
    forbidden = ("gpt-5-nano", "gpt-4o", "gpt-3.5-turbo", "whisper-1", "gpt-oss", "Qwen/", "phi-4")
    hits = [name for name in forbidden if name in ci_text]
    assert not hits, (
        f"model name(s) {hits} appear in ci.yml. Use `vars.DPG_MODEL_*` — see "
        "backend/config/llm_config.py, and tests/backend/test_llm_config_pins.py for the same rule "
        "applied to source."
    )


# ── The reasons must travel with the job ────────────────────────────────────


def test_the_job_header_records_the_branch_protection_decision(ci_text):
    """
    Q-17's answer is only useful where the next person meets it. A reader who finds a red required-
    looking job and no reason will "fix" it by making it required, which is the one thing that must
    not happen.
    """
    header = ci_text[ci_text.index("# ── DPG-24") : ci_text.index("  dpg-platform-independence:")]
    assert "NEVER MAKE THIS A REQUIRED STATUS CHECK" in header
    assert "flaky by construction" in header


def test_the_job_header_records_why_ci_may_route_while_production_pins(ci_text):
    """
    Read naively, the two policies look inconsistent and somebody will "fix" the inconsistency in
    the wrong direction. They separate on the DATA — synthetic here, real grievances in production
    — and the invariant belongs next to the reason.
    """
    header = ci_text[ci_text.index("# ── DPG-24") : ci_text.index("  dpg-platform-independence:")]
    assert "synthetic" in header.lower()
    assert "THE INVARIANT" in header, (
        "the header does not state that the routing policy must change if this job ever gains "
        "access to production data"
    )


def test_the_job_header_is_honest_about_cost_and_about_who_pays_next(ci_text):
    """
    Two acceptance items that are easy to write as intentions and hard to keep as facts: the
    measured spend, and the payer after Q-19's time-boxed envelope ends. Both must appear — as a
    number, or as an explicit `⚠ UNRESOLVED`. A blank is the one thing that is not allowed.
    """
    header = ci_text[ci_text.index("# ── DPG-24") : ci_text.index("  dpg-platform-independence:")]
    assert "MEASURED SPEND:" in header
    assert "WHO PAYS AFTER THE DEMO MONTHS:" in header
    assert "HARD TOKEN CAP" in header


def test_the_workflow_header_counts_its_own_jobs(workflow, ci_text):
    """
    The file's top comment said "Three independent gates" while there were four, for months. A
    header that undercounts is how a gate goes unnoticed — which is the same defect as a marker
    nothing runs, one level up.
    """
    count = len(workflow["jobs"])
    words = {3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven"}
    assert f"{words[count]} independent gates" in ci_text, (
        f"the header does not say there are {count} jobs"
    )
