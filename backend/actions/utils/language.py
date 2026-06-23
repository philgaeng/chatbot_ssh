"""Language detection, skip-instruction matching, and category label helpers."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from rapidfuzz import fuzz

from backend.config.constants import CLASSIFICATION_DATA
from backend.config.database_constants import GRIEVANCE_STATUS_DICT

SKIP_WORDS_DIC: Dict[str, Dict[str, Any]] = {
    "en": {
        "keywords": ["skip", "pass", "next", "skip it", "pass this"],
        "ignore_list": ["access"],
        "fuzzy_threshold_1": 98,
        "fuzzy_threshold_2": 75,
    },
    "ne": {
        "keywords": [
            "छोड्नुहोस्",
            "छोड",
            "अर्को",
            "छोडी दिनुस",
            "छोडिदिनुस",
            "छोड्ने",
            "छोड्दिनु",
            "पछि",
            "पछाडी जाऊ",
            "स्किप",
            "पास",
            "नेक्स्ट",
            "यसलाई छोड्नुहोस्",
            "यो चाहिएन",
        ],
        "fuzzy_threshold_1": 98,
        "fuzzy_threshold_2": 75,
    },
    "hi": {
        "keywords": ["छोड़ें", "छोड़ दो", "अगला", "आगे बढ़ें"],
        "fuzzy_threshold_1": 98,
        "fuzzy_threshold_2": 75,
    },
}

CHAR_PATTERNS = {
    "ne": re.compile(r"[\u0900-\u097F]"),
    "en": re.compile(r"[a-zA-Z]"),
}


def detect_language(text: str) -> str:
    """Detect language from character patterns ('en', 'ne', …)."""
    if not text:
        return "en"
    text = text.strip()
    counts = {lang: len(pattern.findall(text)) for lang, pattern in CHAR_PATTERNS.items()}
    if not counts or max(counts.values()) == 0:
        return "en"
    return max(counts.items(), key=lambda x: x[1])[0]


def fuzzy_match_score(text: str, target_words: List[str]) -> Tuple[float, str]:
    """Best fuzzy ratio score and matched word."""
    text = text.lower().strip() if text else ""
    best_score = 0.0
    best_match = ""
    for word in target_words:
        score = fuzz.ratio(text, word.lower())
        if score > best_score:
            best_score = score
            best_match = word
    return best_score, best_match


def is_skip_instruction(input_text: str) -> Tuple[bool, bool, str]:
    """Return (is_skip, needs_confirmation, matched_word)."""
    try:
        if input_text.startswith("/"):
            return False, False, ""

        input_text = input_text.lower().strip()
        lang = detect_language(input_text)
        lang_cfg = SKIP_WORDS_DIC.get(lang, SKIP_WORDS_DIC["en"])
        skip_words = lang_cfg.get("keywords")
        fuzzy_threshold_1 = lang_cfg.get("fuzzy_threshold_1")
        fuzzy_threshold_2 = lang_cfg.get("fuzzy_threshold_2")
        ignore_words = lang_cfg.get("ignore_list", [])

        best_score = 0
        best_match = ""
        for input_word in input_text.split():
            if not ignore_words or input_word not in ignore_words:
                score, match = fuzzy_match_score(input_word, skip_words)
                if score > best_score:
                    best_score = score
                    best_match = input_word

        if best_score >= fuzzy_threshold_1:
            return True, False, best_match
        if best_score >= fuzzy_threshold_2:
            return True, True, best_match
        return False, False, ""
    except Exception:  # pylint: disable=broad-except
        return False, False, ""


def validate_string_length(text: str, min_length: int = 2) -> bool:
    if not text or not isinstance(text, str):
        return False
    return len(text.strip()) > min_length


def is_valid_email(email: str) -> bool:
    if not email:
        return False
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def categories_in_local_language(categories: List[str], language_code: str) -> List[str]:
    if language_code == "en":
        return categories
    categories_local = []
    key_local_1 = f"generic_grievance_name_{language_code}"
    key_local_2 = f"classification_{language_code}"
    for category in categories:
        category = category.split(" - ")[1].strip()
        category_data = CLASSIFICATION_DATA.get(category, {})
        category_name_local_1 = category_data.get(key_local_1, category)
        category_name_local_2 = category_data.get(key_local_2, category)
        categories_local.append(f"{category_name_local_2} - {category_name_local_1}")
    return categories_local


def categories_in_english(categories: List[str], language_code: str) -> List[str]:
    if not categories:
        return []
    if language_code == "en":
        return list(categories)

    key_local_1 = f"classification_{language_code}"
    key_local_2 = f"generic_grievance_name_{language_code}"
    categories_en: List[str] = []
    for category in categories:
        if not category or not str(category).strip():
            continue
        cat = str(category).strip()
        matched = False
        for item in CLASSIFICATION_DATA.values():
            local_classification = item.get(key_local_1, "")
            local_grievance_name = item.get(key_local_2, "")
            local_category = f"{local_classification} - {local_grievance_name}"
            english_classification = item.get("classification", "")
            english_grievance_name = item.get("generic_grievance_name", "")
            english_category = f"{english_classification} - {english_grievance_name}"
            if cat in (local_category, english_category):
                categories_en.append(english_category)
                matched = True
                break
        if not matched:
            # UI may show English taxonomy labels even when language_code is ne.
            categories_en.append(cat)
    return categories_en


def status_and_description_in_language(status: str, language_code: str) -> str:
    row = GRIEVANCE_STATUS_DICT[status]
    return row[f"name_{language_code}"] + " - " + row[f"description_{language_code}"]
