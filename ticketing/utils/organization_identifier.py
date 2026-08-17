# SPDX-License-Identifier: Apache-2.0

"""Derive human-readable organization_id values and allocate unique PKs."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

# Mirrors the JS splitter in channels/ticketing-ui/app/settings/page.tsx (generateOrgId).
_TOKEN_RE = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\b)|\d+")


def ascii_alnum(s: str, *, keep_underscore: bool = False) -> str:
    """ASCII [A-Za-z0-9] (optionally underscore) from ``s``, dropping everything else.

    SH-6 (OC-06 F1): organization_id is **ASCII-only** — Nepali is carried in the org
    name / display_name_ne, never in the id. Both the derived-id and explicit-id paths
    route through this, so a Devanagari name can no longer mint a Devanagari id
    (``str.isalnum()`` is True for Devanagari; ``str.isascii()`` gates it out). A pure
    Devanagari name derives to empty, and the caller asks for an explicit id.
    """
    return "".join(
        c for c in s
        if (c.isascii() and c.isalnum()) or (keep_underscore and c == "_")
    )


def _split_name_tokens(name: str) -> list[str]:
    parts = re.split(r"[\s_\-/]+", name.strip())
    tokens: list[str] = []
    for part in parts:
        if not part:
            continue
        found = _TOKEN_RE.findall(part)
        if not found:
            alnum = ascii_alnum(part)
            if alnum:
                tokens.append(alnum)
            continue
        for seg in found:
            alnum = ascii_alnum(seg)
            if alnum:
                tokens.append(alnum)
    return tokens


def slug_core_from_name(name: str) -> str:
    """Short uppercase core from the display name (no country prefix)."""
    tokens = _split_name_tokens(name)
    if not tokens:
        return ""
    if len(tokens) == 1:
        t = tokens[0]
        if t.isdigit():
            return t
        if len(t) <= 3:
            return t.upper()
        return t[:6].upper()
    parts: list[str] = []
    for t in tokens:
        if t.isdigit():
            parts.append(t)
        else:
            parts.append(t[0].upper())
    return "".join(parts)[:12]


def suggested_organization_id(name: str, country_code: str | None) -> str:
    """
    Proposed id before uniqueness suffix.
    Multi-country / no country, or core ADB → no country prefix (legacy rule).
    """
    core = slug_core_from_name(name.strip())
    if not core:
        return ""
    if not country_code or core == "ADB":
        return core
    return f"{country_code}_{core}"


def allocate_unique_organization_id(db: Session, base: str) -> str:
    """
    Use `base` if free; otherwise append _2, _3, ... Total length capped at 64.
    """
    from ticketing.models.organization import Organization

    clean = ascii_alnum(base.upper(), keep_underscore=True)
    if not clean:
        clean = "ORG"
    max_len = 64
    n = 0
    while True:
        if n == 0:
            candidate = clean[:max_len]
        else:
            suffix = f"_{n + 1}"
            prefix_len = max_len - len(suffix)
            candidate = (clean[:prefix_len] if prefix_len > 0 else "") + suffix
        if db.get(Organization, candidate) is None:
            return candidate
        n += 1
        if n > 100_000:
            raise RuntimeError("Could not allocate a unique organization_id")
