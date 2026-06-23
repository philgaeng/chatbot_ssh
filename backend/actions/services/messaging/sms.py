"""SMS delivery via Messaging API."""

from __future__ import annotations

import logging
import traceback
from typing import Any, Dict

from backend.clients.messaging_api import send_sms as send_sms_via_api
from backend.config.constants import DIC_SMS_TEMPLATES

logger = logging.getLogger(__name__)


def send_sms_from_template(
    sms_data: Dict[str, Any],
    body_name: str,
    *,
    language_code: str,
) -> None:
    try:
        complainant_phone = sms_data["complainant_phone"]
        sms_body = DIC_SMS_TEMPLATES[body_name][language_code]
        sms_body = sms_body.format(**sms_data)
        context = {
            "source_system": "chatbot",
            "purpose": body_name,
            "grievance_id": sms_data.get("grievance_id"),
            "channel": "sms",
        }
        send_sms_via_api(complainant_phone, sms_body, context=context)
    except Exception as exc:
        logger.error("Failed to send SMS: %s", exc)
        logger.error("SMS error details: %s", traceback.format_exc())
