# SPDX-License-Identifier: Apache-2.0

"""
Centralized per-ticket authorization (HR-02).

Single source of truth for "may this authenticated officer access this ticket?".
This reproduces **exactly** the decision set previously inlined in ``get_ticket``
(``ticketing/api/routers/tickets.py``) — it is a refactor of *where* the check
runs, not a policy change:

    1. ticket exists + not soft-deleted          → 404
    2. SEAH visibility gate                       → 403  (is_seah and not can_see_seah)
    3. admin / assignee / viewer / pending-task /
       jurisdiction-scope visibility              → 403  (otherwise)

Per-action authorization (who may assign / resolve / reply / trigger findings /
add-to-informed) and ``is_archived`` checks stay **inline** in the endpoints — this
module only answers "can the user see the ticket at all". PII masking (TP-15) and the
reveal flow's own policy are likewise untouched.

File endpoints resolve their ``file_id`` to an owning ticket first (officer uploads in
``ticketing.ticket_files`` and chatbot uploads in ``public.file_attachments`` via the
ticket's ``grievance_id``) and then run the same visibility gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ticketing.api.dependencies import CurrentUser, get_authenticated_user, get_db
from ticketing.models.officer_scope import OfficerScope
from ticketing.models.ticket import Ticket
from ticketing.models.ticket_file import TicketFile
from ticketing.models.ticket_task import TicketTask
from ticketing.models.ticket_viewer import TicketViewer
from ticketing.services.officer_jurisdiction import ticket_matches_scope


# ── Core visibility gate (mirrors get_ticket ~740-777) ───────────────────────

def _is_viewer(db: Session, ticket_id: str, user_id: str) -> bool:
    return db.execute(
        select(TicketViewer).where(
            TicketViewer.ticket_id == ticket_id,
            TicketViewer.user_id == user_id,
        )
    ).scalar_one_or_none() is not None


def _has_pending_task(db: Session, ticket_id: str, user_id: str) -> bool:
    return db.execute(
        select(TicketTask).where(
            TicketTask.ticket_id == ticket_id,
            TicketTask.assigned_to_user_id == user_id,
            TicketTask.status == "PENDING",
        ).limit(1)
    ).scalar_one_or_none() is not None


def assert_ticket_visibility(db: Session, ticket: Ticket, current_user: CurrentUser) -> None:
    """Raise 403 unless ``current_user`` may access this (already-loaded) ``ticket``.

    Exact reproduction of the SEAH + admin/assignee/viewer/pending-task/scope gate in
    ``get_ticket`` — including its use of direct ``assigned_to_user_id == user_id``
    equality (not ``matches_assignee``) so behaviour is identical.
    """
    # SEAH visibility gate
    if ticket.is_seah and not current_user.can_see_seah:
        raise HTTPException(status_code=403, detail="Access denied")

    # Admins (super_admin / scoped country/project / legacy local_admin) and observers
    # see all; assignee and viewers always see their ticket; task-holders get implicit
    # read access; everyone else must match a jurisdiction scope row.
    if current_user.is_admin:
        return
    if ticket.assigned_to_user_id == current_user.user_id:
        return
    if _is_viewer(db, ticket.ticket_id, current_user.user_id):
        return
    if _has_pending_task(db, ticket.ticket_id, current_user.user_id):
        return

    scopes = db.execute(
        select(OfficerScope).where(OfficerScope.user_id == current_user.user_id)
    ).scalars().all()
    if any(ticket_matches_scope(db, s, ticket) for s in scopes):
        return

    raise HTTPException(status_code=403, detail="Access denied")


def load_ticket_or_404(db: Session, ticket_id: str) -> Ticket:
    ticket = db.execute(
        select(Ticket).where(Ticket.ticket_id == ticket_id, Ticket.is_deleted.is_(False))
    ).scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


# ── FastAPI dependencies ─────────────────────────────────────────────────────

def require_ticket_access(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> Ticket:
    """Load ``ticket_id`` (404), enforce visibility (403), return the ``Ticket``.

    FastAPI caches ``get_db`` / ``get_authenticated_user`` per request, so the
    returned instance shares the endpoint's session and the endpoint may mutate it.
    """
    ticket = load_ticket_or_404(db, ticket_id)
    assert_ticket_visibility(db, ticket, current_user)
    return ticket


@dataclass
class FileAccess:
    """Resolved, access-checked file plus its owning ticket."""
    ticket: Ticket
    file_id: str
    file_name: str
    file_path: str
    file_type: Optional[str]
    source: str  # "officer" (ticketing.ticket_files) | "chatbot" (public.file_attachments)
    grievance_id: Optional[str] = None


def require_file_access(
    file_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> FileAccess:
    """Resolve ``file_id`` → owning ticket → visibility gate, for either file source.

    Officer uploads (``ticketing.ticket_files``) are tried first; then chatbot uploads
    (``public.file_attachments``) mapped to a visible ticket via ``grievance_id``. A file
    with no visible owning ticket is treated as not found (404) — a caller may not learn
    a file exists on a ticket they cannot see.
    """
    # 1. Officer upload — ticketing.ticket_files (owns ticket_id directly)
    tf = db.get(TicketFile, file_id)
    if tf is not None:
        ticket = load_ticket_or_404(db, tf.ticket_id)
        assert_ticket_visibility(db, ticket, current_user)
        return FileAccess(
            ticket=ticket,
            file_id=tf.file_id,
            file_name=tf.file_name,
            file_path=tf.file_path,
            file_type=tf.file_type,
            source="officer",
            grievance_id=ticket.grievance_id,
        )

    # 2. Chatbot upload — public.file_attachments, mapped to a ticket via grievance_id.
    #    Wrapped defensively: public.file_attachments may be absent in ticketing-only
    #    dev DBs, and a non-uuid file_id would otherwise abort the transaction.
    row = None
    try:
        row = db.execute(
            text(
                "SELECT file_name, file_path, file_type, grievance_id "
                "FROM public.file_attachments WHERE file_id = :fid"
            ),
            {"fid": file_id},
        ).mappings().one_or_none()
    except Exception:
        db.rollback()
        row = None

    if row is not None:
        ticket = db.execute(
            select(Ticket).where(
                Ticket.grievance_id == row["grievance_id"],
                Ticket.is_deleted.is_(False),
            )
        ).scalar_one_or_none()
        if ticket is None:
            raise HTTPException(status_code=404, detail="File not found")
        assert_ticket_visibility(db, ticket, current_user)
        return FileAccess(
            ticket=ticket,
            file_id=file_id,
            file_name=row["file_name"],
            file_path=row["file_path"],
            file_type=row["file_type"],
            source="chatbot",
            grievance_id=row["grievance_id"],
        )

    raise HTTPException(status_code=404, detail="File not found")
