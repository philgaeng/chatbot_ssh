"""
Verify JWTs issued by Keycloak using the realm JWKS endpoint.
Keys are cached for 5 minutes to avoid a fetch on every request.
"""
from __future__ import annotations

import time
from typing import Any

import httpx
from jose import jwt

from ticketing.config.settings import get_settings

_jwks_cache: dict[str, Any] = {}
_cache_ts: float = 0.0
_CACHE_TTL = 300  # seconds


def _get_jwks() -> dict[str, Any]:
    global _jwks_cache, _cache_ts
    if time.time() - _cache_ts < _CACHE_TTL:
        return _jwks_cache
    settings = get_settings()
    url = f"{settings.keycloak_issuer}/protocol/openid-connect/certs"
    resp = httpx.get(url, timeout=5.0)
    resp.raise_for_status()
    _jwks_cache = resp.json()
    _cache_ts = time.time()
    return _jwks_cache


def verify_keycloak_token(token: str) -> dict[str, Any]:
    """Decode and verify a Keycloak-issued JWT. Raises jose.JWTError on failure."""
    settings = get_settings()
    jwks = _get_jwks()
    return jwt.decode(
        token,
        jwks,
        algorithms=["RS256"],
        audience=settings.keycloak_client_id,
        issuer=settings.keycloak_issuer,
    )
