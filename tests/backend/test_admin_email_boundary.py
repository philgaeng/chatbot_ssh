# SPDX-License-Identifier: Apache-2.0

"""The admin-notification boundary (F-19).

Until 2026-09-03 there was no admin email template. `GRIEVANCE_RECAP_ADMIN_BODY` was
*assigned* from `GRIEVANCE_RECAP_COMPLAINANT_BODY`, so the configured admin list received
the complainant's own receipt — raw narrative, name, phone, address, email — on every
submission, with no gate for sensitive cases. `docs/dpg/pii-egress-inventory.md` ranks that
leg **above** the model call for likelihood of real exposure.

These tests pin the two controls that replaced it. They are deliberately written against
**rendered output** and against **the template strings themselves**, not against the
projection helper alone: a test that only exercises the helper passes while the call site
leaks, which is the decorative-test failure a mutation exposed during DPG-34.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any, Dict

import pytest

from backend.actions.services.messaging import recap_email
from backend.config.constants import EMAIL_TEMPLATES

ADMIN_BODIES = ("GRIEVANCE_RECAP_ADMIN_BODY", "GRIEVANCE_STATUS_CHECK_REQUEST_FOLLOW_UP")

# Anything an admin body must never render. Not an exhaustive PII list — these are the
# exact fields the pre-fix templates carried.
FORBIDDEN_PLACEHOLDERS = {
    "grievance_description",
    "grievance_details",
    "complainant_name",
    "complainant_full_name",
    "complainant_phone",
    "complainant_email",
    "complainant_address",
    "complainant_municipality",
    "complainant_village",
}

PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)[^}]*\}")

NARRATIVE = "Ram Bahadur Shrestha of Duhabi called me on 9812345678 and threatened me."


def _grievance(**overrides: Any) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "grievance_id": "GR-2026-0001",
        "grievance_timestamp": "2026-09-03 10:00",
        "grievance_timeline": "2026-10-03",
        "grievance_categories": ["Air Pollution - Dust"],
        "grievance_location": "Jhapa",
        "grievance_summary": "<PERSON_1> reports dust entering the house.",
        "grievance_description": NARRATIVE,
        "complainant_full_name": "Ram Bahadur Shrestha",
        "complainant_name": "Ram Bahadur Shrestha",
        "complainant_phone": "9812345678",
        "complainant_email": "ram@example.com",
        "complainant_address": "Ward 4, Duhabi",
        "grievance_sensitive_issue": False,
    }
    data.update(overrides)
    return data


# ── The templates themselves ────────────────────────────────────────────────────


@pytest.mark.parametrize("body_name", ADMIN_BODIES)
@pytest.mark.parametrize("language", ["en", "ne"])
def test_admin_template_references_only_safe_fields(body_name: str, language: str) -> None:
    """Parses the template string. Adding {grievance_description} fails the build here."""
    template = EMAIL_TEMPLATES[body_name][language]
    referenced = set(PLACEHOLDER.findall(template))
    allowed = set(recap_email.ADMIN_SAFE_FIELDS) | {"portal_link_html"}
    assert referenced <= allowed, (
        f"{body_name}[{language}] references fields outside ADMIN_SAFE_FIELDS: "
        f"{sorted(referenced - allowed)}"
    )


@pytest.mark.parametrize("body_name", ADMIN_BODIES)
@pytest.mark.parametrize("language", ["en", "ne"])
def test_admin_template_names_no_forbidden_field(body_name: str, language: str) -> None:
    """The explicit half: name the fields that caused F-19, so the failure message says so."""
    template = EMAIL_TEMPLATES[body_name][language]
    referenced = set(PLACEHOLDER.findall(template))
    assert not (referenced & FORBIDDEN_PLACEHOLDERS), (
        f"{body_name}[{language}] would mail {sorted(referenced & FORBIDDEN_PLACEHOLDERS)} "
        "to the admin list — this is exactly F-19"
    )


def test_the_admin_body_is_not_the_complainant_body() -> None:
    """The precise regression: F-19 was one assignment, and it could be re-made."""
    assert (
        EMAIL_TEMPLATES["GRIEVANCE_RECAP_ADMIN_BODY"]
        is not EMAIL_TEMPLATES["GRIEVANCE_RECAP_COMPLAINANT_BODY"]
    )
    assert (
        EMAIL_TEMPLATES["GRIEVANCE_RECAP_ADMIN_BODY"]["en"]
        != EMAIL_TEMPLATES["GRIEVANCE_RECAP_COMPLAINANT_BODY"]["en"]
    )


def test_the_complainant_body_still_carries_their_own_record() -> None:
    """Guards the over-correction: the complainant's receipt is their own data and must
    keep the narrative. A fix that scrubbed both would 'pass' every test above."""
    body = EMAIL_TEMPLATES["GRIEVANCE_RECAP_COMPLAINANT_BODY"]["en"]
    assert "{grievance_description}" in body


# ── The projection ──────────────────────────────────────────────────────────────


def test_projection_drops_every_unsafe_key() -> None:
    safe = recap_email._project_admin_fields(_grievance(), not_provided="n/a")
    assert set(safe) == set(recap_email.ADMIN_SAFE_FIELDS) | {"portal_link_html"}
    rendered = " ".join(str(v) for v in safe.values())
    for secret in (NARRATIVE, "Ram Bahadur Shrestha", "9812345678", "ram@example.com"):
        assert secret not in rendered


def test_projection_renders_category_lists_as_text() -> None:
    safe = recap_email._project_admin_fields(
        _grievance(grievance_categories=["A", "B"]), not_provided="n/a"
    )
    assert safe["grievance_categories"] == "A, B"


# ── The send, end to end ────────────────────────────────────────────────────────


def _send(monkeypatch: pytest.MonkeyPatch, data: Dict[str, Any], body_name: str) -> list:
    sent: list = []
    monkeypatch.setattr(recap_email, "ADMIN_EMAILS", ["admin@example.org"])
    monkeypatch.setattr(
        "backend.clients.messaging_api.send_email",
        lambda to, subject, body, context=None: sent.append((to, subject, body)),
    )
    asyncio.run(
        recap_email.send_recap_email_to_admin(
            data, body_name, language_code="en", not_provided="n/a"
        )
    )
    return sent


@pytest.mark.parametrize("body_name", ADMIN_BODIES)
def test_a_sent_admin_email_contains_no_pii(
    monkeypatch: pytest.MonkeyPatch, body_name: str
) -> None:
    """The one that matters: what actually goes over the wire."""
    sent = _send(monkeypatch, _grievance(), body_name)
    assert len(sent) == 1
    _, subject, body = sent[0]
    for secret in (NARRATIVE, "Ram Bahadur Shrestha", "9812345678", "ram@example.com", "Ward 4"):
        assert secret not in body, f"{body_name} leaked {secret!r}"
        assert secret not in subject
    assert "GR-2026-0001" in body


def test_a_sensitive_grievance_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """SEAH cases are visible only to officers cast on the sensitive workflow. The admin
    list is not that cast, so the notification is suppressed rather than trimmed —
    categories and a summary would themselves disclose that a SEAH case exists."""
    sent = _send(
        monkeypatch,
        _grievance(grievance_sensitive_issue=True),
        "GRIEVANCE_RECAP_ADMIN_BODY",
    )
    assert sent == []


def test_unknown_sensitivity_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """`.get(key, False)` would read 'the caller never told us' as 'not sensitive'. That
    is the direction that mails a survivor's case to a list that must not see it."""
    data = _grievance()
    del data["grievance_sensitive_issue"]
    assert _send(monkeypatch, data, "GRIEVANCE_RECAP_ADMIN_BODY") == []


def test_a_template_referencing_an_unsafe_field_refuses_to_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The second layer. If the build-time check above is ever bypassed, the send must
    fail rather than fall back to the full dict — falling back is what created F-19."""
    monkeypatch.setitem(
        EMAIL_TEMPLATES,
        "GRIEVANCE_RECAP_ADMIN_BODY",
        {"en": "<p>{grievance_id} {grievance_description}</p>", "ne": "x"},
    )
    assert _send(monkeypatch, _grievance(), "GRIEVANCE_RECAP_ADMIN_BODY") == []


def test_no_portal_url_yields_no_fabricated_link(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(recap_email, "GRM_PORTAL_BASE_URL", "")
    html = recap_email._admin_portal_link_html()
    assert "href" not in html and "http" not in html


def test_a_configured_portal_url_becomes_a_link(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(recap_email, "GRM_PORTAL_BASE_URL", "https://grm.example.org/")
    html = recap_email._admin_portal_link_html()
    assert 'href="https://grm.example.org/tickets"' in html
