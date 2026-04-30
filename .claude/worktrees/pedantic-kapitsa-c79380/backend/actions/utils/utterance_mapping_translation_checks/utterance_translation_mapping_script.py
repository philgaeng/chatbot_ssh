import pandas as pd
from rapidfuzz import fuzz
import re
import sys
from datetime import datetime
import os

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_SCRIPT_DIR))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

NEW_MAPPINGS_DIR = os.path.join(_SCRIPT_DIR, "new_mappings")
PREVIOUS_TRANSLATIONS_DIR = os.path.join(_SCRIPT_DIR, "previous_translations")
MAPPING_OUTPUT_DIR = os.path.join(_SCRIPT_DIR, "mapping_with_latest_translations")


def _latest_file_by_mtime(directory: str, extension: str) -> str:
    """Return path to the file with latest modification time in directory (with given extension)."""
    if not os.path.isdir(directory):
        raise FileNotFoundError(f"Directory not found: {directory}")
    candidates = [
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.endswith(extension) and os.path.isfile(os.path.join(directory, f))
    ]
    if not candidates:
        raise FileNotFoundError(f"No {extension} files found in {directory}")
    return max(candidates, key=os.path.getmtime)


def _resolve_paths():
    """Resolve utterances file (latest CSV in new_mappings), translations file (latest xlsx in previous_translations), and output path."""
    utterances_path = _latest_file_by_mtime(NEW_MAPPINGS_DIR, ".csv")
    translations_path = _latest_file_by_mtime(PREVIOUS_TRANSLATIONS_DIR, ".xlsx")
    date_str = datetime.now().strftime("%y%m%d")
    os.makedirs(MAPPING_OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(MAPPING_OUTPUT_DIR, f"utterances_{date_str}_mapped_translation.xlsx")
    return utterances_path, translations_path, output_path


# =========================
# FILES (set at runtime in main() from _resolve_paths())
# =========================
UTTERANCES_FILE = None  # Set in main()
TRANSLATIONS_FILE = None  # Set in main()
OUTPUT_FILE = None  # Set in main()

# =========================
# COLUMN NAMES
# Update these if needed
# =========================
#input columns
ACTION_COL = "action"
EN_COL = "en"
NE_COL = "ne"

#output columns
NE_GENERATED_COL = "ne_generated"
NE_ALREADY_TRANSLATED_COL = "ne_already_translated"


# =========================
# MATCHING SETTINGS
# =========================
# Exact normalized text match is checked first.
# If not exact, look for best similar English utterance within the best-matching actions.
# If score >= MINOR_UPDATE_THRESHOLD, copy Nepali but keep status = "To update".
MINOR_UPDATE_THRESHOLD = 70

# Recommended range for utterance-level matching:
# 90 = stricter
# 88 = balanced
# 85 = more permissive

# Action-name fuzzy matching threshold (after normalization with "_" -> " ").
# Higher = stricter action grouping.
ACTION_MATCH_THRESHOLD = 50


def normalize_text(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = " ".join(text.split())
    return text


def normalize_action(value) -> str:
    """
    Normalize action names for fuzzy matching.
    Treats underscores as spaces before applying generic normalization.
    """
    if pd.isna(value):
        return ""
    # Replace underscores with spaces first, then apply the generic normalization.
    return normalize_text(str(value).replace("_", " "))

def similarity(a: str, b: str) -> float:
    """
    RapidFuzz similarity score from 0 to 100.
    token_sort_ratio helps when word order changes slightly.
    """
    if not a and not b:
        return 100.0
    if not a or not b:
        return 0.0

    # You can switch to fuzz.ratio(a, b) if you want stricter word-order matching.
    return fuzz.token_sort_ratio(a.lower(), b.lower())


def main():
    global UTTERANCES_FILE, TRANSLATIONS_FILE, OUTPUT_FILE
    UTTERANCES_FILE, TRANSLATIONS_FILE, OUTPUT_FILE = _resolve_paths()
    print(f"Utterances: {UTTERANCES_FILE}")
    print(f"Translations: {TRANSLATIONS_FILE}")
    print(f"Output: {OUTPUT_FILE}\n")

    # Load files
    utterances = pd.read_csv(UTTERANCES_FILE)
    translations = pd.read_excel(TRANSLATIONS_FILE)

    # Clean column names
    utterances.columns = utterances.columns.str.strip()
    translations.columns = translations.columns.str.strip()

    # Validate required columns
    required_utterance_cols = {ACTION_COL, EN_COL}
    required_translation_cols = {ACTION_COL, EN_COL, NE_COL}

    missing_u = required_utterance_cols - set(utterances.columns)
    missing_t = required_translation_cols - set(translations.columns)

    if missing_u:
        raise ValueError(f"Missing columns in utterances file: {sorted(missing_u)}")
    if missing_t:
        raise ValueError(f"Missing columns in translations file: {sorted(missing_t)}")

    # Normalize key columns
    utterances["_action_raw"] = utterances[ACTION_COL].fillna("").astype(str)
    utterances["_action_norm_action"] = utterances["_action_raw"].apply(normalize_action)
    utterances["_en_norm"] = utterances[EN_COL].apply(normalize_text)

    translations["_action_raw"] = translations[ACTION_COL].fillna("").astype(str)
    translations["_action_norm_action"] = translations["_action_raw"].apply(normalize_action)
    translations["_en_norm"] = translations[EN_COL].apply(normalize_text)
    translations["_ne_norm"] = translations[NE_COL].fillna("").astype(str)

    # Exact lookup keyed by (raw action name, normalized English)
    exact_lookup = {}
    for _, row in translations.iterrows():
        action_raw = row["_action_raw"]
        key = (action_raw, row["_en_norm"])
        if key not in exact_lookup or not exact_lookup[key]["nepali"]:
            exact_lookup[key] = {
                "nepali": row["_ne_norm"],
                "source_english": row[EN_COL],
            }

    # Group translation candidates by raw action
    by_action_raw = {}
    for _, row in translations.iterrows():
        action_raw = row["_action_raw"]
        by_action_raw.setdefault(action_raw, []).append({
            "action_norm_action": row["_action_norm_action"],
            "en_norm": row["_en_norm"],
            "en_original": row[EN_COL],
            "nepali": row["_ne_norm"],
        })

    # Unique translation actions for fuzzy action-name matching
    translation_actions = (
        translations[["_action_raw", "_action_norm_action"]]
        .drop_duplicates()
        .to_records(index=False)
    )

    # Result columns
    statuses = []
    nepali_values = []
    match_types = []
    match_scores = []
    match_source_english = []

    # Match each utterance
    for _, row in utterances.iterrows():
        # Raw and normalized action names for this utterance
        action_raw = str(row[ACTION_COL])
        action_norm_action = normalize_action(action_raw)
        en_norm = row["_en_norm"]

        # 1) Candidate actions: exact raw action-name match
        candidate_actions = set()
        if action_raw in by_action_raw:
            candidate_actions.add(action_raw)

        # 2) If none, fuzzy match action names (normalized with "_" -> " ")
        if not candidate_actions:
            for tr_action_raw, tr_action_norm in translation_actions:
                score = similarity(action_norm_action, tr_action_norm)
                if score >= ACTION_MATCH_THRESHOLD:
                    candidate_actions.add(tr_action_raw)

        # 3) Exact English match within candidate actions
        best_exact = None
        for cand_action in candidate_actions:
            key = (cand_action, en_norm)
            if key in exact_lookup:
                best_exact = exact_lookup[key]
                break

        if best_exact is not None:
            statuses.append("Done")
            nepali_values.append(best_exact["nepali"])
            match_types.append("Exact")
            match_scores.append(100.0)
            match_source_english.append(best_exact["source_english"])
            continue

        # 4) Best fuzzy English match across all candidate actions
        best_score = 0.0
        best_candidate = None

        for cand_action in candidate_actions:
            for candidate in by_action_raw.get(cand_action, []):
                score = similarity(en_norm, candidate["en_norm"])
                if score > best_score:
                    best_score = score
                    best_candidate = candidate

        if best_candidate and best_score >= MINOR_UPDATE_THRESHOLD:
            statuses.append("To update")
            nepali_values.append(best_candidate["nepali"])
            match_types.append("Minor update")
            match_scores.append(round(best_score, 2))
            match_source_english.append(best_candidate["en_original"])
        else:
            statuses.append("To update")
            nepali_values.append("")
            match_types.append("No match")
            match_scores.append(round(best_score, 2) if best_candidate else 0.0)
            match_source_english.append("")

    # Add output columns
    utterances["translation_status"] = statuses
    # nepali_values holds the mapped translations from the translations file
    utterances[NE_ALREADY_TRANSLATED_COL] = nepali_values
    # Preserve the original Nepali column from the utterances CSV
    utterances[NE_GENERATED_COL] = utterances[NE_COL]

    utterances["translation_match_type"] = match_types
    utterances["translation_match_score"] = match_scores

    # Drop helper columns
    utterances = utterances.drop(columns=["_action_raw", "_action_norm_action", "_en_norm"])

    # Save workbook
    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        utterances.to_excel(writer, sheet_name="All", index=False)
        utterances[utterances["translation_status"] == "To update"].to_excel(
            writer, sheet_name="To update", index=False
        )
        utterances[utterances["translation_status"] == "Done"].to_excel(
            writer, sheet_name="Done", index=False
        )

    # Console summary
    print(f"Created: {OUTPUT_FILE}\n")
    print("translation_status summary:")
    print(utterances["translation_status"].value_counts(dropna=False))
    print("\ntranslation_match_type summary:")
    print(utterances["translation_match_type"].value_counts(dropna=False))


if __name__ == "__main__":
    main()