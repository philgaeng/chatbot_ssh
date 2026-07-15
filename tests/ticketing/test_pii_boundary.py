"""
T3-04 — the PII boundary's regression net.

This file is commit 1 of T3-04 and it exists **before** any fix. It is the safety net for
the three commits that follow (backend decrypts -> delete ticketing's workaround -> drop
the key), and its job is to stay green at every one of them. If it ever goes red, the
boundary is broken and the ticket stops.

Why it had to come first (D-09): nothing imported `pii_vault` — `decrypt_ciphertext`,
`reveal_field`, `scrub_pii_value` and `grievance_pii_for_officer_card` were entirely
uncovered. `test_ticket_access_matrix.py` probes `GET /tickets/{id}/pii` for authz only:
it never mocks the client, so it lands in the `_backend_unavailable` branch and asserts
against a null-filled dict. It passes identically whether decryption works or is deleted.
Dropping the key first would have mapped every contact field to None — officers see "—"
on every card, with no error and no failing test.

**The invariant this file pins, and why it is not the spec's.** The spec asks to
parametrize the mocked payload over ciphertext and plaintext "so the same test proves
both … unchanged" through steps 2-4. That cannot hold: today ciphertext is decrypted to
plaintext by the vault workaround, but once step 3 deletes that workaround the same
ciphertext is masked to None. No single assertion is true at both ends. What *is* true at
every commit, and is the property officers actually care about, is:

    * plaintext in  => plaintext on the card   (the regression guard proper)
    * ciphertext in => **never ciphertext on the card**
      (by decryption today; by fail-closed masking after step 3)

So the ciphertext arm asserts the durable property rather than a mechanism that is about
to change. See PROGRESS.md -> Deviations.
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest

from ticketing.services.pii_vault import (
    grievance_pii_for_officer_card,
    grievance_pii_masked,
    looks_like_ciphertext,
    scrub_pii_value,
)

# A realistic pgcrypto hex ciphertext shape: >= 40 chars, all hex.
CIPHERTEXT = "c30d0409030213b7a4f1e2d5c6a7b8" + "0" * 60
PLAIN = {
    "complainant_full_name": "Sita Rai",
    "complainant_phone": "+9779812345678",
    "complainant_email": "sita.rai@example.np",
    "complainant_address": "Ward 4, Birtamod",
}

CARD_CONTACT_FIELDS = ("complainant_name", "phone_number", "email", "address")


def _grievance(**overrides: Any) -> dict[str, Any]:
    row = {
        "grievance_id": "GR-TEST-PII-0001",
        "complainant_full_name": PLAIN["complainant_full_name"],
        "complainant_phone": PLAIN["complainant_phone"],
        "complainant_email": PLAIN["complainant_email"],
        "complainant_address": PLAIN["complainant_address"],
        "complainant_village": "Birtamod",
        "complainant_ward": "4",
        "complainant_municipality": "Birtamod",
        "complainant_district": "Jhapa",
        "complainant_province": "Koshi",
        "location_geo": None,
        "grievance_description": "Dust from the road is making the children sick.",
    }
    row.update(overrides)
    return row


def _ciphertext_grievance() -> dict[str, Any]:
    """What GET /api/grievance/{id} returns TODAY: hex ciphertext on the four fields."""
    return _grievance(
        complainant_full_name=CIPHERTEXT,
        complainant_phone=CIPHERTEXT,
        complainant_email=CIPHERTEXT,
        complainant_address=CIPHERTEXT,
    )


# ── looks_like_ciphertext / scrub_pii_value — zero coverage before this file ──────────


@pytest.mark.parametrize(
    "value,expected",
    [
        (CIPHERTEXT, True),
        (PLAIN["complainant_full_name"], False),
        (PLAIN["complainant_phone"], False),
        (PLAIN["complainant_email"], False),
        (None, False),
        ("", False),
        (12345, False),                      # non-str must not blow up
        ("deadbeef", False),                 # hex but under the 40-char floor
        ("z" * 60, False),                   # long but not hex
        ("A" * 40, True),                    # uppercase hex is still ciphertext
        ("  " + CIPHERTEXT + "  ", True),    # surrounding whitespace tolerated
    ],
)
def test_looks_like_ciphertext(value, expected):
    assert looks_like_ciphertext(value) is expected


def test_scrub_pii_value_masks_ciphertext_and_passes_plaintext():
    assert scrub_pii_value(CIPHERTEXT) is None
    assert scrub_pii_value(PLAIN["complainant_phone"]) == PLAIN["complainant_phone"]
    assert scrub_pii_value(None) is None


def test_scrub_pii_value_is_loud_about_ciphertext(caplog):
    """
    T3-04 step 3's decision, pinned. `scrub_pii_value` is a defense-in-depth ASSERTION,
    not a masking behaviour: since the backend decrypts, ciphertext arriving here means
    something upstream regressed. It must fail closed *and* say so.

    Silence is what made the review's prescribed order dangerous — every contact field
    would map to None and officers would see "—" with nothing in the logs. Added in step
    3 (before it, the value was decrypted rather than scrubbed, so there was nothing to
    shout about).
    """
    import logging as _logging

    with caplog.at_level(_logging.ERROR, logger="ticketing.services.pii_vault"):
        assert scrub_pii_value(CIPHERTEXT) is None

    errors = [r for r in caplog.records if r.levelno >= _logging.ERROR]
    assert errors, "ciphertext on the officer card must be logged at error, not masked silently"
    assert CIPHERTEXT not in caplog.text, "the ciphertext value itself must not be logged"


def test_scrub_pii_value_is_silent_for_plaintext(caplog):
    """CONTROL — the normal path must not spam errors on every card render."""
    import logging as _logging

    with caplog.at_level(_logging.ERROR, logger="ticketing.services.pii_vault"):
        scrub_pii_value(PLAIN["complainant_phone"])
        scrub_pii_value(None)

    assert not [r for r in caplog.records if r.levelno >= _logging.ERROR]


def test_grievance_pii_masked_never_emits_ciphertext():
    """The default (non-card) shape must scrub all four contact fields."""
    data = grievance_pii_masked(_ciphertext_grievance())
    for field in CARD_CONTACT_FIELDS:
        assert data[field] is None, f"{field} leaked ciphertext through grievance_pii_masked"
    # Non-PII location fields are unaffected.
    assert data["district"] == "Jhapa"


# ── grievance_pii_for_officer_card — the function the whole ticket exists for ─────────


def test_officer_card_shows_plaintext_contact_for_standard():
    """
    THE REGRESSION GUARD. A standard ticket's card must show real contact details.
    Green at every one of T3-04's four commits, for a different reason each time:
    today the vault workaround decrypts; after step 2 the backend already did.
    """
    card = grievance_pii_for_officer_card(_grievance(), mask_sensitive_contact=False)

    assert card["complainant_name"] == PLAIN["complainant_full_name"]
    assert card["phone_number"] == PLAIN["complainant_phone"]
    assert card["email"] == PLAIN["complainant_email"]
    assert card["address"] == PLAIN["complainant_address"]


def test_officer_card_never_emits_ciphertext_for_standard():
    """
    The durable half of the ciphertext arm. Today `reveal_field` decrypts it; after step 3
    `scrub_pii_value` masks it. Either way the officer must never be shown hex.
    """
    card = grievance_pii_for_officer_card(_ciphertext_grievance(), mask_sensitive_contact=False)

    for field in CARD_CONTACT_FIELDS:
        assert card[field] != CIPHERTEXT, f"{field} showed raw ciphertext to an officer"
        assert not looks_like_ciphertext(card[field]), f"{field} showed ciphertext-shaped data"


def test_officer_card_masks_contact_for_seah():
    """TP-15, pinned so steps 2-4 cannot quietly alter SEAH masking."""
    card = grievance_pii_for_officer_card(_grievance(), mask_sensitive_contact=True)

    for field in CARD_CONTACT_FIELDS:
        assert card[field] is None, f"SEAH card leaked {field}"
    # Location context is still available to the SEAH officer.
    assert card["district"] == "Jhapa"
    assert card["province"] == "Koshi"


def test_officer_card_masks_seah_even_when_backend_returns_plaintext():
    """
    Guards the step-2 interaction directly: once the backend decrypts, the SEAH arm
    receives plaintext rather than ciphertext. Masking must not depend on the input
    having been unreadable.
    """
    card = grievance_pii_for_officer_card(_grievance(), mask_sensitive_contact=True)
    assert card["phone_number"] is None
    assert card["complainant_name"] is None


@pytest.mark.parametrize("placeholder", ["Not provided", "unknown", "N/A", "na", "anonymous", "", "   "])
def test_officer_card_treats_placeholders_as_empty(placeholder):
    """`_officer_card_identity` collapses placeholder identities to None — both arms of it."""
    card = grievance_pii_for_officer_card(
        _grievance(complainant_full_name=placeholder), mask_sensitive_contact=False
    )
    assert card["complainant_name"] is None


def test_officer_card_passes_through_missing_fields():
    card = grievance_pii_for_officer_card({}, mask_sensitive_contact=False)
    for field in CARD_CONTACT_FIELDS:
        assert card[field] is None


# ── the reveal path — also entirely uncovered before this file ────────────────────────


def test_grievance_reveal_content_returns_plaintext():
    from ticketing.services.pii_vault import grievance_reveal_content

    content = grievance_reveal_content(_grievance())

    assert content["complainant_name"] == PLAIN["complainant_full_name"]
    assert content["phone_number"] == PLAIN["complainant_phone"]
    assert content["grievance_description"] == "Dust from the road is making the children sick."


def test_grievance_reveal_content_never_returns_ciphertext():
    """Reveal is the one place ciphertext would be most damaging to show verbatim."""
    from ticketing.services.pii_vault import grievance_reveal_content

    content = grievance_reveal_content(_ciphertext_grievance())

    for field in ("complainant_name", "phone_number", "email", "address"):
        assert not looks_like_ciphertext(content[field]), f"reveal returned ciphertext for {field}"


# ── GET /tickets/{id}/pii — end to end, with the client boundary mocked ───────────────
#
# This is the spec's "regression guard for the whole ticket": it is the only test that
# proves the officer card renders plaintext through the real router, and the one D-09
# showed did not exist. Mocked at `ticketing.clients.grievance_api.get_grievance_detail`
# (pii.py imports it inside the function, so the module attribute is resolved at call
# time), which keeps the test independent of whether the *backend* decrypts — which is
# exactly what changes underneath it in step 2.

pytestmark = pytest.mark.integration


def _api_envelope(grievance: dict[str, Any]) -> dict[str, Any]:
    """The real shape of GET /api/grievance/{id} (see pii.py's unwrap at :73)."""
    return {"status": "SUCCESS", "data": {"grievance": grievance}}


@pytest.fixture
def pii_client(db, ctx, monkeypatch):
    """TestClient with auth + db overridden, returning (client, make_ticket, set_payload)."""
    from fastapi.testclient import TestClient

    from ticketing.api.dependencies import CurrentUser, get_authenticated_user, get_db
    from ticketing.api.main import app

    user_id = f"t3-04-pii-officer-{uuid.uuid4().hex[:8]}@grm.local"
    ctx.add_scope(user_id, location_code="P1_JHA", includes_children=True)

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_authenticated_user] = lambda: CurrentUser(
        user_id=user_id, role_keys=["super_admin"]
    )
    try:
        yield TestClient(app), ctx, user_id
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_authenticated_user, None)


