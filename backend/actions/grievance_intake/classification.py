"""LLM classification trigger and retrieve-time polling."""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any, Dict, Optional, Text

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher

from backend.config.classification_status import LLM_FAILED, LLM_SKIPPED
from backend.config.database_constants import GRIEVANCE_CLASSIFICATION_STATUS

CLASSIFICATION_POLL_MAX_SECONDS = 20.0
CLASSIFICATION_POLL_INTERVAL_SECONDS = 0.5


def grievance_has_classification_content(
    grievance_data: Optional[Dict[str, Any]],
) -> bool:
    if not grievance_data:
        return False
    summary = (grievance_data.get("grievance_summary") or "").strip()
    categories = grievance_data.get("grievance_categories") or []
    return bool(summary or categories)


async def load_grievance_for_classification(
    db_manager: Any,
    logger: Any,
    grievance_id: str,
    *,
    wait_for_llm: bool = True,
) -> Optional[Dict[str, Any]]:
    """Load grievance row; poll briefly while LLM classification is still pending."""
    if not grievance_id:
        logger.error("retrieve_classification: missing grievance_id")
        return None

    deadline = time.monotonic() + CLASSIFICATION_POLL_MAX_SECONDS
    grievance_data: Optional[Dict[str, Any]] = None

    while True:
        grievance_data = db_manager.get_grievance_by_id(grievance_id)
        if grievance_data is None and db_manager.grievance_row_exists(grievance_id):
            logger.error(
                "retrieve_classification: row exists but read failed for %s",
                grievance_id,
            )
            grievance_data = db_manager.get_grievance_core_by_id(grievance_id)

        if grievance_data is None:
            return None

        if grievance_has_classification_content(grievance_data):
            return grievance_data

        status = grievance_data.get("grievance_classification_status")
        terminal_without_content = status in (
            LLM_SKIPPED,
            GRIEVANCE_CLASSIFICATION_STATUS.get("LLM_failed"),
            GRIEVANCE_CLASSIFICATION_STATUS.get("LLM_error"),
        )
        if terminal_without_content or not wait_for_llm:
            return grievance_data

        if time.monotonic() >= deadline:
            logger.warning(
                "retrieve_classification: timed out waiting for LLM content "
                "(grievance_id=%s db_status=%s)",
                grievance_id,
                status,
            )
            return grievance_data

        await asyncio.sleep(CLASSIFICATION_POLL_INTERVAL_SECONDS)


async def trigger_async_classification(
    form: Any,
    tracker: Tracker,
    dispatcher: CollectingDispatcher,
    grievance_description: Optional[str] = None,
) -> Dict[str, Any]:
    """Enqueue classify_and_summarize_grievance_task (non-blocking)."""
    grievance_id = tracker.get_slot("grievance_id")
    grievance_description = grievance_description or tracker.get_slot(
        "grievance_description"
    )
    form._initialize_language_and_helpers(tracker)

    if not grievance_description or not grievance_id:
        return {
            "grievance_classification_status": form.SKIP_VALUE,
            "grievance_summary": "",
            "grievance_categories": [],
            "grievance_summary_status": form.SKIP_VALUE,
            "grievance_categories_status": form.SKIP_VALUE,
        }

    try:
        try:
            from backend.task_queue.registered_tasks import (
                classify_and_summarize_grievance_task,
            )
        except ImportError as ie:
            form.logger.warning(
                "Celery not available (ImportError: %s); skipping async classification "
                "for grievance %s",
                ie,
                grievance_id,
            )
            if grievance_id:
                form.db_manager.update_grievance(
                    grievance_id,
                    {"grievance_classification_status": LLM_SKIPPED},
                )
            return {
                "grievance_summary": "",
                "grievance_categories": [],
                "grievance_summary_status": form.SKIP_VALUE,
                "grievance_categories_status": form.SKIP_VALUE,
            }

        session_id = tracker.get_slot("flask_session_id") or tracker.sender_id
        input_data = {
            "grievance_id": grievance_id,
            "complainant_id": tracker.get_slot("complainant_id"),
            "language_code": form.language_code,
            "complainant_province": tracker.get_slot("complainant_province")
            or form.province,
            "complainant_district": tracker.get_slot("complainant_district")
            or form.district,
            "flask_session_id": session_id,
            "session_id": session_id,
            "values": {"grievance_description": grievance_description},
        }
        form.logger.info(
            "classification_trigger_prepare grievance_id=%s session_id=%s "
            "has_description=%s description_len=%s",
            grievance_id,
            session_id,
            bool(grievance_description),
            len(grievance_description or ""),
        )

        def _fire() -> None:
            try:
                task_result = classify_and_summarize_grievance_task.delay(input_data)
                form.logger.info(
                    "classification_trigger_enqueued grievance_id=%s task_id=%s",
                    grievance_id,
                    task_result.id,
                )
            except Exception as e:
                form.logger.warning(
                    "classification_trigger_enqueue_failed grievance_id=%s error=%s",
                    grievance_id,
                    e,
                )

        threading.Thread(target=_fire, daemon=True).start()
        return {}

    except Exception as e:
        form.logger.error(f"Error launching async classification: {e}")
        if grievance_id:
            form.db_manager.update_grievance(
                grievance_id,
                {"grievance_classification_status": LLM_FAILED},
            )
        return {
            "grievance_summary": "",
            "grievance_categories": [],
            "grievance_summary_status": form.SKIP_VALUE,
            "grievance_categories_status": form.SKIP_VALUE,
        }
