"""Tests for per-project actor role vocabulary helpers."""
from __future__ import annotations

import pytest

from ticketing.services.project_actor_roles import DEFAULT_ORG_ROLES, normalize_role_entry


def test_normalize_role_entry_requires_key_and_label():
    with pytest.raises(ValueError, match="key"):
        normalize_role_entry({"key": "", "label": "X"}, 0)
    row = normalize_role_entry({"key": "donor", "label": "Donor", "description": "ADB"}, 1)
    assert row["role_key"] == "donor"
    assert row["sort_order"] == 1


def test_default_org_roles_non_empty():
    assert any(r["key"] == "main_contractor" for r in DEFAULT_ORG_ROLES)
