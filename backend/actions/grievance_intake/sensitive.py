"""Sensitive content detection during grievance text intake."""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Dict, Optional, Text

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher


def trigger_detect_sensitive_content_task(
    logger: Any,
    text: str,
    language_code: str,
    *,
    grievance_id: Optional[str] = None,
    session_id: Optional[str] = None,
    complainant_id: Optional[str] = None,
) -> None:
    """Queue detect_sensitive_content_task in a background thread."""
    logger.info(
        "Firing detect_sensitive_content_task in background (grievance_id=%s, session_id=%s)",
        grievance_id,
        session_id,
    )

    def _fire() -> None:
        try:
            from backend.task_queue.registered_tasks import detect_sensitive_content_task

            detect_sensitive_content_task.delay(
                text=text,
                language_code=language_code,
                grievance_id=grievance_id,
                session_id=session_id,
                complainant_id=complainant_id,
            )
        except Exception as e:
            logger.warning(f"Could not queue detect_sensitive_content task: {e}")

    threading.Thread(target=_fire, daemon=True).start()


def persist_grievance_description_for_detection(
    form: Any,
    tracker: Tracker,
    description: str,
) -> None:
    """Ensure grievance row exists so the sensitive Celery task can write results."""
    grievance_id = tracker.get_slot("grievance_id")
    complainant_id = tracker.get_slot("complainant_id")
    if not grievance_id or not complainant_id:
        return
    try:
        form.db_manager.create_or_update_complainant({
            "complainant_id": complainant_id,
            "complainant_province": tracker.get_slot("complainant_province"),
            "complainant_district": tracker.get_slot("complainant_district"),
        })
        form.db_manager.create_or_update_grievance({
            "grievance_id": grievance_id,
            "complainant_id": complainant_id,
            "grievance_description": description,
            "source": "bot",
        })
    except Exception as e:
        form.logger.warning(f"Could not ensure grievance in DB for sensitive task: {e}")


async def get_sensitive_issue_slots_on_submit(
    form: Any,
    full_description: str,
    session_id: Optional[str],
    grievance_id: Optional[str],
    dispatcher: CollectingDispatcher,
) -> Dict[Text, Any]:
    """Prefer DB flag from Celery; brief poll then keyword fallback."""
    if grievance_id:
        try:
            form.logger.debug(
                "Sensitive submit: start DB polling | grievance_id=%s, session_id=%s",
                grievance_id,
                session_id,
            )
            for attempt in range(3):
                grievance = form.db_manager.get_grievance_by_id(grievance_id)
                if grievance is not None and "grievance_sensitive_issue" in grievance:
                    flag_from_db = grievance.get("grievance_sensitive_issue")
                    form.logger.debug(
                        "Sensitive submit: poll %s | grievance_id=%s, grievance_sensitive_issue=%s",
                        attempt,
                        grievance_id,
                        flag_from_db,
                    )
                    if flag_from_db:
                        return {
                            "grievance_sensitive_issue": True,
                            "sensitive_issues_category": "sensitive_content",
                            "sensitive_issues_level": grievance.get(
                                "sensitive_issues_level", "low"
                            ),
                            "sensitive_issues_message": grievance.get(
                                "sensitive_issues_message", ""
                            ),
                            "sensitive_issues_confidence": grievance.get(
                                "sensitive_issues_confidence"
                            ),
                        }
                await asyncio.sleep(0.3)
        except Exception as e:
            form.logger.warning(f"Could not read grievance from DB for sensitive slots: {e}")

    form.logger.debug(
        "Sensitive submit: using keyword detection fallback | grievance_id=%s, session_id=%s",
        grievance_id,
        session_id,
    )
    return form.detect_sensitive_content(dispatcher, full_description) or {
        "grievance_sensitive_issue": False
    }
