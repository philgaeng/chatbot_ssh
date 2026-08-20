"""
Shared by the two `live_llm` suites, which live in different (non-package) test directories.

⚠ It lives here rather than in `tests/backend/` because `tests/` is the only one of the three that
is an importable package — `tests/backend/` and `tests/ticketing/` have no `__init__.py`, which is
also why two files called `test_llm_live.py` cannot coexist across them (pytest reports an import
file mismatch). One helper, one place, no basename collision.
"""
from __future__ import annotations

import pytest


def live_call(call):
    """
    Run a live call, turning an **account-level** refusal into a skip and nothing else into one.

    ⚠ **Why a skip and not a failure.** A 402 or a 429 says the account is out of quota this minute.
    It is not a defect in this repository, and a job that reddens on it teaches everyone to ignore
    the job — which is the D-26 lesson (*a permanently red build is indistinguishable from one nobody
    watches*) arriving through the door Q-17 deliberately left open.

    ⚠ **And why this is not a quarantine.** A model refusal, a malformed reply, a wrong endpoint and
    a broken schema all still **fail** — only the account's own quota skips. The CI step additionally
    fails when *nothing passed*, so a run that skipped everything cannot be read as evidence. Skipping
    quietly and reporting green is exactly the failure mode that pair of controls exists to prevent.

    The marker list is imported from the probe rather than restated, so there is one definition of
    "the account said no" and it cannot drift.
    """
    from scripts.ops.llm_smoke import _BLOCKED_MARKERS

    try:
        return call()
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if any(marker in message.lower() for marker in _BLOCKED_MARKERS):
            pytest.skip(
                "the ACCOUNT refused this call, not the model — nothing here was tested. "
                f"Provider said: {message[:200]}"
            )
        raise
