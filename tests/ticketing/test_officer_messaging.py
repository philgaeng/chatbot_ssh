"""Tests for project-level officer SMS (assignment alerts)."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from ticketing.api.schemas.project_messaging import OfficerMessagingConfig, ProjectMessagingPatch
from ticketing.models.base import SessionLocal
from ticketing.models.project import Project
from ticketing.models.ticket import Ticket
from ticketing.services.officer_messaging import (
    build_officer_sms_body,
    max_workflow_levels_for_project,
    should_send_officer_sms,
    update_officer_messaging,
)


def _ticket(**kwargs) -> Ticket:
    defaults = dict(
        ticket_id="tid-1",
        grievance_id="GRV-2025-001",
        grievance_categories=["Road safety"],
        grievance_location="Morang",
        location_code="P1_MOR",
        project_code="KL_ROAD",
        status_code="OPEN",
        is_deleted=False,
        is_seah=False,
        sla_breached=False,
        priority="NORMAL",
    )
    defaults.update(kwargs)
    return Ticket(**defaults)


def test_should_send_officer_sms_gate():
    off = OfficerMessagingConfig(sms_enabled=False, sms_levels=[1])
    on = OfficerMessagingConfig(sms_enabled=True, sms_levels=[1, 2])
    assert not should_send_officer_sms(off, 1)
    assert should_send_officer_sms(on, 1)
    assert should_send_officer_sms(on, 2)
    assert not should_send_officer_sms(on, 3)


def test_build_officer_sms_body_link_only_no_pii():
    body = build_officer_sms_body(_ticket(), event="assignment")
    assert "GRV-2025-001" in body
    assert "/tickets/tid-1" in body
    assert "Road safety" in body
    assert "Morang" in body
    assert "New case:" in body
    # No complainant fields on ticket model — ensure template stays reference-only
    assert "complainant" not in body.lower()


def test_build_officer_sms_body_escalation_prefix():
    body = build_officer_sms_body(_ticket(), event="escalation")
    assert body.startswith("Escalation:")


@pytest.mark.integration
def test_patch_messaging_rejects_level_above_max():
    db = SessionLocal()
    try:
        project = db.execute(select(Project).limit(1)).scalar_one()
        max_levels = max_workflow_levels_for_project(db, project.project_id)
        if max_levels < 1:
            pytest.skip("No workflow levels on seeded project")
        with pytest.raises(HTTPException) as exc:
            update_officer_messaging(
                db,
                project.project_id,
                ProjectMessagingPatch(sms_enabled=True, sms_levels=[max_levels + 1]),
            )
        assert exc.value.status_code == 422
    finally:
        db.rollback()
        db.close()


def _super_admin_client():
    from fastapi.testclient import TestClient

    from ticketing.api.dependencies import CurrentUser, get_authenticated_user, get_db
    from ticketing.api.main import app

    db = SessionLocal()

    def override_user():
        return CurrentUser(user_id="admin@grm.local", role_keys=["super_admin"])

    def override_get_db():
        yield db

    app.dependency_overrides[get_authenticated_user] = override_user
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), db


@pytest.mark.integration
def test_patch_messaging_api_validation():
    from fastapi.testclient import TestClient

    from ticketing.api.main import app

    client, db = _super_admin_client()
    try:
        project = db.execute(select(Project).limit(1)).scalar_one()
        max_levels = max_workflow_levels_for_project(db, project.project_id)
        if max_levels < 1:
            pytest.skip("No workflow levels on seeded project")
        res = client.patch(
            f"/api/v1/projects/{project.project_id}/messaging",
            json={"sms_enabled": True, "sms_levels": [max_levels + 5]},
        )
        assert res.status_code == 422
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.integration
def test_go_live_f1_warns_when_sms_on_without_phones():
    from ticketing.services import project_go_live as go_live_svc

    db = SessionLocal()
    try:
        project = db.execute(select(Project).limit(1)).scalar_one()
        project.officer_messaging = {
            "sms_enabled": True,
            "sms_levels": [1],
            "whatsapp_levels": [],
        }
        db.flush()
        with patch(
            "ticketing.services.project_go_live.list_grm_officer_profiles",
            return_value={},
        ):
            report = go_live_svc.evaluate_go_live(db, project.project_id)
        f1 = next((c for c in report.checks if c.id == "F1"), None)
        assert f1 is not None
        assert f1.status == "warn"
        assert f1.section == "messaging"
    finally:
        db.rollback()
        db.close()

