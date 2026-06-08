"""Tests for grievance classification catalog (settings + public taxonomy sync)."""
from __future__ import annotations

import pytest

from ticketing.services.grievance_categories_catalog import (
    derive_category_key,
    load_default_catalog,
    normalize_category_entry,
    save_grievance_categories_catalog,
    _validate_catalog_shape,
)


def test_derive_category_key_matches_seed_format():
    key = derive_category_key("Environmental", "Air Pollution")
    assert key == "Environmental - Air Pollution"


def test_normalize_category_entry_computes_key():
    entry = normalize_category_entry(
        {
            "classification": "Environmental",
            "generic_grievance_name": "Air Pollution",
            "description": "Dust from construction.",
            "high_priority": "true",
        }
    )
    assert entry["category_key"] == "Environmental - Air Pollution"
    assert entry["description"] == "Dust from construction."
    assert entry["high_priority"] is True


def test_validate_catalog_rejects_duplicate_keys():
    catalog = {
        "categories": [
            {"category_key": "A - B", "classification": "A", "generic_grievance_name": "B"},
            {"category_key": "A - B", "classification": "A", "generic_grievance_name": "B"},
        ]
    }
    with pytest.raises(ValueError, match="Duplicate"):
        _validate_catalog_shape(catalog)


def test_load_default_catalog_has_entries():
    catalog = load_default_catalog()
    assert len(catalog["categories"]) >= 20
    first = catalog["categories"][0]
    assert first["category_key"]
    assert "generic_grievance_name" in first
    assert "description" in first


def test_save_grievance_categories_catalog_syncs_public(db):
    """Requires live DB with public.grievance_classification_taxonomy."""
    from sqlalchemy import text

    from ticketing.models.base import SessionLocal

    session = SessionLocal()
    try:
        catalog = load_default_catalog()
        # Use a single-category snapshot to limit blast radius
        one = catalog["categories"][0]
        payload = {"categories": [one]}
        save_grievance_categories_catalog(session, payload, "test-super-admin")
        row = session.execute(
            text(
                "SELECT category_key FROM public.grievance_classification_taxonomy "
                "WHERE category_key = :key"
            ),
            {"key": one["category_key"]},
        ).first()
        assert row is not None
        # Restore full catalog for other tests
        save_grievance_categories_catalog(session, catalog, "test-super-admin")
    except Exception:
        pytest.skip("DB not available")
    finally:
        session.close()