@pytest.mark.parametrize(
    "payload_kind",
    [
        "plaintext",   # post-step-2 reality: the backend decrypted before responding
        "ciphertext",  # today's reality: the backend returns pgcrypto hex
    ],
)
def test_get_ticket_pii_never_serves_ciphertext(pii_client, monkeypatch, payload_kind):
    """
    Durable across all four commits: whatever the backend hands back, the officer card
    must not contain ciphertext. Plaintext additionally survives verbatim.
    """
    client, ctx, user_id = pii_client
    ticket = ctx.add_open_ticket(user_id)
    ctx.db.commit()

    grievance = _grievance() if payload_kind == "plaintext" else _ciphertext_grievance()
    monkeypatch.setattr(
        "ticketing.clients.grievance_api.get_grievance_detail",
        lambda gid: _api_envelope(grievance),
    )

    resp = client.get(f"/api/v1/tickets/{ticket.ticket_id}/pii")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body.get("_backend_unavailable") is not True, (
        "landed in the degraded branch — the mock did not take effect, and this test "
        "would then pass vacuously exactly as test_ticket_access_matrix.py does (D-09)"
    )
    assert body["pii_masked"] is False
    for field in CARD_CONTACT_FIELDS:
        assert not looks_like_ciphertext(body[field]), f"served ciphertext for {field}"

    if payload_kind == "plaintext":
        assert body["complainant_name"] == PLAIN["complainant_full_name"]
        assert body["phone_number"] == PLAIN["complainant_phone"]
        assert body["email"] == PLAIN["complainant_email"]
        assert body["address"] == PLAIN["complainant_address"]


