"""
Officer assignment + workflow resolution — integration tests against seeded DB.

Covers geographic scoping, province fallback, load balancing, package routing,
workflow selection, and unassigned tickets when no officer matches.

Requires: migrated ticketing schema + seed (kl_road_standard / mock_tickets).
Run inside ticketing_api container:
  python -m pytest tests/ticketing/test_officer_assignment.py -v
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from ticketing.constants.assignment import COUNTRY_L1_FALLBACK_ROLE
from ticketing.engine.workflow_engine import (
    _location_and_ancestors,
    _province_code_for_location,
    _scope_candidates,
    auto_assign_for_workflow_step,
    auto_assign_officer,
    resolve_workflow,
)
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.workflow import WorkflowDefinition, WorkflowStep

from tests.ticketing.conftest import (
    LOC_P1,
    LOC_P1_JHA,
    LOC_P1_JHA_BIR,
    LOC_P1_MOR,
    LOC_P2_PAR_BIR,
    ORG_ADB,
    ORG_DOR,
    PROJECT_KL_ROAD,
    ROLE_L1,
    WORKFLOW_SEAH_KEY,
    WORKFLOW_STANDARD_KEY,
    _uid,
)

SEEDED_SITE_L1 = "l1-officer@grm.local"

pytestmark = pytest.mark.integration


def _first_step(db, workflow_key: str) -> WorkflowStep:
    wf = db.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.workflow_key == workflow_key)
    ).scalar_one()
    return db.execute(
        select(WorkflowStep)
        .where(WorkflowStep.workflow_id == wf.workflow_id)
        .order_by(WorkflowStep.step_order)
        .limit(1)
    ).scalar_one()


def _simulate_create_assignment(
    db,
    *,
    location_code: str,
    project_code: str = PROJECT_KL_ROAD,
    is_seah: bool = False,
    priority: str = "NORMAL",
    package_id: str | None = None,
) -> str | None:
    """Mirror ticketing.api.routers.tickets.create_ticket assignment logic."""
    workflow = resolve_workflow(
        ORG_DOR, location_code, project_code, is_seah, priority, db
    )
    assert workflow is not None
    step = _first_step(db, workflow.workflow_key)
    return auto_assign_for_workflow_step(
        step.assigned_role_key,
        ORG_DOR,
        location_code,
        project_code,
        db,
        ticket_package_id=package_id,
    )


# ── Location / workflow basics ───────────────────────────────────────────────


class TestLocationHierarchy:
    def test_jhapa_municipality_resolves_to_koshi_province(self, db):
        assert _province_code_for_location(LOC_P1_JHA_BIR, db) == LOC_P1

    def test_jhapa_municipality_ancestor_chain(self, db):
        chain = set(_location_and_ancestors(LOC_P1_JHA_BIR, db))
        assert {LOC_P1_JHA_BIR, LOC_P1_JHA, LOC_P1}.issubset(chain)


class TestWorkflowResolution:
    def test_standard_grievance_uses_project_linked_workflow(self, db, kl_road_project):
        wf = resolve_workflow(
            ORG_DOR, LOC_P1_JHA_BIR, PROJECT_KL_ROAD, False, "NORMAL", db
        )
        assert wf is not None
        assert wf.workflow_id == kl_road_project.standard_workflow_id
        assert wf.workflow_key == WORKFLOW_STANDARD_KEY

    def test_seah_grievance_uses_seah_workflow(self, db, kl_road_project):
        wf = resolve_workflow(
            ORG_DOR, LOC_P1_JHA_BIR, PROJECT_KL_ROAD, True, "NORMAL", db
        )
        assert wf is not None
        assert wf.workflow_id == kl_road_project.seah_workflow_id
        assert wf.workflow_key == WORKFLOW_SEAH_KEY


# ── Geographic scoping ───────────────────────────────────────────────────────


class TestGeographicScoping:
    def test_province_fallback_when_no_local_l1(self, db):
        """
        Real-world edge case (B-GR-20260519-KOJH-F6D0):
        Birtamod/Jhapa ticket, only Morang L1 in Koshi → Morang officer assigned.
        """
        candidates = _scope_candidates(
            ROLE_L1, ORG_DOR, LOC_P1_JHA_BIR, PROJECT_KL_ROAD, db
        )
        assert SEEDED_SITE_L1 in candidates
        assert auto_assign_officer(
            ROLE_L1, ORG_DOR, LOC_P1_JHA_BIR, PROJECT_KL_ROAD, db
        ) == SEEDED_SITE_L1

    def test_district_officer_covers_municipality_via_includes_children(self, ctx):
        """Officer at P1_JHA + includes_children matches P1_JHA_BIR (ancestor path)."""
        jhapa_officer = _uid("jhapa-l1")
        ctx.add_scope(
            jhapa_officer,
            location_code=LOC_P1_JHA,
            includes_children=True,
        )
        candidates = _scope_candidates(
            ROLE_L1, ORG_DOR, LOC_P1_JHA_BIR, PROJECT_KL_ROAD, ctx.db
        )
        assert jhapa_officer in candidates
        assert SEEDED_SITE_L1 not in candidates

    def test_local_district_excludes_cross_district_province_fallback(self, ctx):
        """
        When a Jhapa-scoped L1 exists, Morang L1 must NOT enter via province fallback.
        """
        jhapa_officer = _uid("jhapa-local")
        ctx.add_scope(
            jhapa_officer,
            location_code=LOC_P1_JHA,
            includes_children=True,
        )
        assigned = auto_assign_officer(
            ROLE_L1, ORG_DOR, LOC_P1_JHA_BIR, PROJECT_KL_ROAD, ctx.db
        )
        assert assigned == jhapa_officer

    def test_exact_municipality_scope(self, ctx):
        muni_officer = _uid("muni-exact")
        ctx.add_scope(muni_officer, location_code=LOC_P1_JHA_BIR)
        candidates = _scope_candidates(
            ROLE_L1, ORG_DOR, LOC_P1_JHA_BIR, PROJECT_KL_ROAD, ctx.db
        )
        assert muni_officer in candidates

    def test_province_level_officer_covers_any_district(self, ctx):
        prov_officer = _uid("prov-l1")
        ctx.add_scope(
            prov_officer,
            location_code=LOC_P1,
            includes_children=True,
        )
        for loc in (LOC_P1_JHA_BIR, LOC_P1_MOR):
            candidates = _scope_candidates(
                ROLE_L1, ORG_DOR, loc, PROJECT_KL_ROAD, ctx.db
            )
            assert prov_officer in candidates

    def test_org_wide_site_l1_does_not_match_geographic_tickets(self, ctx):
        """Field tier no longer treats location_code=NULL as a wildcard for site L1."""
        wide_officer = _uid("wide-l1")
        ctx.add_scope(wide_officer, location_code=None)
        candidates = _scope_candidates(
            ROLE_L1, ORG_DOR, LOC_P1_JHA_BIR, PROJECT_KL_ROAD, ctx.db
        )
        assert wide_officer not in candidates


# ── No match / wrong scope ────────────────────────────────────────────────────


class TestNoMatchAndExclusions:
    def test_no_officer_in_province_returns_none(self, db):
        """Madhesh (P2) ticket — no L1 scoped under P2 in seed."""
        candidates = _scope_candidates(
            ROLE_L1, ORG_DOR, LOC_P2_PAR_BIR, PROJECT_KL_ROAD, db
        )
        assert candidates == []
        assert auto_assign_officer(
            ROLE_L1, ORG_DOR, LOC_P2_PAR_BIR, PROJECT_KL_ROAD, db
        ) is None

    def test_simulated_create_leaves_ticket_unassigned_when_no_officer(self, db):
        assert _simulate_create_assignment(db, location_code=LOC_P2_PAR_BIR) is None

    def test_wrong_organization_excluded(self, ctx):
        adb_officer = _uid("adb-only")
        ctx.add_scope(
            adb_officer,
            organization_id=ORG_ADB,
            location_code=LOC_P1_JHA,
            includes_children=True,
        )
        candidates = _scope_candidates(
            ROLE_L1, ORG_DOR, LOC_P1_JHA_BIR, PROJECT_KL_ROAD, ctx.db
        )
        assert adb_officer not in candidates

    def test_wrong_project_code_excluded(self, ctx):
        other_project_officer = _uid("other-proj")
        ctx.add_scope(
            other_project_officer,
            location_code=LOC_P1_JHA,
            project_code="OTHER_PROJECT",
            includes_children=True,
        )
        candidates = _scope_candidates(
            ROLE_L1, ORG_DOR, LOC_P1_JHA_BIR, PROJECT_KL_ROAD, ctx.db
        )
        assert other_project_officer not in candidates

    def test_cross_province_officer_not_matched(self, ctx):
        """Koshi officer must not receive a Madhesh ticket via province fallback."""
        koshi_officer = _uid("koshi-only")
        ctx.add_scope(
            koshi_officer,
            location_code=LOC_P1_MOR,
            includes_children=True,
        )
        candidates = _scope_candidates(
            ROLE_L1, ORG_DOR, LOC_P2_PAR_BIR, PROJECT_KL_ROAD, ctx.db
        )
        assert koshi_officer not in candidates


# ── Load balancing ────────────────────────────────────────────────────────────


class TestLoadBalancing:
    def test_least_loaded_among_two_officers_same_district(self, ctx):
        busy = _uid("busy-l1")
        idle = _uid("idle-l1")
        for uid in (busy, idle):
            ctx.add_scope(
                uid,
                location_code=LOC_P1_JHA,
                includes_children=True,
            )
        for _ in range(3):
            ctx.add_open_ticket(busy, location_code=LOC_P1_JHA_BIR)

        assigned = auto_assign_officer(
            ROLE_L1, ORG_DOR, LOC_P1_JHA_BIR, PROJECT_KL_ROAD, ctx.db
        )
        assert assigned == idle

    def test_tie_break_is_stable_when_load_equal(self, ctx):
        """When load is equal, the same officer is picked on repeated calls (SQL row order)."""
        a = "test-tie-officer-aaa-fixed"
        b = "test-tie-officer-bbb-fixed"
        for uid in (b, a):
            ctx.add_scope(uid, location_code=LOC_P1_JHA, includes_children=True)

        first = auto_assign_officer(
            ROLE_L1, ORG_DOR, LOC_P1_JHA_BIR, PROJECT_KL_ROAD, ctx.db
        )
        second = auto_assign_officer(
            ROLE_L1, ORG_DOR, LOC_P1_JHA_BIR, PROJECT_KL_ROAD, ctx.db
        )
        assert first == second
        assert first in (a, b)


# ── Package routing ───────────────────────────────────────────────────────────


class TestPackageRouting:
    def test_package_scoped_officer_when_ticket_has_package_id(self, ctx, jhapa_lot_package_id):
        pkg_officer = _uid("pkg-l1")
        ctx.add_scope(
            pkg_officer,
            location_code=None,
            package_id=jhapa_lot_package_id,
        )
        candidates = _scope_candidates(
            ROLE_L1,
            ORG_DOR,
            LOC_P1_JHA_BIR,
            PROJECT_KL_ROAD,
            ctx.db,
            ticket_package_id=jhapa_lot_package_id,
        )
        assert pkg_officer in candidates
        assert auto_assign_officer(
            ROLE_L1,
            ORG_DOR,
            LOC_P1_JHA_BIR,
            PROJECT_KL_ROAD,
            ctx.db,
            ticket_package_id=jhapa_lot_package_id,
        ) == pkg_officer

    def test_package_ticket_without_package_officer_falls_back_to_province(self, ctx, jhapa_lot_package_id):
        """QR/package ticket with no package-scoped L1 → province pool (Morang seed)."""
        assigned = auto_assign_officer(
            ROLE_L1,
            ORG_DOR,
            LOC_P1_JHA_BIR,
            PROJECT_KL_ROAD,
            ctx.db,
            ticket_package_id=jhapa_lot_package_id,
        )
        assert assigned == SEEDED_SITE_L1

    def test_location_linked_package_officer_without_ticket_package_id(self, ctx, jhapa_lot_package_id):
        """
        Path C: ticket has location only; officer scoped to package covering that location.
        """
        pkg_officer = _uid("loc-pkg-l1")
        ctx.add_scope(
            pkg_officer,
            location_code=None,
            package_id=jhapa_lot_package_id,
        )
        candidates = _scope_candidates(
            ROLE_L1, ORG_DOR, LOC_P1_JHA_BIR, PROJECT_KL_ROAD, ctx.db
        )
        assert pkg_officer in candidates


# ── Country fallback (district → province → country) ─────────────────────────


class TestCountryFallback:
    def test_country_fallback_role_never_in_field_pool(self, ctx):
        national = _uid("national-fallback")
        ctx.add_scope(
            national,
            role_key=COUNTRY_L1_FALLBACK_ROLE,
            location_code=None,
        )
        candidates = _scope_candidates(
            ROLE_L1, ORG_DOR, LOC_P2_PAR_BIR, PROJECT_KL_ROAD, ctx.db
        )
        assert national not in candidates
        field_pool = _scope_candidates(
            COUNTRY_L1_FALLBACK_ROLE,
            ORG_DOR,
            LOC_P1_JHA_BIR,
            PROJECT_KL_ROAD,
            ctx.db,
            assignment_tier="field",
        )
        assert field_pool == []

    def test_country_fallback_picks_up_unassigned_province(self, ctx):
        national = _uid("national-fallback")
        ctx.add_scope(
            national,
            role_key=COUNTRY_L1_FALLBACK_ROLE,
            location_code=None,
        )
        assigned = auto_assign_for_workflow_step(
            ROLE_L1, ORG_DOR, LOC_P2_PAR_BIR, PROJECT_KL_ROAD, ctx.db
        )
        assert assigned == national

    def test_country_fallback_not_used_when_province_officer_exists(self, ctx):
        national = _uid("national-fallback")
        ctx.add_scope(
            national,
            role_key=COUNTRY_L1_FALLBACK_ROLE,
            location_code=None,
        )
        # Seed Morang L1 already exists — Jhapa ticket should stay on province pool.
        assigned = auto_assign_for_workflow_step(
            ROLE_L1, ORG_DOR, LOC_P1_JHA_BIR, PROJECT_KL_ROAD, ctx.db
        )
        assert assigned == SEEDED_SITE_L1
        assert assigned != national

    def test_country_fallback_not_used_when_local_district_exists(self, ctx):
        national = _uid("national-fallback")
        jhapa = _uid("jhapa-local")
        ctx.add_scope(
            national,
            role_key=COUNTRY_L1_FALLBACK_ROLE,
            location_code=None,
        )
        ctx.add_scope(
            jhapa,
            role_key=ROLE_L1,
            location_code=LOC_P1_JHA,
            includes_children=True,
        )
        assigned = auto_assign_for_workflow_step(
            ROLE_L1, ORG_DOR, LOC_P1_JHA_BIR, PROJECT_KL_ROAD, ctx.db
        )
        assert assigned == jhapa
        assert assigned != national

    def test_simulated_create_uses_country_fallback_for_p2(self, ctx):
        national = "test-national-l1-fixed"
        ctx.add_scope(
            national,
            role_key=COUNTRY_L1_FALLBACK_ROLE,
            location_code=None,
        )
        assigned = _simulate_create_assignment(ctx.db, location_code=LOC_P2_PAR_BIR)
        assert assigned == national


# ── End-to-end simulation ─────────────────────────────────────────────────────


class TestEndToEndSimulation:
    def test_full_standard_intake_jhapa_birtamod(self, db):
        """Regression anchor for B-GR-20260519-KOJH-F6D0 allocation path."""
        assigned = _simulate_create_assignment(db, location_code=LOC_P1_JHA_BIR)
        assert assigned == SEEDED_SITE_L1

    def test_full_intake_with_local_jhapa_officer(self, ctx):
        jhapa_officer = _uid("jhapa-e2e")
        ctx.add_scope(
            jhapa_officer,
            location_code=LOC_P1_JHA,
            includes_children=True,
        )
        assigned = _simulate_create_assignment(
            ctx.db, location_code=LOC_P1_JHA_BIR
        )
        assert assigned == jhapa_officer

    def test_no_duplicate_scope_rows_leaked_after_test(self, ctx, db):
        """Sanity: ctx cleanup removes temporary scopes."""
        temp = _uid("cleanup-check")
        ctx.add_scope(temp, location_code=LOC_P1_JHA)
        scope_id = ctx.scope_ids[-1]
        ctx.cleanup()
        remaining = db.execute(
            select(OfficerScope).where(OfficerScope.scope_id == scope_id)
        ).scalar_one_or_none()
        assert remaining is None
