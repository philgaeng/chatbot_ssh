"""Unit + integration tests for grievance_sync (Option A backfill + H2-04 watermark/paging).

The policy tests at the top are pure host units. The `sync_env`-based tests below drive the
real `run_grievance_sync` core against the live DB. They are written to be **beat-immune** —
the compose stack runs the real `sync_grievances` beat every 2 minutes against the same DB:
  * the watermark is monkeypatched to a per-test in-process holder, so the beat's global
    watermark and these runs never touch each other;
  * seeded grievances use a *real-now* creation date (inside the backfill grace window) so a
    concurrent beat only ever defers them (never backfills our rows), while our runs force the
    backfill by injecting `now = t0 + 1h`;
  * assertions key on our own unique grievance_ids and on `fetched` (the incremental window,
    which the beat cannot perturb), never on globally-shared counts.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

import ticketing.tasks.grievance_sync as gsync
from ticketing.api.dependencies import CurrentUser, get_authenticated_user
from ticketing.api.main import app
from ticketing.models.base import SessionLocal
from ticketing.models.ticket import Ticket
from ticketing.services.grievance_sync_policy import (
    grievance_age_seconds,
    should_attempt_backfill,
)
from ticketing.services.ticket_intake import build_backfill_payload_from_grievance_row
from ticketing.tasks.grievance_sync import run_grievance_sync


# ── Pure policy units (no DB) ────────────────────────────────────────────────


def test_grievance_age_seconds_with_timezone_naive():
    created = datetime(2026, 6, 10, 12, 0, 0)
    now = datetime(2026, 6, 10, 12, 3, 0, tzinfo=timezone.utc)
    assert grievance_age_seconds(created, now=now) == 180.0


def test_should_attempt_backfill_false_within_grace():
    created = datetime.now(timezone.utc) - timedelta(seconds=30)
    g = {"grievance_id": "G-1", "grievance_creation_date": created}
    assert should_attempt_backfill(g, grace_seconds=180) is False


def test_should_attempt_backfill_true_after_grace():
    created = datetime.now(timezone.utc) - timedelta(seconds=300)
    g = {"grievance_id": "G-1", "grievance_creation_date": created}
    assert should_attempt_backfill(g, grace_seconds=180) is True


def test_build_backfill_payload_uses_complainant_location():
    g = {
        "grievance_id": "B-GR-TEST-1",
        "complainant_id": "B-CM-1",
        "grievance_sensitive_issue": False,
        "grievance_high_priority": False,
        "grievance_summary": "Dust on road",
        "grievance_categories": '["Road Hazard - Dust"]',
        "grievance_location": "Morang",
        "location_code": "P1_MOR",
    }
    payload = build_backfill_payload_from_grievance_row(g)
    assert payload.grievance_id == "B-GR-TEST-1"
    assert payload.location_code == "P1_MOR"
    assert payload.organization_id == "DOR"
    assert payload.package_id is None


def test_build_backfill_payload_strips_not_provided_location():
    g = {
        "grievance_id": "B-GR-TEST-2",
        "grievance_sensitive_issue": False,
        "grievance_high_priority": False,
        "location_code": "Not provided",
    }
    payload = build_backfill_payload_from_grievance_row(g)
    assert payload.location_code is None


# ── H2-04 watermark / paging integration (live DB) ───────────────────────────

pytest_integration = pytest.mark.integration


def _insert_grievance(
    db,
    gid,
    *,
    created,
    modified,
    summary="Dust on the road makes the children sick",
    categories='["Road Hazard - Dust"]',
    location="Morang",
    sensitive=False,
    high=False,
    source="bot",
):
    db.execute(
        text(
            """
            INSERT INTO public.grievances
                (grievance_id, grievance_summary, grievance_categories, grievance_location,
                 grievance_high_priority, grievance_sensitive_issue, grievance_creation_date,
                 grievance_modification_date, source, is_temporary)
            VALUES (:gid, :summary, :categories, :location, :high, :sensitive,
                    :created, :modified, :source, FALSE)
            """
        ),
        {
            "gid": gid,
            "summary": summary,
            "categories": categories,
            "location": location,
            "high": high,
            "sensitive": sensitive,
            "created": created,
            "modified": modified,
            "source": source,
        },
    )


def _bump_grievance(db, gid, *, summary, modified):
    db.execute(
        text(
            "UPDATE public.grievances "
            "SET grievance_summary = :s, grievance_modification_date = :m "
            "WHERE grievance_id = :gid"
        ),
        {"s": summary, "m": modified, "gid": gid},
    )


def _ticket_for(db, gid):
    return db.execute(
        select(Ticket).where(Ticket.grievance_id == gid, Ticket.is_deleted.is_(False))
    ).scalar_one_or_none()


def _count_tickets(db, gid):
    return db.execute(
        text("SELECT count(*) FROM ticketing.tickets WHERE grievance_id = :gid"),
        {"gid": gid},
    ).scalar_one()


@pytest.fixture
def sync_env(db, monkeypatch):
    """Isolated in-process watermark + gid tracking + guaranteed cleanup (see module docstring)."""
    gids: list[str] = []
    # Keyset watermark holder, isolated from the global one the beat uses.
    holder = {"pos": (gsync._EPOCH, "")}

    def _load(_db):
        return holder["pos"]

    def _save(_db, watermark, watermark_gid):
        holder["pos"] = (watermark, watermark_gid)

    monkeypatch.setattr(gsync, "_load_watermark", _load)
    monkeypatch.setattr(gsync, "_save_watermark", _save)

    def _new_gid(tag="g"):
        gid = f"H204-{tag}-{uuid.uuid4().hex[:10]}"
        gids.append(gid)
        return gid

    def _set_base(t):
        holder["pos"] = (t, "")

    def _sweep():
        # Clear any aborted txn first, then remove every row this session created — tracked
        # gids (incl. ctx-created ``test-grv-*``) plus any stray ``H204-*`` from a prior run
        # whose teardown was itself interrupted mid-transaction. Ticket children cascade.
        db.rollback()
        for gid in list(gids):
            db.execute(text("DELETE FROM ticketing.tickets WHERE grievance_id = :g"), {"g": gid})
            db.execute(text("DELETE FROM public.grievances WHERE grievance_id = :g"), {"g": gid})
        db.execute(text("DELETE FROM ticketing.tickets WHERE grievance_id LIKE 'H204-%'"))
        db.execute(text("DELETE FROM public.grievances WHERE grievance_id LIKE 'H204-%'"))
        db.commit()

    _sweep()
    try:
        yield SimpleNamespace(
            db=db, holder=holder, new_gid=_new_gid, gids=gids, set_base=_set_base
        )
    finally:
        _sweep()


@pytest_integration
def test_run1_backfills_and_run2_processes_zero_rows(sync_env):
    db = sync_env.db
    t0 = datetime.now(timezone.utc)
    sync_env.set_base(t0 - timedelta(minutes=5))
    gid = sync_env.new_gid("noop")
    _insert_grievance(db, gid, created=t0, modified=t0)
    db.commit()

    # Force backfill (now well past grace) even though the row is "fresh" to a concurrent beat.
    r1 = run_grievance_sync(db, now=t0 + timedelta(hours=1))
    assert r1["fetched"] >= 1
    assert _ticket_for(db, gid) is not None, "backfill should create a ticket"
    assert sync_env.holder["pos"][0] >= t0  # watermark advanced past the row

    # Nothing changed → strict keyset resume fetches zero rows.
    r2 = run_grievance_sync(db, now=t0 + timedelta(hours=1))
    assert r2["fetched"] == 0
    assert r2["created"] == 0
    assert r2["updated"] == 0
    assert r2["pages"] == 0


@pytest_integration
def test_single_modification_is_the_only_row_processed(sync_env):
    db = sync_env.db
    t0 = datetime.now(timezone.utc)
    sync_env.set_base(t0 - timedelta(minutes=5))
    gid = sync_env.new_gid("mod")
    _insert_grievance(db, gid, created=t0, modified=t0, summary="ORIGINAL summary")
    db.commit()

    run_grievance_sync(db, now=t0 + timedelta(hours=1))  # backfill + settle watermark
    ticket = _ticket_for(db, gid)
    assert ticket is not None

    # Modify exactly one grievance; bump its modification date past the watermark.
    _bump_grievance(db, gid, summary="UPDATED summary text", modified=t0 + timedelta(minutes=2))
    db.commit()

    r = run_grievance_sync(db, now=t0 + timedelta(hours=1))
    assert r["fetched"] == 1, "exactly the one modified grievance enters the window"

    db.expire_all()
    refreshed = _ticket_for(db, gid)
    assert refreshed.grievance_summary == "UPDATED summary text"


@pytest_integration
def test_batch_paging_processes_all_rows_across_pages(sync_env, monkeypatch):
    db = sync_env.db
    monkeypatch.setenv("TICKETING_SYNC_BATCH_SIZE", "2")
    t0 = datetime.now(timezone.utc)
    sync_env.set_base(t0 - timedelta(minutes=5))

    n = 5
    my_gids = []
    for i in range(n):
        gid = sync_env.new_gid(f"page{i}")
        my_gids.append(gid)
        _insert_grievance(db, gid, created=t0, modified=t0 + timedelta(seconds=i))
    db.commit()

    r = run_grievance_sync(db, now=t0 + timedelta(hours=1))

    assert r["fetched"] >= n
    assert r["pages"] >= 3, "5 rows at batch=2 must span multiple pages"
    for gid in my_gids:
        assert _ticket_for(db, gid) is not None
    # Watermark parked at the last row's keyset position → our rows are not re-processed.
    r2 = run_grievance_sync(db, now=t0 + timedelta(hours=1))
    assert r2["created"] == 0
    for gid in my_gids:
        assert _count_tickets(db, gid) == 1


@pytest_integration
def test_crash_mid_run_leaves_watermark_and_reconverges_without_duplicates(sync_env, monkeypatch):
    db = sync_env.db
    t0 = datetime.now(timezone.utc)
    base = t0 - timedelta(minutes=5)
    sync_env.set_base(base)
    gid = sync_env.new_gid("crash")
    _insert_grievance(db, gid, created=t0, modified=t0)
    db.commit()

    # Simulate a crash *after* the page's ticket data commits but *before* the watermark
    # advances (the crash-safe ordering window).
    def _boom(*_a, **_k):
        raise RuntimeError("simulated crash before watermark advance")

    monkeypatch.setattr(gsync, "_save_watermark", _boom)

    with pytest.raises(RuntimeError):
        run_grievance_sync(db, now=t0 + timedelta(hours=1))

    # Watermark NOT advanced (still the base).
    assert sync_env.holder["pos"] == (base, "")
    # The backfilled ticket *was* committed before the crash.
    assert _count_tickets(db, gid) == 1

    # Re-run (watermark restored) converges: HR-03 dedup skips the existing ticket, no dup.
    monkeypatch.undo()  # restore the real _save_watermark... then re-isolate
    holder = sync_env.holder
    monkeypatch.setattr(gsync, "_load_watermark", lambda _db: holder["pos"])
    monkeypatch.setattr(gsync, "_save_watermark",
                        lambda _db, w, g: holder.__setitem__("pos", (w, g)))

    r = run_grievance_sync(db, now=t0 + timedelta(hours=1))
    assert r["fetched"] >= 1
    assert r["created"] == 0, "re-run must not create a second ticket"
    assert _count_tickets(db, gid) == 1


@pytest_integration
def test_full_sweep_processes_rows_below_the_watermark(sync_env):
    db = sync_env.db
    t0 = datetime.now(timezone.utc)
    gid = sync_env.new_gid("full")
    # Row modified in the past, then park the watermark AHEAD of it: incremental skips it.
    _insert_grievance(db, gid, created=t0, modified=t0 - timedelta(hours=2))
    db.commit()
    sync_env.set_base(t0)  # watermark ahead of the row

    run_grievance_sync(db, now=t0 + timedelta(hours=1))
    assert _ticket_for(db, gid) is None, "incremental run must skip a row below the watermark"

    full = run_grievance_sync(db, full=True, now=t0 + timedelta(hours=1))
    assert full["full"] is True
    assert full["fetched"] >= 1
    assert _ticket_for(db, gid) is not None, "full sweep must process rows below the watermark"


@pytest_integration
def test_get_ticket_detail_performs_no_cache_writeback(sync_env, ctx):
    """H2-04: GET /tickets/{id} live-merges grievance fields but must not persist them."""
    db = sync_env.db
    officer = "zero-writes-officer@grm.local"
    ticket = ctx.add_open_ticket(officer)
    gid = ticket.grievance_id
    sync_env.gids.append(gid)  # ensure grievance row cleanup
    ticket.grievance_summary = "STALE cache summary"
    db.flush()

    # Grievance row carries a *different* (fresher) summary than the ticket cache.
    _insert_grievance(
        db, gid, created=datetime.now(timezone.utc), modified=datetime.now(timezone.utc),
        summary="FRESH grievance summary",
    )
    db.commit()
    before_updated_at = ticket.updated_at

    def _override_user():
        return CurrentUser(user_id=officer, role_keys=["site_safeguards_focal_person"])

    app.dependency_overrides[get_authenticated_user] = _override_user
    try:
        client = TestClient(app)
        resp = client.get(f"/api/v1/tickets/{ticket.ticket_id}")
    finally:
        app.dependency_overrides.pop(get_authenticated_user, None)

    assert resp.status_code == 200, resp.text
    # Response reflects the live-merged fresh grievance summary...
    assert resp.json()["grievance_summary"] == "FRESH grievance summary"

    # ...but the ticket cache in the DB is UNCHANGED (no write-back, no updated_at bump).
    check = SessionLocal()
    try:
        row = check.execute(
            select(Ticket).where(Ticket.ticket_id == ticket.ticket_id)
        ).scalar_one()
        assert row.grievance_summary == "STALE cache summary"
        assert row.updated_at == before_updated_at
    finally:
        check.close()
