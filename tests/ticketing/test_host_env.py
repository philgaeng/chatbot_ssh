"""
D-36 — the host test bootstrap must agree with the database it talks to.

``_host_env.configure_host_test_env`` runs before any ``ticketing.*`` import and decides
which Postgres host pytest connects to. It used to seed the DB identity from ``env.local``.
That is dead config: every compose service hardcodes ``POSTGRES_DB``/``USER``/``PASSWORD``
in its own ``environment:`` block, so nothing in the stack reads env.local's values — but
host pytest did, and a drifted env.local failed the whole suite with
``password authentication failed``, which reads as a code regression rather than config.

These tests pin the invariant so the env.local read is not "helpfully" restored. They are
green on today's code — they pin behaviour, they do not fix a bug (the fix is in
``_host_env.py`` itself).
"""
from __future__ import annotations

import os

import pytest

from tests.ticketing import _host_env

# Mirrors the hardcoded compose values (docker-compose.yml:27-29) and .env.example.
COMPOSE_DB_IDENTITY = {
    "POSTGRES_USER": "user",
    "POSTGRES_PASSWORD": "password",
    "POSTGRES_DB": "app_db",
}

# A realistically drifted env.local — these are the pre-compose values that broke D-36.
STALE_ENV_LOCAL = {
    "POSTGRES_HOST": "localhost",
    "POSTGRES_USER": "nepal_grievance_admin",
    "POSTGRES_PASSWORD": "K9!mP2$vL5nX8&qR4jW7",
    "POSTGRES_DB": "grievance_db",
    "TICKETING_SECRET_KEY": "from-env-local",
}

_DB_KEYS = ("POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")


@pytest.fixture
def stale_env_local(monkeypatch):
    """Run configure_host_test_env() against a drifted env.local, on a clean env."""
    monkeypatch.setattr(_host_env, "_parse_env_local", lambda _path: dict(STALE_ENV_LOCAL))
    monkeypatch.setattr(_host_env, "_in_ticketing_container", lambda: False)
    for key in (*_DB_KEYS, "TICKETING_SECRET_KEY"):
        monkeypatch.delenv(key, raising=False)
    yield monkeypatch
    # The bootstrap caches settings off the env it just built; monkeypatch restores the
    # env but not the cache, so clear it or later tests read this test's values.
    from ticketing.config.settings import get_settings

    get_settings.cache_clear()


def test_stale_env_local_db_credentials_are_ignored(stale_env_local):
    """The DB identity comes from compose's hardcoded values, never from env.local."""
    _host_env.configure_host_test_env()

    for key, expected in COMPOSE_DB_IDENTITY.items():
        assert os.environ[key] == expected, (
            f"{key} came from env.local ({STALE_ENV_LOCAL[key]!r}) instead of compose "
            f"({expected!r}) — host pytest would talk to a DB that does not exist"
        )


def test_non_db_settings_still_come_from_env_local(stale_env_local):
    """Only the DB identity is fenced off — env.local is still the source for the rest.

    Guards the over-correction: deleting the env.local read wholesale would silently
    drop TICKETING_SECRET_KEY/KEYCLOAK_ISSUER/APP_ENV/AUTH_MODE.
    """
    _host_env.configure_host_test_env()

    assert os.environ["TICKETING_SECRET_KEY"] == "from-env-local"


def test_host_port_is_the_published_one_not_bare_5432(stale_env_local):
    """env.local says POSTGRES_PORT=5432 (the in-network port). The host needs 5433."""
    _host_env.configure_host_test_env()

    assert os.environ["POSTGRES_PORT"] == "5433"


def test_explicit_shell_override_still_wins(stale_env_local):
    """`POSTGRES_DB=scratch pytest ...` must keep working — it is how scratch DBs are used."""
    stale_env_local.setenv("POSTGRES_DB", "app_db_scratch")
    stale_env_local.setenv("POSTGRES_PORT", "6543")

    _host_env.configure_host_test_env()

    assert os.environ["POSTGRES_DB"] == "app_db_scratch"
    assert os.environ["POSTGRES_PORT"] == "6543"
    # …and the un-overridden ones still come from compose, not env.local.
    assert os.environ["POSTGRES_USER"] == "user"