def test_get_ticket_pii_serves_plaintext_for_standard_ticket(pii_client, monkeypatch):
    """
    THE headline guard, stated positively and without a parametrize to hide behind:
    a standard ticket's card shows real contact details. Must be green at commits 1-4.
    """
    client, ctx, user_id = pii_client
    ticket = ctx.add_open_ticket(user_id)
    ctx.db.commit()

    monkeypatch.setattr(
        "ticketing.clients.grievance_api.get_grievance_detail",
        lambda gid: _api_envelope(_grievance()),
    )

    body = client.get(f"/api/v1/tickets/{ticket.ticket_id}/pii").json()

    assert body["complainant_name"] == PLAIN["complainant_full_name"]
    assert body["phone_number"] == PLAIN["complainant_phone"]


def test_get_ticket_pii_masks_contact_for_seah_ticket(pii_client, monkeypatch):
    """TP-15 at the router level — pinned so steps 2-4 cannot loosen SEAH masking."""
    client, ctx, user_id = pii_client
    ticket = ctx.add_open_ticket(user_id)
    ticket.is_seah = True
    ctx.db.flush()
    ctx.db.commit()

    monkeypatch.setattr(
        "ticketing.clients.grievance_api.get_grievance_detail",
        lambda gid: _api_envelope(_grievance()),
    )

    body = client.get(f"/api/v1/tickets/{ticket.ticket_id}/pii").json()

    assert body["pii_masked"] is True
    for field in CARD_CONTACT_FIELDS:
        assert body[field] is None, f"SEAH ticket served {field} on the default card"
