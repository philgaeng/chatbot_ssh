"""
Host-side pytest bootstrap — run before any ``ticketing.*`` import.

Docker ``db`` is not on host :5432 by default; ``docker-compose.grm.yml`` publishes
``${POSTGRES_HOST_PORT:-5433}:5432``. Host pytest must use that port with the
compose credentials (user/password/app_db), not whatever else is on :5432.

Skipped inside the ``ticketing_api`` container (``TICKETING_TEST_IN_DOCKER=1``).
"""
from __future__ import annotations

import os
from pathlib import Path


def _in_ticketing_container() -> bool:
    if os.environ.get("TICKETING_TEST_IN_DOCKER") == "1":
        return True
    return Path("/app/ticketing/api/main.py").is_file()


def _parse_env_local(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


def configure_host_test_env() -> None:
    """Point host pytest at the Docker Postgres port; load ``env.local`` defaults."""
    if _in_ticketing_container():
        return

    repo_root = Path(__file__).resolve().parents[2]
    env_local = _parse_env_local(repo_root / "env.local")

    # NOTE: the DB identity (host/user/password/db) is deliberately NOT read from
    # env.local. Every compose service hardcodes POSTGRES_DB/USER/PASSWORD in its own
    # `environment:` block (docker-compose.yml:27-29, and five more), so env.local's
    # POSTGRES_* values are dead config — no container ever reads them. Honouring them
    # here is the one way host pytest can disagree with the database it is talking to.
    #
    # That is not hypothetical (D-36, 2026-07-15): a drifted env.local
    # (`nepal_grievance_admin`/`grievance_db` — the pre-compose values, still the
    # defaults in some checkouts) made the whole host suite fail with
    # `password authentication failed`, which reads as a code regression rather than
    # config. The correct values are the setdefault fallbacks below, which mirror
    # compose; `.env.example` already agrees with them.
    #
    # An explicit shell override still wins (`key not in os.environ`), so
    # `POSTGRES_DB=scratch pytest ...` keeps working.
    for key in (
        "TICKETING_SECRET_KEY",
        "KEYCLOAK_ISSUER",
        "APP_ENV",
        "AUTH_MODE",
    ):
        if key in env_local and key not in os.environ:
            os.environ[key] = env_local[key]

    os.environ.setdefault("POSTGRES_HOST", "localhost")
    if "POSTGRES_PORT" not in os.environ:
        # Published by docker-compose.grm.yml db.ports (not the in-network 5432).
        os.environ["POSTGRES_PORT"] = env_local.get(
            "POSTGRES_HOST_PORT",
            os.environ.get("POSTGRES_HOST_PORT", "5433"),
        )

    os.environ.setdefault("POSTGRES_USER", "user")
    os.environ.setdefault("POSTGRES_PASSWORD", "password")
    os.environ.setdefault("POSTGRES_DB", "app_db")
    # Dev bypass for API tests that import the FastAPI app (APP_ENV=dev AUTH_MODE=bypass).
    os.environ.setdefault("APP_ENV", "dev")
    os.environ.setdefault("AUTH_MODE", "bypass")
    os.environ.setdefault("KEYCLOAK_ISSUER", "")

    try:
        from ticketing.config.settings import get_settings

        get_settings.cache_clear()
    except ImportError:
        pass
