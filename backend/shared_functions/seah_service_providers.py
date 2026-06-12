"""Lookup and message formatting for SEAH service provider directory rows."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ticketing.constants.nepal_canonical_locations import (
    district_code_for_np,
    municipality_code_for_np,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LOCATION_JSON = _REPO_ROOT / "backend/dev-resources/location_dataset/en_cleaned.json"

_SUFFIX_RE = re.compile(
    r"\s*(Metropolitan City|Sub-Metropolitan city|Sub-Metropolitan City|Municipality|Rural Municipality)\s*$",
    re.IGNORECASE,
)


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    return re.sub(r"\s+", " ", text).strip()


def _norm_place(value: Optional[str]) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    text = _SUFFIX_RE.sub("", text)
    return text.lower()


def _slug(value: str, max_len: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:max_len] or "provider"


def _build_location_index() -> Dict[Tuple[str, str], Tuple[str, str, str, str, str, str]]:
    """(district_norm, municipality_norm) -> (country, province_code, district_code, municipality_code, province, district)."""
    with open(_LOCATION_JSON, encoding="utf-8") as f:
        data = json.load(f)

    index: Dict[Tuple[str, str], Tuple[str, str, str, str, str, str]] = {}
    for prov in data:
        province_code = f"P{prov['id']}"
        province_name = _clean_text(prov.get("name"))
        used_districts: set[str] = set()
        for dist in prov.get("districts", []):
            district_name = _clean_text(dist.get("name"))
            district_code = district_code_for_np(province_code, district_name, used_districts)
            used_munis: set[str] = set()
            for muni in dist.get("municipalities", []):
                muni_name = _clean_text(muni.get("name"))
                municipality_code = municipality_code_for_np(district_code, muni_name, used_munis)
                index[(_norm_place(district_name), _norm_place(muni_name))] = (
                    "NP",
                    province_code,
                    district_code,
                    municipality_code,
                    province_name,
                    district_name,
                )
    return index


def resolve_location_codes(
    province: Optional[str],
    district: Optional[str],
    municipality: Optional[str],
) -> Dict[str, Optional[str]]:
    """Best-effort canonical codes from complainant-facing place names."""
    district_key = _norm_place(district)
    municipality_key = _norm_place(municipality)
    result: Dict[str, Optional[str]] = {
        "country_code": "NP",
        "province_code": None,
        "district_code": None,
        "municipality_code": None,
    }
    if not district_key:
        return result

    index = _build_location_index()
    if municipality_key:
        row = index.get((district_key, municipality_key))
        if row:
            result["province_code"] = row[1]
            result["district_code"] = row[2]
            result["municipality_code"] = row[3]
            return result

    for (d_key, _), row in index.items():
        if d_key == district_key:
            result["province_code"] = row[1]
            result["district_code"] = row[2]
            break
    return result


def format_provider_details_block(row: Dict[str, Any], language_code: str) -> str:
    name = _clean_text(row.get("seah_center_name"))
    address = _clean_text(row.get("address"))
    phone = _clean_text(row.get("phone"))
    municipality = _clean_text(row.get("municipality"))
    district = _clean_text(row.get("district"))

    if language_code == "ne":
        lines: List[str] = []
        if name:
            lines.append(name)
        location_bits = [b for b in (address, municipality, district) if b]
        if location_bits:
            lines.append("ठेगाना : " + ", ".join(location_bits))
        if phone:
            lines.append(f"फोन : {phone}")
        return "\n".join(lines)

    lines = []
    if name:
        lines.append(name)
    location_bits = [b for b in (address, municipality, district) if b]
    if location_bits:
        lines.append("Address : " + ", ".join(location_bits))
    if phone:
        lines.append(f"Phone : {phone}")
    return "\n".join(lines)


def format_recommendation_utterance(
    providers: List[Dict[str, Any]],
    language_code: str,
    municipality: Optional[str] = None,
    district: Optional[str] = None,
) -> str:
    place = _clean_text(municipality) or _clean_text(district) or "your area"
    if not providers:
        if language_code == "ne":
            return (
                f"हामी तपाईंलाई {place} मा उपलब्ध SEAH सहयोग केन्द्रसँग सम्पर्क गर्न सिफारिस गर्दछौं। "
                "थप विवरणका लागि https://nwchelpline.gov.np हेर्नुहोस्।"
            )
        return (
            f"We recommend that you contact a SEAH support centre serving {place} "
            "where special support can be provided to you."
        )

    if len(providers) == 1:
        center = _clean_text(providers[0].get("seah_center_name")) or "a local support centre"
        if language_code == "ne":
            return (
                f"हामी तपाईंलाई {center} मा सम्पर्क गर्न सिफारिस गर्दछौं, जहाँ तपाईंलाई विशेष सहयोग उपलब्ध गराइनेछ।"
            )
        return (
            f"We recommend that you contact {center} where special support will be provided to you."
        )

    names = ", ".join(
        _clean_text(p.get("seah_center_name")) for p in providers if _clean_text(p.get("seah_center_name"))
    )
    if language_code == "ne":
        return (
            f"हामी तपाईंलाई {place} मा उपलब्ध निम्न SEAH सहयोग केन्द्रहरूमध्ये कुनै एकसँग सम्पर्क गर्न सिफारिस गर्दछौं: {names}।"
        )
    return (
        f"We recommend contacting one of the following support centres in {place}: {names}."
    )


def format_details_utterance(
    providers: List[Dict[str, Any]],
    language_code: str,
) -> str:
    if not providers:
        if language_code == "ne":
            return "यस क्षेत्रका लागि केन्द्र विवरण उपलब्ध छैन।"
        return "Centre details are not available for this area yet."

    blocks = [format_provider_details_block(row, language_code) for row in providers]
    return "\n\n".join(block for block in blocks if block)
