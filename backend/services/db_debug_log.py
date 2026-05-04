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
