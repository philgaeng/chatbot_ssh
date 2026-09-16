# SPDX-License-Identifier: Apache-2.0

"""The staff-notification boundary — what may be emailed to someone who is not the complainant.

**Why this module exists, and why it is not in `backend/actions/`.** Three separate email paths
each carried the whole grievance record — a submission receipt (F-19), a follow-up request (F-19),
and a status update to an office list (F-22). Each was written by somebody solving a different
problem, and **none looked wrong at its own call site.** Two live in `backend/actions/`, one in
`backend/api/`. A control implemented in either would have to be copied into the other, and a
security control with two implementations has one that is out of date.

**The rule.** A notification to staff carries *what happened*, not *the record*. The recipient opens
the case in the platform — behind authentication, with an audit trail — instead of holding a copy in
a mailbox with neither.

Two independent controls, because each covers the other's failure mode:

1. **Allow-list** (`ADMIN_SAFE_FIELDS`), projected **before** formatting. Not a deny-list: a
   deny-list has to be updated when a new PII field is added, and nobody will.
2. **Sensitivity gate**, failing closed. A case on a sensitive workflow is visible only to the
   officers cast on it; none of these recipient lists is that cast. Suppressed **entirely** rather
   than trimmed — categories and a summary would themselves disclose that such a case exists.

⚠ **Residual, and it is not designed away.** The asynchronous detector can raise the sensitivity
flag *after* a notification is sent. The window is small — it writes during the contact/OTP steps,
and the submission notification runs after them — and control 1 is what bounds the damage when it
happens. That is why both exist rather than either.

Findings: `docs/dpg/privacy-assessment.md` F-19, F-22 · `docs/dpg/pii-egress-inventory.md` E5, E13
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Mapping, Optional, Tuple

from backend.config.constants import EMAIL_TEMPLATES, GRM_PORTAL_BASE_URL

logger = logging.getLogger(__name__)

# The complete set of keys that may reach a staff-facing email body. Everything else is dropped
# before `.format()` is called, so a template cannot render what it never receives.
#
# ⚠ Adding a key here is a privacy decision, not a formatting one. `complainant_id` is deliberately
# absent: it is pseudonymous rather than anonymous, and it is a direct index into the PII record.
ADMIN_SAFE_FIELDS = frozenset(
    {
        "grievance_id",
        "grievance_timestamp",
        "grievance_timeline",
        "grievance_categories",
        "grievance_location",
        "grievance_summary",
        "grievance_status",
        "grievance_status_update_date",
    }
)

# The value used when sensitivity cannot be established. Distinct from False on purpose:
# `.get(key, False)` reads "the caller never told us" as "not sensitive", which is the direction
# that mails a survivor's case to a list that must not see it.
SENSITIVITY_UNKNOWN = object()


def is_suppressed_for_sensitivity(data: Mapping[str, Any]) -> Tuple[bool, str]:
    """(suppress?, reason). An absent flag suppresses — see SENSITIVITY_UNKNOWN."""
    flag = data.get("grievance_sensitive_issue", SENSITIVITY_UNKNOWN)
    if flag is SENSITIVITY_UNKNOWN:
        return True, "unknown"
    if bool(flag):
        return True, "true"
    return False, "false"


def portal_link_html() -> str:
    """A link into the platform, or an instruction. Never a fabricated URL, and never a fallback
    to including the record because the link is missing — that degradation is how F-19 started."""
    if not GRM_PORTAL_BASE_URL:
        return "<p>Open the grievance in the GRM portal to review the full record.</p>"
    return (
        f'<p><a href="{GRM_PORTAL_BASE_URL.rstrip("/")}/tickets">Open the GRM portal</a> '
        "and search for the grievance ID above to review the full record.</p>"
    )


def project_admin_fields(data: Mapping[str, Any], *, not_provided: str) -> Dict[str, Any]:
    """Keep only ADMIN_SAFE_FIELDS, rendering lists as text. Nothing else survives."""
    safe: Dict[str, Any] = {}
    for key in ADMIN_SAFE_FIELDS:
        value = data.get(key)
        if isinstance(value, (list, tuple)):
            value = ", ".join(str(v) for v in value if v)
        safe[key] = value if value not in (None, "", []) else not_provided
    safe["portal_link_html"] = portal_link_html()
    return safe


def build_admin_email(
    body_name: str,
    data: Mapping[str, Any],
    *,
    language_code: str = "en",
    not_provided: str = "n/a",
) -> Optional[Tuple[str, str]]:
    """Return (subject, body) for a staff notification, or None if it must not be sent.

    Returns None — rather than raising or degrading — when the case is sensitive, when the template
    is missing, or when the template references a field outside the allow-list. **Refusing to send
    is the only safe response to that last one:** retrying with the full dict is exactly what F-19
    was, so the KeyError is the alarm rather than a problem to work around.
    """
    grievance_id = data.get("grievance_id") or "?"

    suppress, reason = is_suppressed_for_sensitivity(data)
    if suppress:
        logger.info(
            "Staff notification suppressed for grievance_id=%s (sensitive=%s): the recipients "
            "are not cast on the sensitive workflow",
            grievance_id,
            reason,
        )
        return None

    template = EMAIL_TEMPLATES.get(body_name, {}).get(language_code)
    subject_template = EMAIL_TEMPLATES.get(f"{body_name}_SUBJECT", {}).get(language_code)
    if not template or not subject_template:
        logger.error("No staff template for %s/%s", body_name, language_code)
        return None

    safe = project_admin_fields(data, not_provided=not_provided)
    try:
        return subject_template.format(**safe), template.format(**safe)
    except KeyError as missing:
        logger.error(
            "Staff template %s references non-safe field %s — refusing to send for "
            "grievance_id=%s",
            body_name,
            missing,
            grievance_id,
        )
        return None
