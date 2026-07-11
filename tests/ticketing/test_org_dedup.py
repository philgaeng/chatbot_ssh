"""SH-4 — fuzzy duplicate-candidate finder for organizations (design §2.4).

Two layers (mirrors test_org_tree.py):
  - **pure** (no app, no DB, runs in CI): the matcher — distinctive name tokens + generic
    stoplist, corporate-vs-free email domains, fuzzy address, scoring/thresholds, ranking.
  - **integration** (``@pytest.mark.integration``, needs live DB + seed): create/update
    persist email+address; the preview endpoint returns candidates; **create is never
    blocked** by a near-duplicate; the preview needs only auth while create needs the
    org-structure write gate.
"""
from __future__ import annotations

import uuid

import pytest

from ticketing.services.org_dedup import (
    ADDRESS_MATCH_THRESHOLD,
    FREE_EMAIL_DOMAINS,
    GENERIC_NAME_STOPWORDS,
    NAME_MATCH_THRESHOLD,
    OrgRecord,
    address_similarity,
    corporate_email_domain,
    distinctive_tokens,
    email_domains_match,
    find_duplicate_candidates,
    name_similarity,
    score_pair,
)


# ══════════════════════════════════════════════════════════════════════════════
# Pure: tokenization + stoplist
# ══════════════════════════════════════════════════════════════════════════════

def test_distinctive_tokens_drop_generics_digits_and_short():
    # "construction", "pvt", "ltd", "company", "the", "of" are generic; "5" is a digit;
    # only the distinctive place/brand tokens survive.
    assert distinctive_tokens("Kankai Construction Company Pvt. Ltd.") == {"kankai"}
    assert distinctive_tokens("Jhapa Division Road Office") == {"jhapa"}
    assert distinctive_tokens("Sector 5 Builders") == {"sector"}  # "5" dropped, "builders" generic
    assert distinctive_tokens("") == set()
    assert distinctive_tokens(None) == set()


def test_generic_stoplist_covers_the_documented_words():
    # The words the SH-4 ticket / design §2.4 name explicitly.
    for w in ("company", "corporation", "organization", "contractor", "construction",
              "pvt", "ltd", "jv", "office", "department", "roads"):
        assert w in GENERIC_NAME_STOPWORDS


def test_purely_generic_name_has_no_distinctive_tokens():
    # "Department of Roads" is all-generic → nothing to match on.
    assert distinctive_tokens("Department of Roads") == set()


# ══════════════════════════════════════════════════════════════════════════════
# Pure: name similarity
# ══════════════════════════════════════════════════════════════════════════════

def test_name_exact_and_near_match():
    assert name_similarity("Kankai Construction Pvt Ltd", "Kankai Constructions") == 1.0
    # near: one extra distinctive token → Jaccard 2/3, still >= threshold
    assert name_similarity("Kankai Nirman Sewa", "Kankai Nirman") == pytest.approx(2 / 3)
    assert name_similarity("Kankai Nirman", "Kankai Nirman Sewa") >= NAME_MATCH_THRESHOLD


def test_name_stoplist_lets_variants_collide():
    # "…Construction JV" and "…Contractor JV" both reduce to the distinctive brand token.
    assert name_similarity("Everest Construction JV", "Everest Contractor JV") == 1.0


def test_name_below_threshold_and_generic_only():
    # different brands → no shared distinctive token
    assert name_similarity("Kankai Construction", "Mechi Builders") == 0.0
    # a single shared *place* among otherwise-different distinctive tokens does not over-fire
    assert name_similarity("Jhapa Division Road Office", "Jhapa Nirman Sewa Kendra") < NAME_MATCH_THRESHOLD
    # two all-generic names are never a name match
    assert name_similarity("Department of Roads", "Department of Railways") == 0.0


# ══════════════════════════════════════════════════════════════════════════════
# Pure: email domain (corporate vs free)
# ══════════════════════════════════════════════════════════════════════════════

def test_corporate_email_domain_extraction():
    assert corporate_email_domain("info@KankaiCon.com.np") == "kankaicon.com.np"
    assert corporate_email_domain("bad-no-at") is None
    assert corporate_email_domain("a@b@c.com") is None
    assert corporate_email_domain("nodomain@") is None
    assert corporate_email_domain(None) is None


def test_free_providers_are_ignored():
    for free in ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com"):
        assert free in FREE_EMAIL_DOMAINS
        assert corporate_email_domain(f"someone@{free}") is None


def test_email_domains_match_only_on_corporate():
    assert email_domains_match("a@kankaicon.com.np", "hr@kankaicon.com.np") is True
    # same *free* domain is not a signal
    assert email_domains_match("a@gmail.com", "b@gmail.com") is False
    # different corporate domains
    assert email_domains_match("a@kankaicon.com.np", "b@mechibuild.com") is False
    assert email_domains_match(None, "b@x.com") is False


