"""Tests for project/package entity code validation and rename cascade."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from ticketing.constants.entity_codes import (
    EntityCodeError,
    normalize_entity_code,
    validate_entity_code,
)
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.project import Project
from ticketing.models.ticket import Ticket
from ticketing.services.entity_codes import next_package_code, rename_project_short_code
from tests.ticketing.conftest import AssignmentTestContext


def test_normalize_entity_code_strips_and_uppercases():
    assert normalize_entity_code("  kl_road  ") == "KL_ROAD"
    assert normalize_entity_code("ab/cd-12") == "ABCD12"
    assert normalize_entity_code("123456789") == "12345678"


def test_validate_entity_code_rejects_empty():
    with pytest.raises(EntityCodeError):
        validate_entity_code("", field="Project code")


def test_validate_entity_code_accepts_underscore():
    assert validate_entity_code("KL_01") == "KL_01"


def test_next_package_code_zero_padded():
    class _FakeScalars:
        def __init__(self, codes):
            self._codes = codes

        def all(self):
            return self._codes

    class _FakeExecute:
        def __init__(self, codes):
            self._codes = codes

        def scalars(self):
            return _FakeScalars(self._codes)

    class _FakeDb:
        def __init__(self, codes):
            self._codes = codes

        def execute(self, _stmt):
            return _FakeExecute(self._codes)

    assert next_package_code(_FakeDb([]), "proj-1") == "01"
    assert next_package_code(_FakeDb(["01", "02"]), "proj-1") == "03"


def test_rename_project_short_code_cascades(db, kl_road_project):
    project = kl_road_project
    old_code = project.short_code
    new_code = f"T{uuid.uuid4().hex[:5].upper()}"

    ctx = AssignmentTestContext(db=db)
    try:
        scope = ctx.add_scope(
            user_id="cascade-test@grm.local",
            project_code=old_code,
        )
        scope.project_id = project.project_id
        db.flush()

        ticket = ctx.add_open_ticket("cascade-test@grm.local", project_code=old_code)
        ticket.project_id = project.project_id
        db.flush()

        rename_project_short_code(db, project, new_code)
        db.commit()

        db.refresh(project)
        assert project.short_code == new_code

        refreshed_scope = db.get(OfficerScope, scope.scope_id)
        assert refreshed_scope is not None
        assert refreshed_scope.project_code == new_code

        refreshed_ticket = db.get(Ticket, ticket.ticket_id)
        assert refreshed_ticket is not None
        assert refreshed_ticket.project_code == new_code

        conflict = db.execute(
            select(Project).where(Project.short_code == new_code)
        ).scalar_one()
        assert conflict.project_id == project.project_id
    finally:
        rename_project_short_code(db, project, old_code)
        db.commit()
        ctx.cleanup()
