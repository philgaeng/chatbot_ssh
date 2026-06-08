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

    # env.local values first (except port — host must not use bare 5432 unless set explicitly)
    for key in (
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "POSTGRES_HOST",
        "TICKETING_SECRET_KEY",
        "KEYCLOAK_ISSUER",
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
    # Dev bypass for API tests that import the FastAPI app
    os.environ.setdefault("KEYCLOAK_ISSUER", "")

    try:
        from ticketing.config.settings import get_settings

        get_settings.cache_clear()
    except ImportError:
        pass
