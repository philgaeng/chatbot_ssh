"""Fuzzy full-name lookup against complainant DB."""

from __future__ import annotations

from typing import Any, List


def validate_full_name_to_list(
    full_name: str,
    db_manager: Any,
    helpers: Any,
) -> list:
    full_name = full_name.lower().strip()
    all_full_names = db_manager.get_all_complainant_full_names()
    return helpers.match_full_name_list(full_name, all_full_names)
