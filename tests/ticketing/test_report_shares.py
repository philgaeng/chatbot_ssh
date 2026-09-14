# SPDX-License-Identifier: Apache-2.0

"""
Report share links (TP-05) — the service behind `POST /api/v1/reports/share`.

⚠ **Written because there were no tests at all**, which is how GRM-071 shipped: sharing a
report returned HTTP 500 on every deployment where nobody had shared one before. The route
was in `route_snapshot.txt`, so the "new route: snapshot updated" box was ticked — and
nothing ever called it. A snapshot proves a route *exists*; only a test proves it *works*.

The first test below is the regression: it exercises the **insert** branch of `_save`, which
is the branch that only runs once in the life of a database and therefore the one nobody hits
in development after the first time.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from ticketing.models.base import SessionLocal
from ticketing.models.settings import Settings
from ticketing.services.report_shares import (
    SETTING_KEY,
    create_report_share,
    get_share_by_token,
)

CREATOR = "admin@grm.local"
LATER_CREATOR = "project-admin@grm.local"


@pytest.fixture
def no_share_row(db):
    """A database that has never had a report shared — the state that produced GRM-071.

    Snapshots any existing row, removes it, and restores it afterwards, so this never
    destroys shares another test (or the developer's own stack) created. Rule 3.4.
    """
    existing = db.get(Settings, SETTING_KEY)
    saved = (existing.value, existing.updated_by_user_id) if existing else None
    if existing:
        db.delete(existing)
        db.commit()
    try:
        yield
    finally:
        db.execute(delete(Settings).where(Settings.key == SETTING_KEY))
        if saved is not None:
            db.add(Settings(key=SETTING_KEY, value=saved[0], updated_by_user_id=saved[1]))
        db.commit()


def _create(db, name: str = "e2e regression share", created_by: str = CREATOR):
    return create_report_share(
        db,
        name=name,
        report_kind="overview",
        filters={"date_from": "2026-01-01", "date_to": "2026-12-31"},
        rows_internal=[{"grievance_id": "GRV-2025-001"}],
        rows_public=[{"grievance_id": "GRV-2025-001"}],
        columns_internal=["grievance_id"],
        columns_public=["grievance_id"],
        created_by=created_by,
    )


@pytest.mark.integration
def test_the_first_share_on_a_database_succeeds(db, no_share_row):
    """GRM-071: the insert branch raised TypeError → HTTP 500 for the first sharer."""
    item = _create(db)

    assert item["internal_token"] and item["public_token"]
    assert item["internal_token"] != item["public_token"]

    row = db.get(Settings, SETTING_KEY)
    assert row is not None, "the settings row must exist after the first share"
    assert len(row.value) == 1


@pytest.mark.integration
def test_a_share_is_retrievable_by_either_token(db, no_share_row):
    """The tokens are the whole feature: /reports/view/<internal>, /reports/public/<public>."""
    item = _create(db)

    by_internal = get_share_by_token(db, item["internal_token"])
    by_public = get_share_by_token(db, item["public_token"])

    assert by_internal is not None and by_internal["id"] == item["id"]
    assert by_public is not None and by_public["id"] == item["id"]
    assert get_share_by_token(db, "not-a-real-token") is None


@pytest.mark.integration
def test_who_created_a_share_is_recorded_on_both_the_first_and_a_later_share(db, no_share_row):
    """Both branches of `_save` must write the audit column.

    ⚠ The update branch is the sneaky one: `row.updated_by = ...` on a model without that
    column raises nothing — Python simply attaches an attribute nobody reads — so the value
    was discarded in silence.

    ⭐ **The second share must be by a DIFFERENT officer, and that is the whole test.** The
    first draft used the same creator twice and the mutation SURVIVED (measured 2026-09-06):
    the insert had already written `CREATOR`, so an update that discarded its value left the
    column reading correct anyway. A test that asserts a value the broken code also produces
    is decoration — Rule 5.3, caught by running the mutation rather than trusting the shape
    of the test.
    """
    _create(db, "first", created_by=CREATOR)
    first = db.get(Settings, SETTING_KEY)
    assert first.updated_by_user_id == CREATOR

    _create(db, "second", created_by=LATER_CREATOR)
    db.expire_all()
    later = db.get(Settings, SETTING_KEY)
    assert len(later.value) == 2
    assert later.updated_by_user_id == LATER_CREATOR, (
        "the update branch must write the audit column too — see the docstring"
    )


@pytest.mark.integration
def test_only_the_last_fifty_shares_are_kept(db, no_share_row):
    """The cap is what stops a settings row growing without bound; nothing else prunes it."""
    for i in range(52):
        _create(db, f"share {i}")

    db.expire_all()
    row = db.get(Settings, SETTING_KEY)
    assert len(row.value) == 50
    assert row.value[0]["name"] == "share 51", "newest first"


@pytest.mark.integration
def test_a_blank_name_falls_back_rather_than_storing_an_empty_label(db, no_share_row):
    item = _create(db, "   ")
    assert item["name"] == "GRM report"
