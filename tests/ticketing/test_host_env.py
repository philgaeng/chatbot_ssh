# SPDX-License-Identifier: Apache-2.0
"""
The host test bootstrap must agree with the database it talks to.

``_host_env.configure_host_test_env`` runs before any ``ticketing.*`` import and decides
which Postgres the host-side suite connects to. It reads the DB identity from
``env.local`` — the same file every compose service interpolates
``POSTGRES_USER``/``PASSWORD``/``DB`` from with ``${VAR:?}``. One source, so host pytest
and the running stack cannot drift apart.

⚠ **This pins the opposite of what it once did, and the reversal is the point.** While
eleven compose services hardcoded those three variables in their own ``environment:``
blocks — which override ``env_file:`` — env.local's values were read by nothing, and
honouring them here was the one way host pytest could disagree with the database
(D-36: the whole suite failed with ``password authentication failed``, which reads as a
code regression rather than config). The literals are gone and env.local is live, so
hardcoding credentials here would now *cause* D-36 rather than prevent it.

These tests are green on today's code: they pin behaviour, they do not fix a bug.
"""
from __future__ import annotations

import os

import pytest

from tests.ticketing import _host_env

# What a correct env.local supplies. These are values, not a second source of truth —
# the tests below assert the bootstrap *propagates env.local*, whatever it holds.
ENV_LOCAL = {
    "POSTGRES_HOST": "localhost",
    "POSTGRES_PORT": "5432",  # the in-network port; the host must not use it
    "POSTGRES_USER": "user",
    "POSTGRES_PASSWORD": "rotated-secret-from-sops",
    "POSTGRES_DB": "app_db",
    "TICKETING_SECRET_KEY": "from-env-local",
}

_DB_KEYS = ("POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")


def _clean(monkeypatch, env_local):
    """Run configure_host_test_env() against a given env.local, on a clean environment."""
    monkeypatch.setattr(_host_env, "_parse_env_local", lambda _path: dict(env_local))
    monkeypatch.setattr(_host_env, "_in_ticketing_container", lambda: False)
    for key in (*_DB_KEYS, "TICKETING_SECRET_KEY", "POSTGRES_HOST_PORT"):
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


@pytest.fixture
def env_local(monkeypatch):
    yield _clean(monkeypatch, ENV_LOCAL)
    # The bootstrap caches settings off the env it just built; monkeypatch restores the
    # env but not the cache, so clear it or later tests read this test's values.
    from ticketing.config.settings import get_settings

    get_settings.cache_clear()


def test_db_credentials_come_from_env_local(env_local):
    """The identity is env.local's, because that is what the containers were given."""
    _host_env.configure_host_test_env()

    for key in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"):
        assert os.environ[key] == ENV_LOCAL[key], (
            f"{key} did not come from env.local — host pytest would authenticate with a "
            f"credential no container holds, which is D-36 with the sign flipped"
        )


def test_no_credential_is_hardcoded_in_the_bootstrap(env_local):
    """A literal here silently overrides a rotated secret. Rotation must be enough.

    The mutation this catches: reinstating `os.environ.setdefault("POSTGRES_PASSWORD",
    "password")`. That passes every other test in this file and breaks the suite the
    next time the database password is rotated — which is exactly what happened.
    """
    source = (_host_env.__file__ and open(_host_env.__file__, encoding="utf-8").read()) or ""
    for banned in ('setdefault("POSTGRES_USER"', 'setdefault("POSTGRES_PASSWORD"', 'setdefault("POSTGRES_DB"'):
        assert banned not in source, (
            f"{banned}…) reintroduces a hardcoded DB credential in the bootstrap; "
            f"the value belongs in env.local, which both this file and compose read"
        )


def test_missing_credentials_fail_with_an_actionable_message(monkeypatch):
    """No env.local and no shell env: say what to run, do not guess and fail at connect.

    Guessing is what produced `password authentication failed` for D-36. The fallbacks
    that used to live here mirrored the compose literals; with those gone there is no
    correct value to guess.
    """
    _clean(monkeypatch, {})

    with pytest.raises(RuntimeError) as exc:
        _host_env.configure_host_test_env()

    message = str(exc.value)
    assert "make env-local" in message, "the error must name the command that fixes it"
    assert "POSTGRES_PASSWORD" in message, "the error must name what is missing"


def test_non_db_settings_still_come_from_env_local(env_local):
    """Guards the over-correction: env.local is the source for these too."""
    _host_env.configure_host_test_env()

    assert os.environ["TICKETING_SECRET_KEY"] == "from-env-local"


def test_host_port_is_the_published_one_not_env_locals(env_local):
    """env.local's POSTGRES_PORT is the in-network 5432. The host needs the published 5433.

    This is the one value the bootstrap must NOT propagate, and the reason it is a
    separate branch rather than another key in the loop.
    """
    _host_env.configure_host_test_env()

    assert os.environ["POSTGRES_PORT"] == "5433"


def test_published_port_override_is_honoured(monkeypatch):
    """A non-default POSTGRES_HOST_PORT in env.local moves host pytest with it."""
    _clean(monkeypatch, {**ENV_LOCAL, "POSTGRES_HOST_PORT": "15433"})

    _host_env.configure_host_test_env()

    assert os.environ["POSTGRES_PORT"] == "15433"


def test_explicit_shell_override_still_wins(env_local):
    """`POSTGRES_DB=scratch pytest ...` must keep working — it is how scratch DBs are used.

    It is also why CI is untouched by any of this: it sets POSTGRES_* in the job env.
    """
    env_local.setenv("POSTGRES_DB", "app_db_scratch")
    env_local.setenv("POSTGRES_PORT", "6543")

    _host_env.configure_host_test_env()

    assert os.environ["POSTGRES_DB"] == "app_db_scratch"
    assert os.environ["POSTGRES_PORT"] == "6543"
    # …and the un-overridden ones still come from env.local.
    assert os.environ["POSTGRES_USER"] == ENV_LOCAL["POSTGRES_USER"]
