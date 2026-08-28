# SPDX-License-Identifier: Apache-2.0

"""
Safe one-line summaries for service / DB DEBUG and INFO logs.

Avoid logging full ORM rows, ciphertext, phones, emails, or grievance body text.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


def grievance_row_summary(row: Optional[Dict[str, Any]]) -> str:
    """Grievance dict: id, shape, text lengths — no field values."""
    if not row:
        return "grievance=None"
    gid = row.get("grievance_id", "?")
    desc = row.get("grievance_description") or ""
    summ = row.get("grievance_summary") or ""
    dlen = len(desc) if isinstance(desc, str) else 0
    slen = len(summ) if isinstance(summ, str) else 0
    cats = row.get("grievance_categories")
    if isinstance(cats, list):
        cat_n = len(cats)
    else:
        cat_n = 1 if cats else 0
    mod = row.get("grievance_modification_date")
    return (
        f"id={gid} field_count={len(row)} description_len={dlen} "
        f"summary_len={slen} categories_n={cat_n} modified={mod}"
    )


def complainant_row_summary(row: Optional[Dict[str, Any]]) -> str:
    if not row:
        return "complainant=None"
    cid = row.get("complainant_id", "?")
    return f"id={cid} field_count={len(row)}"


def grievance_join_row_summary(row: Optional[Dict[str, Any]]) -> str:
    """Joined grievance + status row (e.g. phone lookup) without PII values."""
    if not row:
        return "row=None"
    gid = row.get("grievance_id", "?")
    st = row.get("grievance_status")
    return f"grievance_id={gid} field_count={len(row)} status={st!r}"


def dict_keys_sorted(data: Optional[Dict[str, Any]]) -> str:
    if not data:
        return "keys=[]"
    return f"keys={sorted(data.keys())}"


def sql_params_shape(params: Sequence[Any]) -> str:
    """Describe bind parameter shapes only (no values)."""
    parts: List[str] = []
    for p in params:
        if p is None:
            parts.append("NULL")
        elif isinstance(p, (bytes, memoryview)):
            parts.append(f"bytes[{len(bytes(p))}]")
        elif isinstance(p, str):
            parts.append(f"str[{len(p)}]")
        else:
            parts.append(type(p).__name__)
    return f"n={len(parts)} [{','.join(parts)}]"


def sql_first_row_shape(columns: Sequence[str], row: Sequence[Any]) -> str:
    """First raw SQL row: column names + value types / lengths only."""
    if not columns or row is None:
        return "empty"
    pairs: List[str] = []
    for c, v in list(zip(columns, row))[:24]:
        if v is None:
            pairs.append(f"{c}=NULL")
        elif isinstance(v, (bytes, memoryview)):
            pairs.append(f"{c}=bytes[{len(bytes(v))}]")
        elif isinstance(v, str):
            pairs.append(f"{c}=str[{len(v)}]")
        else:
            pairs.append(f"{c}={type(v).__name__}")
    out = "; ".join(pairs)
    if len(columns) > 24:
        out += "; ..."
    return out


def redact_db_params(db_params: Dict[str, Any]) -> Dict[str, Any]:
    """Copy DB config dict with password redacted for logging."""
    out = dict(db_params)
    if out.get("password"):
        out["password"] = "***"
    return out


def mask_phone_for_log(phone: Optional[str]) -> str:
    """Last few digits only for operational logs."""
    if not phone:
        return "(none)"
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) <= 4:
        return "(redacted)"
    return f"***{digits[-4:]}"


def email_send_log_summary(to_emails: Sequence[str]) -> str:
    return f"recipient_count={len(to_emails)}"


def text_len_for_log(label: str, text: Optional[str]) -> str:
    if text is None:
        return f"{label}=None"
    if not isinstance(text, str):
        text = str(text)
    return f"{label}_chars={len(text)}"


def text_prefix_for_log(label: str, text: Optional[str], chars: int = 8) -> str:
    """First ``chars`` characters of free text, plus its length — enough to find the record.

    The owner's rule (2026-08-27): *"prune the logs by just logging the first 8 characters so
    someone can find it."* **It applies to free text only** — a grievance narrative, a summary, an
    officer note. A prefix of a *bounded identifier* is not a redaction: 8 characters of a 10-digit
    phone leaves 8 of 10 digits, and 8 characters of a 6-digit OTP leaves the whole OTP.

    So the rule is per field type, and this function is the free-text half:
      * free text        → this function
      * phone            → ``mask_phone_for_log`` (last 4 only)
      * OTP              → never logged, at any length
      * whole grievance  → ``grievance_row_summary``

    ⚠ Eight characters of a narrative is still narrative, and can read *"Ram Baha"*. That is a
    bounded, deliberate trade for findability — the same one ``_grievance_ref`` makes in
    ``LLM_services.py`` — not an anonymisation. Do not describe it as one.
    """
    if text is None:
        return f"{label}=None"
    if not isinstance(text, str):
        text = str(text)
    if not text:
        return f"{label}=''"
    head = text[:chars]
    suffix = "…" if len(text) > chars else ""
    return f"{label}={head!r}{suffix} ({len(text)} chars)"
