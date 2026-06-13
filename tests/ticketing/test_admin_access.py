"""Unit tests for ticketing.services.admin_access matrix helpers."""
from __future__ import annotations

import pytest

from ticketing.api.dependencies import CurrentUser
from ticketing.services.admin_access import (
    AdminScopeRow,
    SettingsAction,
    admin_workflow_tracks,
    can_create_operational_role,
    can_create_project,
    can_manage_structure,
    can_mutate_workflow,
    is_country_admin,
    is_project_admin,
    require_settings_write,
)
from ticketing.api.schemas.user import AdminScopeCreate
from fastapi import HTTPException


def _scope(**kwargs) -> AdminScopeRow:
    defaults = dict(
        admin_scope_id="s1",
        user_id="u@grm.local",
        role_key="country_admin",
        country_code="NP",
        project_id=None,
        organization_id=None,
        package_id=None,
        workflow_track="standard",
    )
    defaults.update(kwargs)
    return AdminScopeRow(**defaults)


def test_standard_country_admin_can_manage_structure():
    user = CurrentUser(
        user_id="c@grm.local",
        role_keys=["country_admin"],
        admin_scopes=[_scope(workflow_track="standard")],
    )
    assert can_manage_structure(user)
    assert is_country_admin(user, "standard")
    assert not is_country_admin(user, "seah")


def test_seah_country_admin_can_manage_structure():
    user = CurrentUser(
        user_id="seah@grm.local",
        role_keys=["country_admin"],
        admin_scopes=[_scope(workflow_track="seah")],
    )
    assert can_manage_structure(user)
    assert is_country_admin(user, "seah")


def test_country_admin_can_create_project_either_track():
    standard = CurrentUser(
        user_id="c@grm.local",
        role_keys=["country_admin"],
        admin_scopes=[_scope(workflow_track="standard")],
    )
    seah = CurrentUser(
        user_id="seah@grm.local",
        role_keys=["country_admin"],
        admin_scopes=[_scope(workflow_track="seah")],
    )
    assert can_create_project(standard)
    assert can_create_project(seah)
    require_settings_write(standard, SettingsAction.CREATE_PROJECT)
    require_settings_write(seah, SettingsAction.CREATE_PROJECT)


def test_project_admin_scope():
    user = CurrentUser(
        user_id="p@grm.local",
        role_keys=["project_admin"],
        admin_scopes=[_scope(role_key="project_admin", project_id="KL_ROAD", country_code=None)],
    )
    assert is_project_admin(user, "KL_ROAD", "standard")
    assert not can_create_operational_role(user, track="standard")


def test_require_structure_ok_for_seah_country_admin():
    user = CurrentUser(
        user_id="seah@grm.local",
        role_keys=["country_admin"],
        admin_scopes=[_scope(workflow_track="seah")],
    )
    require_settings_write(user, SettingsAction.MANAGE_STRUCTURE, track="standard")


def test_super_admin_bypasses_track_checks():
    user = CurrentUser(user_id="admin@grm.local", role_keys=["super_admin"])
    require_settings_write(user, SettingsAction.MANAGE_STRUCTURE, track="standard")
    require_settings_write(user, SettingsAction.PLATFORM_SETTINGS)


def test_country_admin_dual_track_scopes():
    user = CurrentUser(
        user_id="both@grm.local",
        role_keys=["country_admin"],
        admin_scopes=[
            _scope(workflow_track="standard"),
            _scope(admin_scope_id="s2", workflow_track="seah"),
        ],
    )
    assert admin_workflow_tracks(user) == {"standard", "seah"}
    assert is_country_admin(user, "standard")
    assert is_country_admin(user, "seah")
    assert can_mutate_workflow(user, "standard")
    assert can_mutate_workflow(user, "seah")


def test_admin_scope_create_resolves_both_tracks():
    body = AdminScopeCreate(
        user_id="c@grm.local",
        role_key="country_admin",
        country_code="NP",
        workflow_track="both",
    )
    assert AdminScopeCreate.resolved_workflow_tracks(body) == ["standard", "seah"]


def test_admin_scope_create_resolves_workflow_tracks_list():
    body = AdminScopeCreate(
        user_id="c@grm.local",
        role_key="country_admin",
        country_code="NP",
        workflow_tracks=["seah", "standard", "seah"],
    )
    assert AdminScopeCreate.resolved_workflow_tracks(body) == ["seah", "standard"]
