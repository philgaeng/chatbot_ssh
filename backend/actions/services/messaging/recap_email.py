# SPDX-License-Identifier: Apache-2.0

"""Recap email preparation and delivery via Messaging API."""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
from typing import Any, Callable, Dict, List, Tuple

from rasa_sdk.executor import CollectingDispatcher

from backend.config.constants import ADMIN_EMAILS, EMAIL_TEMPLATES, GRM_PORTAL_BASE_URL

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


# ── The admin boundary (F-19, 2026-09-03) ────────────────────────────────────
# Until 2026-09-03 an admin notification was the complainant's own receipt: the whole
# grievance record — raw narrative, name, phone, address, email — mailed to a configured
# list on every submission, with no gate for sensitive cases. It was ranked ABOVE the
# model call in `docs/dpg/pii-egress-inventory.md` for likelihood of real exposure.
#
# ⭐ Fixed HERE, at the one function every admin send passes through, rather than in each
# template — the same choice DPG-33 and DPG-34 made at the model and log boundaries, and
# for the same reason: a per-template fix is correct until someone adds a template.
#
# ALLOW-LIST, not deny-list. `ADMIN_SAFE_FIELDS` is what may reach an admin body; every
# other key is dropped before formatting rather than removed after. A deny-list has to be
# updated when a new PII field is added, and nobody will.
ADMIN_SAFE_FIELDS = frozenset(
    {
        "grievance_id",
        "grievance_timestamp",
        "grievance_timeline",
        "grievance_categories",
        "grievance_location",
        "grievance_summary",
    }
)

# The value used when sensitivity cannot be established. Distinct from False on purpose:
# `.get(key, False)` would treat "the caller never told us" as "not sensitive", which is
# the failure direction that mails a survivor's case to a list that must not see it.
_SENSITIVITY_UNKNOWN = object()


def _admin_portal_link_html() -> str:
    """A link into the platform, or nothing. Never a fabricated URL."""
    if not GRM_PORTAL_BASE_URL:
        return (
            "<p>Open the grievance in the GRM portal to review the full record.</p>"
        )
    return (
        f'<p><a href="{GRM_PORTAL_BASE_URL.rstrip("/")}/tickets">'
        "Open the GRM portal</a> and search for the grievance ID above to review the "
        "full record.</p>"
    )


def _project_admin_fields(grievance_data: Dict[str, Any], *, not_provided: str) -> Dict[str, Any]:
    """Keep only ADMIN_SAFE_FIELDS, rendering lists as text. Nothing else survives."""
    safe: Dict[str, Any] = {}
    for key in ADMIN_SAFE_FIELDS:
        value = grievance_data.get(key)
        if isinstance(value, (list, tuple)):
            value = ", ".join(str(v) for v in value if v)
        safe[key] = value if value not in (None, "", []) else not_provided
    safe["portal_link_html"] = _admin_portal_link_html()
    return safe


async def send_recap_email_to_admin(
    grievance_data: Dict[str, Any],
    body_name: str,
    *,
    language_code: str,
    not_provided: str,
) -> None:
    """Notify the admin list. Carries no complainant PII, and nothing at all for a
    sensitive case.

    Two independent controls, because either alone has a failure mode:

    1. **Sensitivity gate, failing closed.** A SEAH case is visible only to officers cast
       on the sensitive workflow; the admin list is not that cast. An unknown flag is
       treated as sensitive. ⚠ Residual: the flag can still be raised by the asynchronous
       detector *after* this runs, so a case flagged late is mailed as ordinary. The
       window is small (the detector writes during the contact/OTP steps, this runs after
       them) and control 2 is what bounds the damage — which is why it exists.
    2. **Allow-list projection.** Even a case that slips control 1 discloses no narrative
       and no contact details, because those keys never reach `.format()`.
    """
    grievance_id = grievance_data.get("grievance_id") or "?"
    sensitive = grievance_data.get("grievance_sensitive_issue", _SENSITIVITY_UNKNOWN)
    if sensitive is _SENSITIVITY_UNKNOWN or bool(sensitive):
        logger.info(
            "Admin recap suppressed for grievance_id=%s (sensitive=%s): the admin list "
            "is not cast on the sensitive workflow",
            grievance_id,
            "unknown" if sensitive is _SENSITIVITY_UNKNOWN else "true",
        )
        return

    try:
        template = EMAIL_TEMPLATES.get(body_name, {}).get(language_code)
        subject_template = EMAIL_TEMPLATES.get(f"{body_name}_SUBJECT", {}).get(language_code)
        if not template or not subject_template:
            logger.error("No admin template for %s/%s", body_name, language_code)
            return

        safe = _project_admin_fields(grievance_data, not_provided=not_provided)
        try:
            body = template.format(**safe)
            subject = subject_template.format(**safe)
        except KeyError as missing:
            # ⭐ The second half of the allow-list, and the reason projection happens
            # BEFORE formatting: a template referencing a field outside ADMIN_SAFE_FIELDS
            # raises here and the mail is NOT sent. Refusing to send is the only safe
            # response — falling back to the full dict is what created F-19.
            logger.error(
                "Admin template %s references non-safe field %s — refusing to send for "
                "grievance_id=%s",
                body_name,
                missing,
                grievance_id,
            )
            return

        if not ADMIN_EMAILS:
            return

        context = {
            "source_system": "chatbot",
            "purpose": body_name,
            "grievance_id": grievance_data.get("grievance_id"),
            "channel": "email",
        }
        from backend.clients.messaging_api import send_email as send_email_via_api

        def _deliver() -> None:
            send_email_via_api(ADMIN_EMAILS, subject, body, context=context)

        await asyncio.to_thread(_deliver)
        logger.debug(
            "Admin notification sent for grievance_id=%s template=%s",
            grievance_id,
            body_name,
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
