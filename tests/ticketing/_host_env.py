"""
Host-side pytest bootstrap — run before any ``ticketing.*`` import.

Docker ``db`` is not on host :5432 by default; ``docker-compose.grm.yml`` publishes
``${POSTGRES_HOST_PORT:-5433}:5432``. Host pytest must use that **port** with the
credentials the containers use, not whatever else is on :5432.

``env.local`` is that single source. Every compose service interpolates
``POSTGRES_USER`` / ``POSTGRES_PASSWORD`` / ``POSTGRES_DB`` from it with ``${VAR:?}``,
so reading it here is what makes host pytest and the containers agree by construction
rather than by two lists being kept in step by hand.

⚠ The **port** is the one value that must NOT come from ``env.local``'s ``POSTGRES_PORT``:
that is the in-network port (5432) every container reaches ``db`` on. The host reaches the
same database through the published mapping, ``POSTGRES_HOST_PORT`` (5433).

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

    # The DB identity comes from env.local, because that is now the same source the
    # containers read: every compose service interpolates POSTGRES_USER/PASSWORD/DB from
    # it with `${VAR:?}`. Host pytest and the stack therefore cannot disagree.
    #
    # ⚠ This used to be the opposite, for a reason that was correct at the time and is
    # not any more. Eleven compose services hardcoded POSTGRES_DB/USER/PASSWORD in their
    # own `environment:` blocks, which override `env_file:`, so env.local's POSTGRES_*
    # were dead config that no container read. Honouring them here was then the one way
    # host pytest could disagree with the database it was talking to — and it did
    # (D-36, 2026-07-15): a drifted env.local failed the whole host suite with
    # `password authentication failed`, which reads as a code regression rather than
    # config. The literals were removed and env.local became live, so the fence now
    # points the wrong way: hardcoding `password` here would reproduce D-36 exactly,
    # against a rotated database.
    #
    # An explicit shell override still wins (`key not in os.environ`), so
    # `POSTGRES_DB=scratch pytest ...` keeps working, and CI — which sets POSTGRES_*
    # in the job env — is untouched by any of this.
    for key in (
        "TICKETING_SECRET_KEY",
        "KEYCLOAK_ISSUER",
        "APP_ENV",
        "AUTH_MODE",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
    ):
        if key in env_local and key not in os.environ:
            os.environ[key] = env_local[key]

    os.environ.setdefault("POSTGRES_HOST", "localhost")
    if "POSTGRES_PORT" not in os.environ:
        # Published by docker-compose.grm.yml db.ports (not env.local's POSTGRES_PORT,
        # which is the in-network 5432 that only containers can reach).
        os.environ["POSTGRES_PORT"] = env_local.get(
            "POSTGRES_HOST_PORT",
            os.environ.get("POSTGRES_HOST_PORT", "5433"),
        )

    # No fallback credentials, deliberately. The previous defaults mirrored the compose
    # literals; now that those are gone there is no correct value to guess, and guessing
    # would resurrect the failure this bootstrap exists to prevent. Say what to run.
    missing = [k for k in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB") if not os.environ.get(k)]
    if missing:
        raise RuntimeError(
            "host pytest cannot resolve the database identity: "
            + ", ".join(missing)
            + " is unset and env.local does not supply it. Run `make env-local` to "
            "regenerate env.local from .env.shared + secrets.enc.env, or set the "
            "variables in your shell. (Inside a container this bootstrap does not run.)"
        )
    # Dev bypass for API tests that import the FastAPI app (APP_ENV=dev AUTH_MODE=bypass).
    os.environ.setdefault("APP_ENV", "dev")
    os.environ.setdefault("AUTH_MODE", "bypass")
    os.environ.setdefault("KEYCLOAK_ISSUER", "")

    try:
        from ticketing.config.settings import get_settings

        get_settings.cache_clear()
    except ImportError:
        pass
