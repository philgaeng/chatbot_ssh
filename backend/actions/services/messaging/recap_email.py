"""Recap email preparation and delivery via Messaging API."""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
from typing import Any, Callable, Dict, List, Tuple

from rasa_sdk.executor import CollectingDispatcher

from backend.config.constants import ADMIN_EMAILS, EMAIL_TEMPLATES

logger = logging.getLogger(__name__)


def prepare_recap_email(
    email_data: Dict[str, Any],
    body_name: str,
    *,
    language_code: str,
    not_provided: str,
) -> Tuple[str, str]:
    try:
        if (
            email_data.get("grievance_categories")
            and email_data.get("grievance_categories") != not_provided
        ):
            categories_html = "".join(
                f"<li>{category}</li>"
                for category in (email_data["grievance_categories"] or [])
            )
        else:
            categories_html = ""

        if body_name not in EMAIL_TEMPLATES:
            logger.error("Unknown body_name: %s", body_name)
            return "", ""

        body = EMAIL_TEMPLATES[body_name][language_code]
        subject_key = f"{body_name}_SUBJECT"
        subject = (
            EMAIL_TEMPLATES[subject_key][language_code]
            if subject_key in EMAIL_TEMPLATES
            else body
        )

        format_kwargs = dict(
            complainant_name=email_data.get("complainant_full_name", not_provided),
            grievance_description=email_data.get("grievance_description", not_provided),
            project=email_data.get("complainant_project", not_provided),
            complainant_municipality=email_data.get("complainant_municipality", not_provided),
            complainant_village=email_data.get("complainant_village", not_provided),
            complainant_address=email_data.get("complainant_address", not_provided),
            complainant_phone=email_data.get("complainant_phone", not_provided),
            grievance_id=email_data.get("grievance_id", ""),
            complainant_email=email_data.get("complainant_email", not_provided),
            grievance_timeline=email_data.get("grievance_timeline", not_provided),
            grievance_timestamp=email_data.get("grievance_timestamp", not_provided),
            categories_html=categories_html,
            grievance_summary=email_data.get("grievance_summary", not_provided),
            grievance_categories=email_data.get("grievance_categories", not_provided),
        )
        return body.format(**format_kwargs), subject.format(**format_kwargs)
    except Exception as exc:
        logger.error("Failed to prepare recap email: %s", exc)
        return "", ""


async def send_recap_email(
    to_emails: List[str],
    grievance_data: Dict[str, Any],
    body_name: str,
    *,
    language_code: str,
    not_provided: str,
) -> None:
    try:
        body, subject = prepare_recap_email(
            grievance_data,
            body_name,
            language_code=language_code,
            not_provided=not_provided,
        )
        if not subject or not body:
            logger.error(
                "Failed to prepare recap email: empty subject/body for %s",
                body_name,
            )
            return

        grievance_id = grievance_data.get("grievance_id")
        context = {
            "source_system": "chatbot",
            "purpose": body_name,
            "grievance_id": grievance_id,
            "channel": "email",
        }

        from backend.clients.messaging_api import send_email as send_email_via_api

        def _deliver() -> None:
            send_email_via_api(to_emails, subject, body, context=context)

        await asyncio.to_thread(_deliver)
        logger.debug(
            "Recap email sent via Messaging API for grievance_id=%s template=%s",
            grievance_id,
            body_name,
        )
    except Exception as exc:
        logger.error("Failed to send system notification email: %s", exc)


async def send_recap_email_to_admin(
    grievance_data: Dict[str, Any],
    body_name: str,
    *,
    language_code: str,
    not_provided: str,
) -> None:
    try:
        await send_recap_email(
            ADMIN_EMAILS,
            grievance_data,
            body_name,
            language_code=language_code,
            not_provided=not_provided,
        )
    except Exception as exc:
        logger.error("Failed to send recap email to admin: %s", exc)
        logger.error("Admin email error details: %s", traceback.format_exc())


async def send_recap_email_to_complainant(
    complainant_email: str,
    body_name: str,
    grievance_data: Dict[str, Any],
    dispatcher: CollectingDispatcher,
    *,
    language_code: str,
    not_provided: str,
    get_utterance: Callable[[int], str],
) -> None:
    try:
        await send_recap_email(
            [complainant_email],
            grievance_data,
            body_name,
            language_code=language_code,
            not_provided=not_provided,
        )
        message = get_utterance(3)
        dispatcher.utter_message(text=message.format(complainant_email=complainant_email))
    except Exception as exc:
        logger.error(
            "Failed to send recap email to complainant %s: %s",
            complainant_email,
            exc,
        )
        logger.error("Complainant email error details: %s", traceback.format_exc())
