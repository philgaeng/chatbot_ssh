# SPDX-License-Identifier: Apache-2.0
"""
An unreachable Keycloak is asked once per TTL, not once per read (`GRM-107`).

**Measured 2026-09-14 on the e2e stack**, which runs no Keycloak: one failed snapshot fetch cost
~6.4 s (a 3.6 s DNS failure plus python-keycloak's retry), the roster reads the snapshot twice, and a
failure was never remembered — so every `/users/roster` took ~13 s. The Staffing pane reads the roster
once per level and sat on "Loading…" for over a minute. In production that is the shape of a Keycloak
outage: every admin click pays the full timeout again.
"""
from __future__ import annotations

import threading
import time

import pytest

from ticketing.services import keycloak_users as ku


@pytest.fixture(autouse=True)
def clean(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(ku, "keycloak_configured", lambda: True)
    ku._snapshot_cache = None
    ku._snapshot_cached_at = 0.0
    ku._snapshot_failed_at = 0.0
    yield
    ku._snapshot_cache = None
    ku._snapshot_cached_at = 0.0
    ku._snapshot_failed_at = 0.0


def _failing(monkeypatch: pytest.MonkeyPatch, delay: float = 0.0) -> list[int]:
    calls: list[int] = []

    def fetch():
        calls.append(1)
        if delay:
            time.sleep(delay)
        raise ConnectionError("Can't connect to server")

    monkeypatch.setattr(ku, "_fetch_snapshot", fetch)
    return calls


def test_a_failed_fetch_is_not_retried_within_the_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    """⭐ The defect: every read used to pay the full connection timeout again."""
    calls = _failing(monkeypatch)
    for _ in range(5):
        assert ku._get_snapshot() is None
    assert len(calls) == 1


def test_it_tries_again_once_the_ttl_has_passed(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _failing(monkeypatch)
    now = [1000.0]
    monkeypatch.setattr(ku.time, "monotonic", lambda: now[0])
    ku._get_snapshot()
    now[0] += ku._SNAPSHOT_TTL_SECONDS + 1
    ku._get_snapshot()
    assert len(calls) == 2


def test_concurrent_reads_share_one_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Eight levels of the Staffing pane ask at once; one of them should pay, not all eight."""
    calls = _failing(monkeypatch, delay=0.2)
    threads = [threading.Thread(target=ku._get_snapshot) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(calls) == 1


def test_a_stale_snapshot_is_still_served_while_backing_off(monkeypatch: pytest.MonkeyPatch) -> None:
    good = ku._KcSnapshot()
    ku._snapshot_cache = good
    ku._snapshot_cached_at = time.monotonic() - ku._SNAPSHOT_TTL_SECONDS - 1  # expired
    calls = _failing(monkeypatch)
    assert ku._get_snapshot() is good
    assert ku._get_snapshot() is good
    assert len(calls) == 1


def test_a_success_ends_the_back_off(monkeypatch: pytest.MonkeyPatch) -> None:
    ku._snapshot_failed_at = time.monotonic() - ku._SNAPSHOT_TTL_SECONDS - 1
    snap = ku._KcSnapshot()
    monkeypatch.setattr(ku, "_fetch_snapshot", lambda: snap)
    assert ku._get_snapshot() is snap
    assert ku._snapshot_failed_at == 0.0


@pytest.mark.parametrize("how", ["force", "invalidate"])
def test_force_and_invalidate_both_skip_the_back_off(monkeypatch: pytest.MonkeyPatch, how: str) -> None:
    """A mutation that went through Keycloak is evidence it is back; do not keep serving nothing."""
    calls = _failing(monkeypatch)
    ku._get_snapshot()
    if how == "force":
        ku._get_snapshot(force=True)
    else:
        ku.invalidate_officer_profiles_cache()
        ku._get_snapshot()
    assert len(calls) == 2
