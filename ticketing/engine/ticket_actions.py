# SPDX-License-Identifier: Apache-2.0

"""Officer-action engine (H2-02 Pass 3).

Pure business logic for the officer actions that used to be inlined in the
``perform_action`` router (``api/routers/tickets/…``). Each ``ACTION_HANDLERS``
entry is ``(db, ticket, actor, payload) -> ActionOutcome``:

  * it mutates the ticket + writes events (via the canonical ``_add_event``),
  * it raises :class:`ActionError` — never ``HTTPException`` — for a
    client-correctable failure, and
  * it returns the event plus the async side-effects (complainant notice,
    translation, findings/summary regen, assignment/​supervisor notifications)
    that the router fires **after commit**.

The router keeps the thin shell: validate + authz guards → ``dispatch`` →
apply the outcome (reopen-clears-archive, commit, refresh, enqueue, response).

No HTTP imports here — models / services / engine / clients / constants only,
so this stays a leaf with no import cycle back into the routers.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ticketing.clients.grievance_api import update_grievance_status
from ticketing.constants.classification import officer_validation_required
from ticketing.constants.resolution import (
    format_resolution_note,
    resolution_category_label,
    validate_resolution_category,
    validate_resolution_note,
)
from ticketing.engine.escalation import convene_grc, escalate_ticket
from ticketing.engine.events import _add_event
from ticketing.engine.workflow_engine import _find_supervisor_user_id, get_current_step
from ticketing.models.ticket import Ticket, TicketEvent
from ticketing.models.ticket_file import TicketFile
from ticketing.models.ticket_viewer import TicketViewer
from ticketing.models.workflow import WorkflowStep
from ticketing.services.chart_behaviors import user_can_see_seah
from ticketing.services.grievance_content import fetch_grievance_row
from ticketing.services.overdue_episodes import close_open_episode

if TYPE_CHECKING:  # runtime-free — annotations are strings under `from __future__`
    from ticketing.api.dependencies import CurrentUser

logger = logging.getLogger(__name__)


# ─── typed error + result object ──────────────────────────────────────────────

class ActionError(Exception):
    """A client-correctable action failure, HTTP-agnostic.

    The router maps this to ``HTTPException(status_code, detail)``. Every action
    error today is a 422, but ``status_code`` stays explicit so the mapping is
    exact and a future non-422 branch needs no special-casing.
    """

    def __init__(self, detail: str, status_code: int = 422):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass
class ActionOutcome:
    """What an action did, plus the after-commit work the router must fire.

    ``ticket`` is echoed back because ESCALATE re-fetches it under a row lock;
    every other handler returns the same instance it received.
    """

    event: TicketEvent
    ticket: Ticket
    notify_complainant_text: Optional[str] = None
    translate_note_event_id: Optional[str] = None
    translate_resolution_event_id: Optional[str] = None
    generate_findings: bool = False
    generate_resolved_summary: bool = False
    # (new_assigned, old_assigned, event_label) → enqueue_assignment_notifications
    assignment_notify: Optional[tuple[str, Optional[str], str]] = None
    # OC-04 §5.5: the step a manual escalation came OFF, notified after commit.
    supervisor_notify_from_step: Optional[WorkflowStep] = None


# ─── shared helpers (moved verbatim from the router) ──────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _actor_role(actor: "CurrentUser") -> Optional[str]:
    """Snapshot the first role key at write time for audit correlation."""
    return actor.role_keys[0] if getattr(actor, "role_keys", None) else None


def _extract_mentions(text: str) -> list[str]:
    """Return list of @mention targets from note text (e.g. ['piu-l2', 'all'])."""
    # Supports ids with dots/hyphens and email-style ids like admin@grm.local.
    return re.findall(r"(?<![\w@])@([A-Za-z0-9][A-Za-z0-9._-]*(?:@[A-Za-z0-9][A-Za-z0-9._-]*)?)", text)


def _get_viewer_ids(db: Session, ticket_id: str) -> list[str]:
    """Return list of all viewer user_ids for a ticket."""
    viewers = db.execute(
        select(TicketViewer).where(TicketViewer.ticket_id == ticket_id)
    ).scalars().all()
    return [v.user_id for v in viewers]


_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif")


def _ticket_has_image_attachment(db: Session, ticket: Ticket) -> bool:
    """True when ≥1 image exists in complainant or officer attachments (TP-11)."""
    officer_files = db.execute(
        select(TicketFile).where(TicketFile.ticket_id == ticket.ticket_id)
    ).scalars().all()
    for tf in officer_files:
        if (tf.file_type or "").lower() == "image":
            return True
        if tf.file_name and tf.file_name.lower().endswith(_IMAGE_EXTENSIONS):
            return True

    try:
        rows = db.execute(
            text(
                """
                SELECT file_type, file_name
                FROM public.file_attachments
                WHERE grievance_id = :gid
                """
            ),
            {"gid": ticket.grievance_id},
        ).mappings().all()
        for row in rows:
            ft = (row.get("file_type") or "").lower()
            fn = (row.get("file_name") or "").lower()
            if ft == "image" or ft.startswith("image/"):
                return True
            if fn.endswith(_IMAGE_EXTENSIONS):
                return True
    except Exception as exc:
        logger.warning("image gate: file_attachments unavailable — %s", exc)
        db.rollback()
    return False


def _has_resolution_record_event(db: Session, ticket_id: str) -> bool:
    events = db.execute(
        select(TicketEvent)
        .where(
            TicketEvent.ticket_id == ticket_id,
            TicketEvent.event_type == "NOTE_ADDED",
        )
        .order_by(TicketEvent.created_at.desc())
    ).scalars().all()
    for ev in events:
        payload = ev.payload or {}
        if payload.get("is_resolution_record"):
            return True
    return False


def _auto_acknowledge_if_assigned_actor(
    db: Session,
    ticket: Ticket,
    current_user: "CurrentUser",
) -> Optional[TicketEvent]:
    """Assigned actor engaging (note, field report, reply) starts the case without a separate ack."""
    if ticket.status_code not in ("OPEN", "ESCALATED"):
        return None
    if not ticket.assigned_to_user_id:
        return None
    if not current_user.is_admin and not current_user.matches_assignee(
        ticket.assigned_to_user_id
    ):
        return None
    old_status = ticket.status_code
    ticket.status_code = "IN_PROGRESS"
    ticket.step_started_at = _now()
    ticket.updated_by_user_id = current_user.user_id
    return _add_event(
        db,
        ticket,
        "ACKNOWLEDGED",
        old_status=old_status,
        new_status="IN_PROGRESS",
        step_id=ticket.current_step_id,
        created_by=current_user.user_id,
        seen=True,
        actor_role=_actor_role(current_user),
        summary_regen_required=True,
    )


# ─── action handlers — one per action_type ────────────────────────────────────

def acknowledge(db: Session, ticket: Ticket, actor: "CurrentUser", payload) -> ActionOutcome:
    old_status = ticket.status_code
    event_step_id = ticket.current_step_id

    g_row = fetch_grievance_row(db, ticket.grievance_id)
    class_status = (g_row or {}).get("grievance_classification_status")
    if officer_validation_required(class_status):
        raise ActionError(
            "Review and confirm the grievance summary and categories "
            "before acknowledging this ticket."
        )
    close_open_episode(db, ticket, "ACKNOWLEDGED")
    ticket.status_code = "IN_PROGRESS"
    ticket.step_started_at = _now()
    ticket.updated_by_user_id = actor.user_id
    event = _add_event(
        db, ticket, "ACKNOWLEDGED",
        old_status=old_status, new_status="IN_PROGRESS",
        step_id=event_step_id,
        note=payload.note,
        created_by=actor.user_id,
        seen=True,
        actor_role=_actor_role(actor),
        summary_regen_required=True,
    )
    return ActionOutcome(event=event, ticket=ticket)


def escalate(db: Session, ticket: Ticket, actor: "CurrentUser", payload) -> ActionOutcome:
    # HR-04: take a row lock on the ticket before mutating so the SLA watchdog
    # (which selects candidates FOR UPDATE SKIP LOCKED) and any other concurrent
    # writer cannot double-escalate. populate_existing refreshes the in-session
    # instance with the freshly-locked row state. Lock is held until db.commit().
    ticket = db.execute(
        select(Ticket)
        .where(Ticket.ticket_id == ticket.ticket_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()
    if not _ticket_has_image_attachment(db, ticket):
        raise ActionError(
            "At least one image attachment is required before escalating. "
            "Upload a site photo or ask the complainant to send photos via WhatsApp."
        )
    review_notes = (payload.escalation_notes or payload.note or "").strip()
    if not review_notes:
        raise ActionError("escalation_notes is required for ESCALATE")
    old_assigned = ticket.assigned_to_user_id
    supervisor_notify_from_step = get_current_step(ticket, db)  # OC-04 §5.5 (before it moves)
    # Delegate to engine — single code path for manual + auto escalation
    result = escalate_ticket(
        ticket, db,
        triggered_by="MANUAL",
        note=review_notes,
        created_by_user_id=actor.user_id,
        actor_role=_actor_role(actor),
        escalation_date=payload.escalation_date,
        persons_involved=payload.persons_involved or [actor.user_id],
        escalation_notes=review_notes,
    )
    if result is None:
        raise ActionError(
            "No next step available — ticket is already at the final escalation level"
        )

    assignment_notify = None
    if ticket.assigned_to_user_id and ticket.assigned_to_user_id != old_assigned:
        assignment_notify = (ticket.assigned_to_user_id, old_assigned, "escalation")

    return ActionOutcome(
        event=result,
        ticket=ticket,
        assignment_notify=assignment_notify,
        notify_complainant_text=(
            "Your grievance is being reviewed at the next level. "
            "We will continue to keep you updated."
        ),
        supervisor_notify_from_step=supervisor_notify_from_step,
    )


def resolve(db: Session, ticket: Ticket, actor: "CurrentUser", payload) -> ActionOutcome:
    old_status = ticket.status_code
    event_step_id = ticket.current_step_id

    if ticket.status_code not in ("RESOLVED", "CLOSED") and not _ticket_has_image_attachment(db, ticket):
        raise ActionError(
            "At least one image attachment is required before resolving. "
            "Upload a site photo or ask the complainant to send photos via WhatsApp."
        )
    try:
        category = validate_resolution_category(payload.resolution_category)
        officer_text = validate_resolution_note(payload.note)
    except ValueError as exc:
        raise ActionError(str(exc)) from exc

    # Backfill path: allow officers to add missing resolution details
    # on already resolved/closed tickets (needed for closure summary generation).
    if ticket.status_code in ("RESOLVED", "CLOSED"):
        if _has_resolution_record_event(db, ticket.ticket_id):
            raise ActionError("Ticket is already resolved.")
        formatted_note = format_resolution_note(category, officer_text)
        resolution_event = _add_event(
            db,
            ticket,
            "NOTE_ADDED",
            step_id=event_step_id,
            note=formatted_note,
            payload={
                "internal": True,
                "is_resolution_record": True,
                "resolution_category": category,
                "resolution_backfilled": True,
            },
            created_by=actor.user_id,
            seen=True,
            actor_role=_actor_role(actor),
            summary_regen_required=True,
        )
        ticket.updated_by_user_id = actor.user_id
        return ActionOutcome(
            event=resolution_event,
            ticket=ticket,
            translate_resolution_event_id=resolution_event.event_id,
            generate_findings=True,
            generate_resolved_summary=True,
        )

    _auto_acknowledge_if_assigned_actor(db, ticket, actor)
    close_open_episode(db, ticket, "RESOLVED")
    formatted_note = format_resolution_note(category, officer_text)
    resolution_event = _add_event(
        db,
        ticket,
        "NOTE_ADDED",
        step_id=event_step_id,
        note=formatted_note,
        payload={
            "internal": True,
            "is_resolution_record": True,
            "resolution_category": category,
        },
        created_by=actor.user_id,
        seen=True,
        actor_role=_actor_role(actor),
        summary_regen_required=True,
    )

    ticket.status_code = "RESOLVED"
    ticket.updated_by_user_id = actor.user_id
    cat_label = resolution_category_label(category)
    event = _add_event(
        db,
        ticket,
        "RESOLVED",
        old_status=old_status,
        new_status="RESOLVED",
        step_id=event_step_id,
        note=f"Case resolved — {cat_label}",
        payload={
            "resolution_category": category,
            "resolution_event_id": resolution_event.event_id,
        },
        created_by=actor.user_id,
        seen=True,
        actor_role=_actor_role(actor),
        summary_regen_required=True,
    )
    try:
        update_grievance_status(
            ticket.grievance_id,
            "RESOLVED",
            note=officer_text[:500],
        )
    except Exception as exc:
        logger.warning(
            "update_grievance_status failed ticket_id=%s: %s", ticket.ticket_id, exc
        )
    return ActionOutcome(
        event=event,
        ticket=ticket,
        translate_resolution_event_id=resolution_event.event_id,
        notify_complainant_text=(
            "Your grievance has been resolved. "
            "Thank you for bringing this to our attention. "
            "A detailed outcome letter will be sent shortly."
        ),
        generate_findings=True,
        generate_resolved_summary=True,
    )


def note(db: Session, ticket: Ticket, actor: "CurrentUser", payload) -> ActionOutcome:
    if not payload.note:
        raise ActionError("note is required for action_type=NOTE")
    event_step_id = ticket.current_step_id
    _auto_acknowledge_if_assigned_actor(db, ticket, actor)
    note_payload: dict = {"internal": True}
    if payload.is_call_report:
        note_payload["is_call_report"] = True
    # Internal note — no status change, not visible to complainant
    event = _add_event(
        db, ticket, "NOTE_ADDED",
        step_id=event_step_id,
        note=payload.note,
        payload=note_payload,
        created_by=actor.user_id,
        seen=True,
        actor_role=_actor_role(actor),
        summary_regen_required=True,
    )
    # Fire translation task after commit (7a — translate note to English for supervisors)
    translate_note_event_id = event.event_id

    # ── @mention notifications (UI_SPEC.md §2.8) ──────────────────────────
    # Parse @mentions and create lightweight MENTION notification events.
    # These events have seen=False (drive badge) but are NOT rendered in the thread.
    mentions = _extract_mentions(payload.note)
    if mentions:
        viewer_ids = _get_viewer_ids(db, ticket.ticket_id)
        assigned_id = ticket.assigned_to_user_id
        all_participant_ids = list({*viewer_ids, *([assigned_id] if assigned_id else [])})

        notify_set: set[str] = set()
        for mention in mentions:
            if mention.lower() == "all":
                notify_set.update(all_participant_ids)
            elif mention != actor.user_id:
                notify_set.add(mention)

        # R1 SEAH leak-proof: on a SEAH ticket, never plant a MENTION event (which carries
        # the case's existence into the recipient's bell) for a user who can't see SEAH —
        # covers a stray @mention or an @all that reaches a mis-cast non-SEAH participant.
        if ticket.is_seah and notify_set:
            notify_set = {uid for uid in notify_set if user_can_see_seah(db, uid)}

        for target_uid in notify_set:
            _add_event(
                db, ticket, "MENTION",
                step_id=event_step_id,
                note=f"@mentioned by {actor.user_id}",
                payload={"mentioned_by": actor.user_id, "source_event_id": event.event_id},
                seen=False,
                notify_user_id=target_uid,
                created_by=actor.user_id,
                actor_role=_actor_role(actor),
                summary_regen_required=False,
            )
    return ActionOutcome(
        event=event, ticket=ticket, translate_note_event_id=translate_note_event_id
    )


def field_report(db: Session, ticket: Ticket, actor: "CurrentUser", payload) -> ActionOutcome:
    if not payload.note:
        raise ActionError("note is required for action_type=FIELD_REPORT")
    event_step_id = ticket.current_step_id
    _auto_acknowledge_if_assigned_actor(db, ticket, actor)
    # Officer field report — structured finding, no status change, not visible to complainant.
    # Stored as NOTE_ADDED with is_field_report=True so the UI can render it distinctly
    # and the AI findings pipeline picks it up (NOTE_ADDED is already in _FINDINGS_EVENT_TYPES).
    event = _add_event(
        db, ticket, "NOTE_ADDED",
        step_id=event_step_id,
        note=payload.note,
        payload={"internal": True, "is_field_report": True},
        created_by=actor.user_id,
        seen=True,
        actor_role=_actor_role(actor),
        summary_regen_required=True,
    )
    return ActionOutcome(event=event, ticket=ticket, translate_note_event_id=event.event_id)


def request_reassignment(db: Session, ticket: Ticket, actor: "CurrentUser", payload) -> ActionOutcome:
    event_step_id = ticket.current_step_id
    reason = (payload.reassignment_reason_code or "").strip().upper()
    valid_reasons = {"OUT_OF_PACKAGE_SCOPE", "OUT_OF_LOCATION", "OTHER"}
    if reason not in valid_reasons:
        raise ActionError(f"reassignment_reason_code must be one of {sorted(valid_reasons)}")
    if reason == "OTHER" and not (payload.reassignment_notes or "").strip():
        raise ActionError("reassignment_notes required when reason is OTHER")

    # DESIGN-cast-model §3.4: resolve the reassignment authority via the fallback chain
    # (Dispatcher → Supervisor → project_admin). exclude_self=True — a bounce never targets
    # the assignee themselves. project_admin is the guaranteed backstop, so this only dead-ends
    # on a misconfigured project with no admin at all.
    from ticketing.services.reassignment import resolve_reassignment_authority

    authority = resolve_reassignment_authority(db, ticket, exclude_self=True)
    target_id = authority.user_id
    if not target_id:
        raise ActionError(
            "No reassignment authority is configured for this project. "
            "Ask an admin to staff a Dispatcher or Supervisor, or add a project administrator."
        )

    old_assigned = ticket.assigned_to_user_id
    ticket.assigned_to_user_id = target_id
    ticket.updated_by_user_id = actor.user_id

    event = _add_event(
        db, ticket, "REASSIGNMENT_REQUESTED",
        old_assigned=old_assigned,
        new_assigned=target_id,
        step_id=event_step_id,
        note=(payload.reassignment_notes or "").strip() or None,
        payload={
            "reason_code": reason,
            "reason_notes": (payload.reassignment_notes or "").strip() or None,
            "requested_by": actor.user_id,
            "authority_source": authority.source,
        },
        seen=False,
        notify_user_id=target_id,
        created_by=actor.user_id,
        actor_role=_actor_role(actor),
        summary_regen_required=True,
    )
    _add_event(
        db, ticket, "ASSIGNED",
        old_assigned=old_assigned,
        new_assigned=target_id,
        step_id=event_step_id,
        note=f"Reassignment routed to {authority.source.replace('_', ' ')} ({reason.replace('_', ' ').lower()})",
        payload={"reason_code": reason, "via_reassignment_request": True, "authority_source": authority.source},
        seen=False,
        notify_user_id=target_id,
        created_by=actor.user_id,
        actor_role=_actor_role(actor),
        summary_regen_required=False,
    )
    assignment_notify = None
    if target_id != old_assigned:
        assignment_notify = (target_id, old_assigned, "reassign")
    return ActionOutcome(event=event, ticket=ticket, assignment_notify=assignment_notify)


def grc_convene(db: Session, ticket: Ticket, actor: "CurrentUser", payload) -> ActionOutcome:
    # GRC Chair schedules hearing — notifies all GRC members (unseen events → badges)
    hearing_date = payload.grc_hearing_date if hasattr(payload, "grc_hearing_date") else None
    events = convene_grc(
        ticket, db,
        note=payload.note,
        convened_by_user_id=actor.user_id,
        hearing_date=hearing_date,
        actor_role=_actor_role(actor),
    )
    event = events[0]  # first event is the CONVENED event
    return ActionOutcome(event=event, ticket=ticket)


# action_type → handler. Keys must stay in sync with VALID_ACTIONS in the router.
ACTION_HANDLERS = {
    "ACKNOWLEDGE": acknowledge,
    "ESCALATE": escalate,
    "RESOLVE": resolve,
    "NOTE": note,
    "FIELD_REPORT": field_report,
    "REASSIGNMENT_REQUESTED": request_reassignment,
    "GRC_CONVENE": grc_convene,
}
