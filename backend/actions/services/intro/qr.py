"""Pure helpers for the /introduce landing action: payload parsing + QR lookup.

Extracted from ``ActionIntroduce`` so the action keeps only its dispatch flow.
``parse_introduce_payload`` is pure; ``resolve_qr_token`` performs lookups via the
injected ``db_manager`` and the QR-scan client, returning a plain slot bundle.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from backend.actions.utils.ticketing_dispatch import fetch_qr_scan
from backend.shared_functions.location_mapping import resolve_location_code_to_names

_logger = logging.getLogger(__name__)


def parse_introduce_payload(message: str, logger: Optional[logging.Logger] = None) -> Dict[str, Any]:
    """Extract the JSON payload embedded in the /introduce message.

    Recognised keys: province, district, flask_session_id, t (QR token). Any other
    keys are ignored. Returns an empty dict on parse failure.
    """
    log = logger or _logger
    if not message or "{" not in message or "}" not in message:
        return {}
    try:
        json_str = message[message.index("{") : message.rindex("}") + 1]
        data = json.loads(json_str)
    except (ValueError, json.JSONDecodeError) as exc:
        log.warning("parse_introduce_payload - failed to parse introduce payload: %s", exc)
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def resolve_qr_token(
    db_manager: Any,
    token: str,
    logger: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    """Resolve a QR token to a slot bundle (token + scan + place names).

    Always returns a dict — empty when the token is missing/invalid so the caller
    can fall back to the standard geo questions.
    """
    log = logger or _logger
    if not token:
        return {}
    scan = fetch_qr_scan(token)
    if not scan:
        log.info("resolve_qr_token - QR token unresolved, falling back to geo questions: token=%s", token)
        return {}

    location_code = scan.get("location_code")
    names: Dict[str, Any] = {}
    if location_code:
        try:
            names = resolve_location_code_to_names(db_manager, location_code) or {}
        except Exception as exc:  # pylint: disable=broad-except
            log.warning("resolve_qr_token - location code resolution failed: %s", exc)
            names = {}

    bundle = {
        "qr_token": token,
        "package_id": scan.get("package_id"),
        "package_label": scan.get("label"),
        "project_code": scan.get("project_code"),
        "location_code": location_code,
        "complainant_province": names.get("province_name"),
        "complainant_district": names.get("district_name"),
    }
    log.info(
        "resolve_qr_token - QR token resolved: token=%s package_id=%s project_code=%s "
        "location_code=%s district=%s province=%s",
        token,
        bundle.get("package_id"),
        bundle.get("project_code"),
        bundle.get("location_code"),
        bundle.get("complainant_district"),
        bundle.get("complainant_province"),
    )
    return bundle
