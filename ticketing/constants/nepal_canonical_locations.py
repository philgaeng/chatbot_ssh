"""
Human-readable canonical location_code values for Nepal per docs/ticketing_system/LOCATION_CODES.md.

- Provinces: P1 … P7 (CAPS, no NP_ prefix).
- Districts: {province}_{MNEMONIC} e.g. P1_MOR (3 letters; 4 if collision in same province).
- Municipalities: {district}_{MNEMONIC} (3 letters; extend on collision under same parent).

Used by location import (JSON/CSV) and by DB migration from legacy NP_* keys.
"""
from __future__ import annotations

import re
from typing import Iterable

__all__ = [
    "letters_prefix",
    "next_mnemonic",
    "district_code_for_np",
    "municipality_code_for_np",
    "province_code_for_np_json",
    "legacy_province_np_pattern",
    "collect_english_names",
    "is_already_canonical_np",
    "plan_np_legacy_to_canonical_renames",
    "apply_location_rename_map",
]

_PROV_LEGACY_WIDE = re.compile(r"^NP_P(\d+)$")
_CANONICAL_SHAPE = re.compile(r"^P\d+(_[A-Z][A-Z0-9]*)*$")


def letters_prefix(name: str, length: int) -> str:
    """Uppercase A–Z only from *name*, then take first *length* letters (min 1)."""
    if not name:
        return "X" * max(1, min(3, length))
    letters = "".join(c for c in name.upper() if c.isalpha())
    if not letters:
        return "X" * max(1, min(3, length))
    if len(letters) >= length:
        return letters[:length]
    return letters + ("X" * (length - len(letters)))


def next_mnemonic(name: str, used: set[str], base_len: int = 3, max_len: int = 8) -> str:
    """
    Deterministic mnemonic unique within *used*. Tries 3 letters, then 4, then suffix MO2 style.
    """
    base = re.sub(r"\s+", " ", (name or "").strip())
    for L in range(base_len, max_len + 1):
        cand = letters_prefix(base, L)
        if cand not in used:
            used.add(cand)
            return cand
    n = 2
    while True:
        cand = f"{letters_prefix(base, 3)[:2]}{n}"
        if cand not in used:
            used.add(cand)
            return cand
        n += 1


def province_code_for_np_json(source_id: int) -> str:
    """Province node from JSON uses numeric id 1–7 → P1–P7."""
    if source_id < 1 or source_id > 7:
        # Still emit P{n} for uncommon trees; doc focuses on seven provinces.
        return f"P{source_id}"
    return f"P{source_id}"


def legacy_province_np_pattern() -> re.Pattern[str]:
    return _PROV_LEGACY_WIDE


def province_code_from_legacy_or_source(
    old_code: str,
    source_id: int | None,
    level_number: int,
) -> str | None:
    """Resolve new province code from legacy NP_Pn or source_id (level 1 only)."""
    if level_number != 1:
        return None
    m = _PROV_LEGACY_WIDE.match(old_code.strip())
    if m:
        return f"P{int(m.group(1))}"
    if source_id is not None:
        return province_code_for_np_json(int(source_id))
    return None


def district_code_for_np(province_code: str, english_name: str, used_mnemonics: set[str]) -> str:
    mn = next_mnemonic(english_name, used_mnemonics, base_len=3)
    return f"{province_code}_{mn}"


def municipality_code_for_np(district_code: str, english_name: str, used_mnemonics: set[str]) -> str:
    mn = next_mnemonic(english_name, used_mnemonics, base_len=3)
    return f"{district_code}_{mn}"


def collect_english_names(trans_rows: Iterable[dict]) -> dict[str, str]:
    """First English name per location_code from translation rows."""
    out: dict[str, str] = {}
    for row in trans_rows:
        if row.get("lang_code") != "en":
            continue
        code = (row.get("location_code") or "").strip()
        name = (row.get("name") or "").strip()
        if code and name and code not in out:
            out[code] = name
    return out


def is_already_canonical_np(code: str) -> bool:
    """True if *code* matches P1 / P1_JHA / P1_JHA_BIR style (not legacy NP_*)."""
    c = (code or "").strip()
    if not c.startswith("P") or c.startswith("NP"):
        return False
    return bool(_CANONICAL_SHAPE.match(c))


def plan_np_legacy_to_canonical_renames(
    loc_rows: list[dict],
    trans_rows: list[dict],
) -> dict[str, str]:
    """
    Build old_code -> new_code for rows with country_code NP.
    Identity for already-canonical codes. Rows with unmapped parents keep their old code.
    """
    names = collect_english_names(trans_rows)
    np_rows = [r for r in loc_rows if (r.get("country_code") or "").upper() == "NP"]
    sorted_rows = sorted(
        np_rows,
        key=lambda r: (int(r.get("level_number") or 99), str(r.get("location_code") or "")),
    )

    old_to_new: dict[str, str] = {}
    used_by_parent: dict[str, set[str]] = {}

    def used_for(parent_new: str) -> set[str]:
        return used_by_parent.setdefault(parent_new, set())

    for row in sorted_rows:
        old = (row.get("location_code") or "").strip()
        if not old:
            continue
        if is_already_canonical_np(old):
            old_to_new[old] = old
            continue

        level = int(row.get("level_number") or 0)
        parent_old = row.get("parent_location_code")
        try:
            src = row.get("source_id")
            source_id = int(src) if src is not None and str(src).strip() != "" else None
        except (TypeError, ValueError):
            source_id = None

        nm = names.get(old, "")

        if level == 1:
            new = province_code_from_legacy_or_source(old, source_id, level)
            if not new:
                new = f"P{source_id or 1}"
            old_to_new[old] = new
            continue

        parent_new = None
        if parent_old:
            parent_new = old_to_new.get(parent_old)
        if not parent_new:
            old_to_new[old] = old
            continue

        if not nm:
            nm = old

        if level == 2:
            new = district_code_for_np(parent_new, nm, used_for(parent_new))
        else:
            new = municipality_code_for_np(parent_new, nm, used_for(parent_new))

        old_to_new[old] = new

    for row in np_rows:
        oc = (row.get("location_code") or "").strip()
        if oc and oc not in old_to_new:
            old_to_new[oc] = oc

    return old_to_new


def apply_location_rename_map(
    loc_rows: list[dict],
    trans_rows: list[dict],
    rename: dict[str, str],
) -> None:
    """Mutate *loc_rows* and *trans_rows* in place."""
    for r in loc_rows:
        oc = (r.get("location_code") or "").strip()
        if oc in rename:
            r["location_code"] = rename[oc]
        pl = r.get("parent_location_code")
        if pl:
            r["parent_location_code"] = rename.get(pl, pl)
    for r in trans_rows:
        oc = (r.get("location_code") or "").strip()
        if oc in rename:
            r["location_code"] = rename[oc]
