"""Role archetype permission templates."""
from ticketing.constants.role_archetypes import (
    list_archetypes,
    permissions_for_archetype,
)


def test_informed_archetype_permissions():
    assert permissions_for_archetype("informed") == [
        "tickets:read",
        "tickets:note",
    ]


def test_informed_archetype_listed():
    keys = [a["key"] for a in list_archetypes()]
    assert "informed" in keys
    informed = next(a for a in list_archetypes() if a["key"] == "informed")
    assert "Informed participant" in informed["label"]
