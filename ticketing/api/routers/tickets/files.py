# SPDX-License-Identifier: Apache-2.0

"""File attachment endpoints (complainant chatbot files + officer uploads).

  GET  /tickets/{ticket_id}/files
  GET  /files/{file_id}
  POST /tickets/{ticket_id}/attachments
  GET  /tickets/{ticket_id}/attachments
  GET  /attachments/{file_id}
"""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ticketing.api.dependencies import CurrentUser, get_authenticated_user, get_db
from ticketing.api.ticket_access import FileAccess, require_file_access, require_ticket_access
from ticketing.engine.events import _add_event
from ticketing.models.ticket import Ticket
from ticketing.models.ticket_file import TicketFile

from ._shared import _actor_role, _new_id

logger = logging.getLogger(__name__)
router = APIRouter()


def _resolve_attachment_path(stored_path: str | None) -> str | None:
    """Resolve DB file_path to a readable path on disk."""
    if not stored_path:
        return None
    if os.path.isabs(stored_path) and os.path.isfile(stored_path):
        return stored_path
    upload_root = os.getenv("UPLOAD_FOLDER", "uploads")
    for candidate in (stored_path, os.path.join(upload_root, stored_path)):
        if os.path.isfile(candidate):
            return candidate
    return None


def _media_type_for_path(file_path: str) -> str:
    lower = file_path.lower()
    if lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".pdf"):
        return "application/pdf"
    if lower.endswith((".m4a", ".mp4")):
        return "audio/mp4"
    if lower.endswith(".mp3"):
        return "audio/mpeg"
    if lower.endswith(".wav"):
        return "audio/wav"
    if lower.endswith(".webm"):
        return "audio/webm"
    if lower.endswith(".aac"):
        return "audio/aac"
    if lower.endswith(".ogg"):
        return "audio/ogg"
    return "application/octet-stream"


