"""Unit tests for ticketing.services.admin_access matrix helpers."""
from __future__ import annotations

import pytest

from ticketing.api.dependencies import CurrentUser
from ticketing.services.admin_access import (
    AdminScopeRow,
    SettingsAction,
    can_create_operational_role,
    can_manage_structure,
    is_country_admin,
    is_project_admin,
    require_settings_write,
)
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


def test_seah_country_admin_cannot_manage_structure():
    user = CurrentUser(
        user_id="seah@grm.local",
        role_keys=["country_admin"],
        admin_scopes=[_scope(workflow_track="seah")],
    )
    assert not can_manage_structure(user)
    assert is_country_admin(user, "seah")


def test_project_admin_scope():
    user = CurrentUser(
        user_id="p@grm.local",
        role_keys=["project_admin"],
        admin_scopes=[_scope(role_key="project_admin", project_id="KL_ROAD", country_code=None)],
    )
    assert is_project_admin(user, "KL_ROAD", "standard")
    assert not can_create_operational_role(user, track="standard")


def test_require_structure_raises_for_seah_country_admin():
    user = CurrentUser(
        user_id="seah@grm.local",
        role_keys=["country_admin"],
        admin_scopes=[_scope(workflow_track="seah")],
    )
    with pytest.raises(HTTPException) as exc:
        require_settings_write(user, SettingsAction.MANAGE_STRUCTURE, track="standard")
    assert exc.value.status_code == 403


def test_super_admin_bypasses_track_checks():
    user = CurrentUser(user_id="admin@grm.local", role_keys=["super_admin"])
    require_settings_write(user, SettingsAction.MANAGE_STRUCTURE, track="standard")
    require_settings_write(user, SettingsAction.PLATFORM_SETTINGS)