# ══════════════════════════════════════════════════════════════════════════════
# Pure: address similarity
# ══════════════════════════════════════════════════════════════════════════════

def test_address_similarity_high_and_low():
    high = address_similarity("Birtamod-5, Jhapa, Koshi", "Birtamod 5, Jhapa")
    assert high >= ADDRESS_MATCH_THRESHOLD
    assert address_similarity("Kathmandu", "Pokhara") < ADDRESS_MATCH_THRESHOLD
    # missing / too short → 0
    assert address_similarity(None, "Birtamod, Jhapa") == 0.0
    assert address_similarity("ab", "ab") == 0.0


# ══════════════════════════════════════════════════════════════════════════════
# Pure: score_pair — each signal qualifies alone; below all → None
# ══════════════════════════════════════════════════════════════════════════════

def _rec(name, oid="X", email=None, address=None):
    return OrgRecord(name=name, organization_id=oid, email=email, address=address)


def test_score_pair_qualifies_on_name_alone():
    c = score_pair(_rec("Kankai Construction Pvt Ltd", "P"), _rec("Kankai Constructions", "E"))
    assert c is not None and "name" in c.reasons and c.name_score == 1.0


def test_score_pair_qualifies_on_email_alone():
    c = score_pair(
        _rec("Alpha Traders", "P", email="info@kankaicon.com.np"),
        _rec("Beta Suppliers", "E", email="hr@kankaicon.com.np"),
    )
    assert c is not None and c.reasons == ["email_domain"] and c.email_domain_match


def test_score_pair_qualifies_on_address_alone():
    c = score_pair(
        _rec("Alpha", "P", address="Birtamod-5, Jhapa, Koshi"),
        _rec("Beta", "E", address="Birtamod 5, Jhapa"),
    )
    assert c is not None and c.reasons == ["address"]


def test_score_pair_below_all_thresholds_is_none():
    assert score_pair(_rec("Mechi Builders", "P"), _rec("Kankai Traders", "E")) is None
    # free-domain email + unrelated names → nothing
    assert score_pair(
        _rec("Mechi Builders", "P", email="a@gmail.com"),
        _rec("Kankai Traders", "E", email="b@gmail.com"),
    ) is None


# ══════════════════════════════════════════════════════════════════════════════
# Pure: find_duplicate_candidates — ranking, exclude, limit, empty
# ══════════════════════════════════════════════════════════════════════════════

def test_ranking_multi_signal_outranks_name_only():
    proposed = _rec("Kankai Construction", "P", email="info@kankaicon.com.np",
                    address="Birtamod-5, Jhapa")
    existing = [
        # full three-signal hit
        _rec("Kankai Constructions", "STRONG", email="hr@kankaicon.com.np",
             address="Birtamod 5, Jhapa"),
        # name-only hit
        _rec("Kankai Nirman Construction", "NAMEONLY"),
        # no match at all
        _rec("Mechi Builders", "NONE"),
    ]
    ranked = find_duplicate_candidates(proposed, existing)
    ids = [c.organization_id for c in ranked]
    assert ids == ["STRONG", "NAMEONLY"]  # NONE excluded, STRONG first
    assert ranked[0].score > ranked[1].score
    assert set(ranked[0].reasons) == {"name", "email_domain", "address"}


def test_exclude_self_and_empty():
    proposed = _rec("Kankai Construction", "SELF")
    existing = [_rec("Kankai Constructions", "SELF"), _rec("Kankai Nirman", "OTHER")]
    ids = [c.organization_id for c in find_duplicate_candidates(proposed, existing, exclude_id="SELF")]
    assert ids == ["OTHER"]
    assert find_duplicate_candidates(proposed, []) == []


def test_ranking_ties_break_on_id_and_limit_applies():
    proposed = _rec("Kankai Construction", "P")
    existing = [_rec("Kankai Constructions", oid) for oid in ("ZZZ", "AAA", "MMM")]
    ranked = find_duplicate_candidates(proposed, existing, limit=2)
    assert [c.organization_id for c in ranked] == ["AAA", "MMM"]  # equal score → id asc, capped at 2


# ══════════════════════════════════════════════════════════════════════════════
# Integration — router + DB (needs live seeded DB)
# ══════════════════════════════════════════════════════════════════════════════

def _super():
    from ticketing.api.dependencies import CurrentUser
    return CurrentUser(user_id="s@grm.local", role_keys=["super_admin"])


