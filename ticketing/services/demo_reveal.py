"""
Demo-only reveal fallback when seed grievance_ids are not in public.grievances.

Mock tickets reference IDs like GRV-2025-002 that exist only in ticketing.*.
Reveal still needs plaintext for the audited overlay during local/demo use.
"""
from __future__ import annotations

from typing import Any

# Fictional demo PII — not stored in ticketing.*; shown only after vault reveal.
_DEMO_COMPLAINANT_PII: dict[str, dict[str, str]] = {
    "CPL-2025-001": {
        "complainant_full_name": "Sita Devi Sharma",
        "complainant_phone": "+977 9841234567",
        "complainant_email": "sita.sharma.demo@example.com",
        "complainant_address": "Ward 4, Urlabari, Morang",
    },
    "CPL-2025-002": {
        "complainant_full_name": "Ram Bahadur Thapa",
        "complainant_phone": "+977 9812345678",
        "complainant_email": "ram.thapa.demo@example.com",
        "complainant_address": "Farm road, Dharan-8, Sunsari",
    },
    "CPL-2025-003": {
        "complainant_full_name": "Gita Kumari Rai",
        "complainant_phone": "+977 9801122334",
        "complainant_email": "gita.rai.demo@example.com",
        "complainant_address": "Biratnagar-10, Morang",
    },
    "CPL-2025-004": {
        "complainant_full_name": "Hari Prasad Yadav",
        "complainant_phone": "+977 9856677889",
        "complainant_email": "hari.yadav.demo@example.com",
        "complainant_address": "Biratnagar outskirts, Morang",
    },
    "CPL-2025-005": {
        "complainant_full_name": "Maya Gurung",
        "complainant_phone": "+977 9823456789",
        "complainant_email": "maya.gurung.demo@example.com",
        "complainant_address": "Irrigation channel ward, Urlabari, Morang",
    },
    "CPL-2025-SEAH-001": {
        "complainant_full_name": "Anonymous Complainant (SEAH)",
        "complainant_phone": "+977 9800000001",
        "complainant_email": "seah.confidential.demo@example.com",
        "complainant_address": "Withheld — SEAH case",
    },
}


def ticket_reveal_fallback_grievance(ticket: Any) -> dict[str, Any]:
    """Build a grievance-shaped dict from ticket cache + demo complainant PII."""
    pii = _DEMO_COMPLAINANT_PII.get(ticket.complainant_id or "", {})
    location = ticket.grievance_location or ""
    return {
        "grievance_description": ticket.grievance_summary or "",
        "complainant_full_name": pii.get(
            "complainant_full_name", "Demo complainant"
        ),
        "complainant_phone": pii.get("complainant_phone", "+977 9800000000"),
        "complainant_email": pii.get(
            "complainant_email", "complainant.demo@example.com"
        ),
        "complainant_address": pii.get(
            "complainant_address", location or "Address not on file (demo)"
        ),
        "complainant_municipality": None,
        "complainant_district": None,
    }
