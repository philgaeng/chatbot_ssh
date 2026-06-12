"""Shared validation for project short_code and package package_code."""
from __future__ import annotations

import re

ENTITY_CODE_PATTERN = re.compile(r"^[A-Z0-9_]{1,8}$")
ENTITY_CODE_MAX_LEN = 8


class EntityCodeError(ValueError):
    pass


def normalize_entity_code(raw: str | None) -> str:
    """Uppercase, strip, keep only A-Z 0-9 _, max 8 chars."""
    if raw is None:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", (raw or "").strip().upper())
    return cleaned[:ENTITY_CODE_MAX_LEN]


def validate_entity_code(raw: str | None, *, field: str = "Code") -> str:
    """Return normalized code or raise EntityCodeError."""
    code = normalize_entity_code(raw)
    if not code:
        raise EntityCodeError(f"{field} is required.")
    if not ENTITY_CODE_PATTERN.match(code):
        raise EntityCodeError(
            f"{field} must be 1–{ENTITY_CODE_MAX_LEN} characters: A–Z, 0–9, underscore."
        )
    return code