def _operational():
    from ticketing.api.dependencies import CurrentUser
    return CurrentUser(user_id="o@grm.local", role_keys=["site_safeguards_focal_person"])


def _client(user):
    from fastapi.testclient import TestClient

    from ticketing.api.dependencies import get_authenticated_user
    from ticketing.api.main import app
    from ticketing.models.base import SessionLocal, get_db

    db = SessionLocal()

    def _db():
        yield db

    app.dependency_overrides[get_authenticated_user] = lambda: user
    app.dependency_overrides[get_db] = _db
    return app, TestClient(app), db


def _oid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:6].upper()}"


@pytest.fixture
def cleanup_orgs():
    ids: list[str] = []
    yield ids
    from ticketing.models.base import SessionLocal
    from ticketing.models.organization import Organization

    s = SessionLocal()
    try:
        for oid in ids:
            obj = s.get(Organization, oid)
            if obj:
                s.delete(obj)
        s.commit()
    finally:
        s.close()


@pytest.mark.integration
def test_create_and_update_persist_email_and_address(cleanup_orgs):
    app, client, db = _client(_super())
    try:
        oid = _oid("SH4EA")
        cleanup_orgs.append(oid)
        res = client.post(
            "/api/v1/organizations",
            json={
                "organization_id": oid, "name": "SH4 Email/Addr Org",
                "org_category": "third_party", "unit_type": "company",
                "email": "info@sh4corp.example", "address": "Birtamod-5, Jhapa",
            },
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["email"] == "info@sh4corp.example"
        assert body["address"] == "Birtamod-5, Jhapa"

        # Round-trip from the DB via the list endpoint (proves the columns persisted).
        got = client.get(f"/api/v1/organizations?root_id={oid}&active_only=false").json()
        assert got and got[0]["email"] == "info@sh4corp.example"

        # PATCH updates both; "" clears to null.
        res2 = client.patch(
            f"/api/v1/organizations/{oid}",
            json={"email": "new@sh4corp.example", "address": ""},
        )
        assert res2.status_code == 200, res2.text
        assert res2.json()["email"] == "new@sh4corp.example"
        assert res2.json()["address"] is None
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.integration
def test_preview_returns_candidate_and_create_is_never_blocked(cleanup_orgs):
    app, client, db = _client(_super())
    try:
        nonce = uuid.uuid4().hex[:6]
        brand = f"Zylkappa{nonce}"  # distinctive token that matches nothing seeded
        first_id, dup_id = _oid("SH4DUP"), _oid("SH4DUP2")
        cleanup_orgs.extend([first_id, dup_id])

        r1 = client.post(
            "/api/v1/organizations",
            json={"organization_id": first_id, "name": f"{brand} Construction Pvt Ltd",
                  "org_category": "third_party", "unit_type": "company",
                  "email": "info@zylkappa.example"},
        )
        assert r1.status_code == 201, r1.text

        # Preview surfaces the near-duplicate (name + corporate email).
        prev = client.post(
            "/api/v1/organizations/duplicate-candidates",
            json={"name": f"{brand} Constructions", "email": "hr@zylkappa.example",
                  "country_code": None},
        )
        assert prev.status_code == 200, prev.text
        cand_ids = {c["organization_id"] for c in prev.json()}
        assert first_id in cand_ids
        hit = next(c for c in prev.json() if c["organization_id"] == first_id)
        assert "name" in hit["reasons"] and hit["email_domain_match"] is True

        # Creation is NEVER blocked by a duplicate — the near-dup still creates (201).
        r2 = client.post(
            "/api/v1/organizations",
            json={"organization_id": dup_id, "name": f"{brand} Constructions",
                  "org_category": "third_party", "unit_type": "company"},
        )
        assert r2.status_code == 201, r2.text
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.integration
def test_preview_needs_only_auth_but_create_needs_write_gate():
    # An operational (non-admin) user may run the *preview* (read-only soft flag) …
    app, client, db = _client(_operational())
    try:
        prev = client.post(
            "/api/v1/organizations/duplicate-candidates",
            json={"name": "Anything Ltd"},
        )
        assert prev.status_code == 200, prev.text
        # … but may NOT create — that carries the MANAGE_ORG_STRUCTURE gate.
        res = client.post(
            "/api/v1/organizations",
            json={"name": "Operational Cannot Create", "org_category": "third_party"},
        )
        assert res.status_code == 403, res.text
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.integration
def test_preview_empty_name_returns_no_candidates():
    app, client, db = _client(_super())
    try:
        res = client.post("/api/v1/organizations/duplicate-candidates", json={"name": "   "})
        assert res.status_code == 200
        assert res.json() == []
    finally:
        app.dependency_overrides.clear()
        db.close()