@router.get(
    "/tickets/{ticket_id}/files",
    summary="List file attachments uploaded by complainant via chatbot",
)
def list_ticket_files(
    ticket_id: str,
    ticket: Ticket = Depends(require_ticket_access),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> list[dict]:
    """
    Reads public.file_attachments for the grievance linked to this ticket.
    Read-only — no join, separate query per architecture rules.
    """
    if ticket.is_archived and not current_user.can_view_archived:
        raise HTTPException(status_code=403, detail="Case is archived")

    try:
        rows = db.execute(
            text(
                """
                SELECT file_id::text, file_name, file_path, file_type, file_size, upload_timestamp
                FROM public.file_attachments
                WHERE grievance_id = :grievance_id
                ORDER BY upload_timestamp
                """
            ),
            {"grievance_id": ticket.grievance_id},
        ).mappings().all()
        return [dict(r) for r in rows]
    except Exception as exc:
        # public.file_attachments may not exist in dev/test environments that
        # only run the ticketing stack without the full chatbot DB.  Return an
        # empty list so the UI degrades gracefully instead of crashing.
        logger.warning("list_ticket_files: public.file_attachments unavailable — %s", exc)
        db.rollback()  # clear the aborted transaction so the session stays usable
        return []


@router.get(
    "/files/{file_id}",
    summary="Download a file attachment by file_id",
)
def download_file(
    file_id: str,
    fa: FileAccess = Depends(require_file_access),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> FileResponse:
    """
    Streams a file from disk using the path stored in public.file_attachments.

    HR-02: ``require_file_access`` resolves file → owning ticket and enforces the same
    SEAH + jurisdiction/visibility gate as the ticket detail view *before* streaming.
    Previously this endpoint only checked ``is_archived`` — any authenticated officer
    could pull any grievance's chatbot files, piercing the SEAH wall.
    """
    if fa.ticket.is_archived and not current_user.can_view_archived:
        raise HTTPException(status_code=403, detail="Case is archived")

    file_path = _resolve_attachment_path(fa.file_path)
    if not file_path:
        raise HTTPException(status_code=404, detail="File not on disk")

    media_type = _media_type_for_path(file_path)
    return FileResponse(path=file_path, filename=fa.file_name, media_type=media_type)


@router.post(
    "/tickets/{ticket_id}/attachments",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file attachment as an officer (with optional caption)",
)
async def upload_officer_attachment(
    ticket_id: str,
    file: UploadFile = File(...),
    caption: str = Form(""),
    ticket: Ticket = Depends(require_ticket_access),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> dict:
    if ticket.is_archived:
        raise HTTPException(status_code=409, detail="Cannot upload files to an archived case")

    # Save file to uploads/ticketing/{ticket_id}/
    upload_dir = Path("uploads") / "ticketing" / ticket_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_id = _new_id()
    original_name = file.filename or "upload"
    suffix = Path(original_name).suffix or ""
    dest = upload_dir / f"{file_id}{suffix}"

    with dest.open("wb") as buf:
        shutil.copyfileobj(file.file, buf)

    file_size = dest.stat().st_size
    # Derive a simple file_type category from MIME or extension
    mime = file.content_type or ""
    if mime.startswith("image/"):
        file_type = "image"
    elif mime.startswith("audio/") or suffix.lower() in (".m4a", ".mp3", ".wav", ".aac", ".webm", ".ogg"):
        file_type = "audio"
    elif mime == "application/pdf" or suffix.lower() == ".pdf":
        file_type = "pdf"
    else:
        file_type = "document"

    tf = TicketFile(
        file_id=file_id,
        ticket_id=ticket_id,
        file_name=original_name,
        file_path=str(dest),
        file_type=file_type,
        file_size=file_size,
        caption=caption.strip() or None,
        uploaded_by_user_id=current_user.user_id,
    )
    db.add(tf)

    # Add an internal note event so the upload appears in the case timeline
    note_text = f"📎 Attached: {original_name}"
    if caption.strip():
        note_text += f" — {caption.strip()}"
    _add_event(
        db, ticket, "NOTE_ADDED",
        step_id=ticket.current_step_id,
        note=note_text,
        payload={"file_id": file_id, "internal": True},
        created_by=current_user.user_id,
        seen=True,
        actor_role=_actor_role(current_user),
        summary_regen_required=True,
    )

    db.commit()
    db.refresh(tf)

    return {
        "file_id": tf.file_id,
        "ticket_id": tf.ticket_id,
        "file_name": tf.file_name,
        "file_type": tf.file_type,
        "file_size": tf.file_size,
        "caption": tf.caption,
        "uploaded_by_user_id": tf.uploaded_by_user_id,
        "uploaded_at": tf.uploaded_at,
    }


@router.get(
    "/tickets/{ticket_id}/attachments",
    summary="List officer-uploaded attachments for a ticket",
)
def list_officer_attachments(
    ticket_id: str,
    ticket: Ticket = Depends(require_ticket_access),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_authenticated_user),
) -> list[dict]:
    files = db.execute(
        select(TicketFile)
        .where(TicketFile.ticket_id == ticket_id)
        .order_by(TicketFile.uploaded_at)
    ).scalars().all()

    return [
        {
            "file_id": f.file_id,
            "file_name": f.file_name,
            "file_type": f.file_type,
            "file_size": f.file_size,
            "caption": f.caption,
            "uploaded_by_user_id": f.uploaded_by_user_id,
            "uploaded_at": f.uploaded_at,
        }
        for f in files
    ]


@router.get(
    "/attachments/{file_id}",
    summary="Download an officer-uploaded attachment",
)
def download_officer_attachment(
    file_id: str,
    fa: FileAccess = Depends(require_file_access),
) -> FileResponse:
    # HR-02: was auth-only — ANY authenticated user could download ANY officer
    # attachment by file_id (no SEAH gate, no scope/viewer check). require_file_access
    # now resolves file → owning ticket and enforces the full visibility gate.
    if not os.path.isfile(fa.file_path):
        raise HTTPException(status_code=404, detail="File not on disk")

    media_type = _media_type_for_path(fa.file_path)
    return FileResponse(path=fa.file_path, filename=fa.file_name, media_type=media_type)
