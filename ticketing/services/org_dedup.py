"""
Fuzzy duplicate-candidate finder for organizations (SH-4, design §2.4).

The problem: because project owners (``project_admin``) can create participant orgs
(contractors), the registry accretes near-duplicates — the "ADB_2" swamp (OC-06 O2).
The *old* SH-4 behaviour was a silent ``ADB_2`` rename on an exact-name collision.
This module replaces that with a **fuzzy candidate finder** whose result the UI shows
as a **soft flag** ("Possible duplicate: {org} · Use existing / Create anyway") — it is
**never a hard block**; creation always proceeds.

Everything here is **pure** — no DB, no HTTP, no SQLAlchemy — so the scoring and
thresholds are unit-testable with plain dataclasses (mirrors the pure/DB split in
``ticketing/seed/org_import_core.py`` and ``ticketing/services/org_tree.py``). The
router builds :class:`OrgRecord` values from ``ticketing.organizations`` rows and hands
them here; the DB lookup lives in the endpoint, the judgement lives here.

Three match signals (design §2.4), each scored in ``[0, 1]``:

1. **Distinctive name-token overlap.** Tokenize both names, drop a stoplist of generic
   business/organisation words (company, contractor, construction, pvt, ltd, jv, office,
   department, roads, …) so "…Construction JV" and "…Contractor JV" still collide on the
   *distinctive* tokens. Score = Jaccard of the distinctive token sets. Stripping the
   generics means "Kankai" and "Kankai Construction Company" both reduce to ``{kankai}``
   → score 1.0, while a merely-shared place name among otherwise-different distinctive
   tokens yields a low Jaccard and does *not* over-fire.
2. **Corporate email-domain match.** Free providers (gmail, yahoo, hotmail, outlook, …)
   are ignored; a match on a *corporate* domain is a strong signal.
3. **Fuzzy address match.** Normalised ``difflib`` ratio.

A candidate qualifies if **any** signal is strong enough on its own (name Jaccard ≥
:data:`NAME_MATCH_THRESHOLD`, a corporate email-domain match, or address similarity ≥
:data:`ADDRESS_MATCH_THRESHOLD`). Candidates are ranked by a weighted aggregate so a
name+email+address hit sorts above a name-only hit; ties break on ``organization_id`` for
determinism.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Iterable

__all__ = [
    "OrgRecord",
    "DuplicateCandidate",
    "GENERIC_NAME_STOPWORDS",
    "FREE_EMAIL_DOMAINS",
    "NAME_MATCH_THRESHOLD",
    "ADDRESS_MATCH_THRESHOLD",
    "distinctive_tokens",
    "name_similarity",
    "corporate_email_domain",
    "email_domains_match",
    "address_similarity",
    "score_pair",
    "find_duplicate_candidates",
]


# ── Tuning constants (module-level so tests reference the same values) ──────────

# A name is a match on its own at or above this Jaccard of distinctive tokens.
NAME_MATCH_THRESHOLD = 0.5
# An address is a match on its own at or above this normalised difflib ratio.
ADDRESS_MATCH_THRESHOLD = 0.82

# Ranking weights for the aggregate score. Name is primary (officers enter complete org
# names carefully — design §2.4), a corporate email-domain match is a strong corroborator,
# and address nudges the ranking. They need not sum to 1; the aggregate is only an ordering.
NAME_WEIGHT = 0.5
EMAIL_WEIGHT = 0.35
ADDRESS_WEIGHT = 0.15

# Generic words stripped before name comparison so only *distinctive* tokens drive the
# match (design §2.4 stoplist: corporation/company/organization/contractor/construction/
# pvt/ltd/jv/…, plus office/department/roads from the SH-4 ticket). Deliberately business-
# and unit-type words only — **not** geographic names, which stay distinctive so a shared
# district (Jhapa, Morang) is meaningful, not noise.
GENERIC_NAME_STOPWORDS = frozenset(
    {
        # legal / corporate form
        "company", "companies", "co", "corporation", "corporations", "corp",
        "incorporated", "inc", "organization", "organisation", "org",
        "pvt", "private", "ltd", "limited", "llc", "llp",
        "jv", "joint", "venture", "ventures",
        "enterprise", "enterprises", "firm", "group", "groups", "holdings",
        # construction / contracting trade words
        "contractor", "contractors", "construction", "constructions", "constructor",
        "builder", "builders", "engineering", "engineers", "developers", "developer",
        "suppliers", "supplier", "trading", "traders", "trade",
        "services", "service", "works", "solutions",
        "associates", "association", "partners", "partnership",
        # government / office unit words (SH-4 ticket: office/department/roads)
        "office", "offices", "department", "departments", "dept",
        "division", "directorate", "ministry", "authority", "board", "committee",
        "road", "roads",
        # connective filler
        "and", "the", "of", "for", "at", "in", "on", "a", "an",
        "international", "intl", "national",
    }
)

# Free/webmail providers — an email on one of these is a personal address, not a corporate
# identity, so a shared free domain is *not* a dedup signal (design §2.4: "free providers
# gmail/yahoo/hotmail/outlook/… ignored").
FREE_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com", "googlemail.com",
        "yahoo.com", "yahoo.co.in", "yahoo.co.uk", "ymail.com", "rocketmail.com",
        "hotmail.com", "hotmail.co.uk", "outlook.com", "live.com", "msn.com",
        "aol.com", "icloud.com", "me.com", "mac.com",
        "protonmail.com", "proton.me", "gmx.com", "gmx.net",
        "mail.com", "zoho.com", "yandex.com", "yandex.ru",
        "fastmail.com", "hushmail.com", "inbox.com",
    }
)


# ── Records ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class OrgRecord:
    """Minimal, PII-light view of an organization for matching.

    Used for both the *proposed* org (``organization_id`` left blank) and each *existing*
    org. ``email``/``address`` are the SH-4 columns; ``country_code`` is carried for the
    caller's optional pre-filtering (the matcher itself is country-agnostic).
    """

    name: str
    organization_id: str = ""
    email: str | None = None
    address: str | None = None
    country_code: str | None = None


@dataclass(frozen=True)
class DuplicateCandidate:
    """A ranked candidate match returned to the soft-flag UI."""

    organization_id: str
    name: str
    score: float
    reasons: list[str] = field(default_factory=list)
    name_score: float = 0.0
    email_domain_match: bool = False
    address_score: float = 0.0


# ── Name signal ────────────────────────────────────────────────────────────────

# Word characters excluding underscore, Unicode-aware (keeps Devanagari letters so a
# Nepali org name still tokenizes; only ASCII generics are in the stoplist).
_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def distinctive_tokens(name: str | None) -> set[str]:
    """Lowercase word tokens of ``name`` minus generic stopwords, pure digits, and 1-char
    tokens. The remaining set is what actually distinguishes one org from another."""
    if not name:
        return set()
    out: set[str] = set()
    for tok in _TOKEN_RE.findall(name.lower()):
        if len(tok) < 2 or tok.isdigit() or tok in GENERIC_NAME_STOPWORDS:
            continue
        out.add(tok)
    return out


def name_similarity(a: str | None, b: str | None) -> float:
    """Jaccard overlap of the two names' distinctive token sets, in ``[0, 1]``.

    0.0 when either name has no distinctive tokens (e.g. a purely generic name like
    "Construction Company Pvt Ltd") — two content-free names must not be judged duplicates.
    """
    ta, tb = distinctive_tokens(a), distinctive_tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    if not inter:
        return 0.0
    return inter / len(ta | tb)


# ── Email signal ───────────────────────────────────────────────────────────────

def corporate_email_domain(email: str | None) -> str | None:
    """Return the lowercased domain of ``email`` if it is a *corporate* address, else None.

    None for empty/malformed input and for free/webmail providers (a personal address is
    not an org identity signal)."""
    if not email:
        return None
    email = email.strip().lower()
    if email.count("@") != 1:
        return None
    domain = email.rsplit("@", 1)[1].strip().strip(".")
    if not domain or "." not in domain or " " in domain:
        return None
    if domain in FREE_EMAIL_DOMAINS:
        return None
    return domain


def email_domains_match(a: str | None, b: str | None) -> bool:
    """True iff both emails resolve to the *same corporate* domain."""
    da = corporate_email_domain(a)
    db = corporate_email_domain(b)
    return da is not None and da == db


# ── Address signal ─────────────────────────────────────────────────────────────

_ADDR_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_ADDR_WS_RE = re.compile(r"\s+")


def _normalize_address(addr: str | None) -> str:
    if not addr:
        return ""
    cleaned = _ADDR_PUNCT_RE.sub(" ", addr.lower())
    return _ADDR_WS_RE.sub(" ", cleaned).strip()


def address_similarity(a: str | None, b: str | None) -> float:
    """Normalised ``difflib`` similarity ratio of two addresses, in ``[0, 1]``.

    0.0 when either is missing or too short to be meaningful."""
    na, nb = _normalize_address(a), _normalize_address(b)
    if len(na) < 4 or len(nb) < 4:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


# ── Scoring + ranking ──────────────────────────────────────────────────────────

def score_pair(proposed: OrgRecord, existing: OrgRecord) -> DuplicateCandidate | None:
    """Score ``existing`` against ``proposed``; return a candidate or None if below all
    thresholds. Pure — the single place the signal weights and thresholds live."""
    name_score = name_similarity(proposed.name, existing.name)
    email_match = email_domains_match(proposed.email, existing.email)
    addr_score = address_similarity(proposed.address, existing.address)

    reasons: list[str] = []
    if name_score >= NAME_MATCH_THRESHOLD:
        reasons.append("name")
    if email_match:
        reasons.append("email_domain")
    if addr_score >= ADDRESS_MATCH_THRESHOLD:
        reasons.append("address")
    if not reasons:
        return None  # below threshold on every signal → not a candidate

    score = (
        NAME_WEIGHT * name_score
        + EMAIL_WEIGHT * (1.0 if email_match else 0.0)
        + ADDRESS_WEIGHT * addr_score
    )
    return DuplicateCandidate(
        organization_id=existing.organization_id,
        name=existing.name,
        score=round(score, 4),
        reasons=reasons,
        name_score=round(name_score, 4),
        email_domain_match=email_match,
        address_score=round(addr_score, 4),
    )


def find_duplicate_candidates(
    proposed: OrgRecord,
    existing: Iterable[OrgRecord],
    *,
    exclude_id: str | None = None,
    limit: int = 8,
) -> list[DuplicateCandidate]:
    """Rank likely-duplicate candidates for ``proposed`` among ``existing``.

    ``exclude_id`` drops that organization from the scan (an org never dedups against
    itself on update). Results are sorted by aggregate score descending, then
    ``organization_id`` ascending for stable ordering, and truncated to ``limit``.
    Country scoping, if any, is the caller's concern — this matcher is country-agnostic.
    """
    candidates: list[DuplicateCandidate] = []
    for org in existing:
        if exclude_id and org.organization_id == exclude_id:
            continue
        cand = score_pair(proposed, org)
        if cand is not None:
            candidates.append(cand)
    candidates.sort(key=lambda c: (-c.score, c.organization_id))
    if limit is not None and limit >= 0:
        candidates = candidates[:limit]
    return candidates
