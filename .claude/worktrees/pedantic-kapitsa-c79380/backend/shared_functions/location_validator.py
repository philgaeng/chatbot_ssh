# actions/helpers.py

import csv
import logging
from datetime import datetime
import json

import psycopg2
from psycopg2.extras import RealDictCursor
from rapidfuzz import process
from typing import Any, Dict, List, Optional, Tuple

from backend.config.constants import (
    CUT_OFF_FUZZY_MATCH_LOCATION,
    DB_CONFIG,
    DEFAULT_VALUES,
    DIC_LOCATION_WORDS,
    LOCATION_FOLDER_PATH,
)

DEFAULT_LANGUAGE_CODE = DEFAULT_VALUES["DEFAULT_LANGUAGE_CODE"]


def _norm_municipality(name: Optional[str]) -> str:
    if not name:
        return ""
    return str(name).title().replace(" Municipality", "").strip()


def _norm_district(name: Optional[str]) -> str:
    if not name:
        return ""
    return str(name).title().replace(" District", "").strip()


class ContactLocationValidator:
    """
    Validate and normalize location names using fuzzy matching.
    Uses cleaned JSON under dev-resources (location_dataset_*_cleaned.json) and
    municipality / GRM office rows from Postgres when seeded, else CSV fallbacks.
    """

    def __init__(self, json_path: Optional[str] = None) -> None:
        json_path = json_path or LOCATION_FOLDER_PATH
        self._json_base = str(json_path).rstrip("/\\")
        json_path_en = f"{self._json_base}_en_cleaned.json"
        json_path_ne = f"{self._json_base}_ne_cleaned.json"
        self.json_path_office_in_charge = f"{self._json_base}_GRM_list_office_in_charge.csv"
        self.logger = logging.getLogger(__name__)
        self.locations_both_language: Dict[str, Any] = {}
        with open(json_path_en, "r", encoding="utf-8") as file:
            self.locations_both_language["en"] = self._normalize_locations(json.load(file))
        with open(json_path_ne, "r", encoding="utf-8") as file:
            self.locations_both_language["ne"] = self._normalize_locations(json.load(file))

        self.municipality_villages: List[Dict[str, str]] = self._load_municipality_villages()
        self._office_rows: List[Dict[str, Any]] = self._load_office_rows()

    def _load_municipality_villages(self) -> List[Dict[str, str]]:
        try:
            conn = psycopg2.connect(
                host=DB_CONFIG["host"],
                database=DB_CONFIG["database"],
                user=DB_CONFIG["user"],
                password=DB_CONFIG["password"],
                port=DB_CONFIG["port"],
            )
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        "SELECT municipality, ward, village FROM reference_municipality_villages"
                    )
                    rows = cur.fetchall()
            finally:
                conn.close()
            if rows:
                return [
                    {
                        "municipality": _norm_municipality(r.get("municipality")),
                        "ward": str(r.get("ward", "")),
                        "village": (r.get("village") or "").strip(),
                    }
                    for r in rows
                ]
        except Exception as e:
            self.logger.warning("reference_municipality_villages unavailable (%s); using CSV", e)

        csv_path = f"{self._json_base}_municipality_villages.csv"
        out: List[Dict[str, str]] = []
        try:
            with open(csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    key_m = "Municipality" if "Municipality" in row else "municipality"
                    key_w = "Ward" if "Ward" in row else "ward"
                    key_v = "Village" if "Village" in row else "village"
                    out.append(
                        {
                            "municipality": _norm_municipality(row.get(key_m)),
                            "ward": str(row.get(key_w, "")).strip(),
                            "village": (row.get(key_v) or "").strip(),
                        }
                    )
        except FileNotFoundError:
            self.logger.error("Municipality/village CSV not found: %s", csv_path)
        return out

    def _load_office_rows(self) -> List[Dict[str, Any]]:
        try:
            conn = psycopg2.connect(
                host=DB_CONFIG["host"],
                database=DB_CONFIG["database"],
                user=DB_CONFIG["user"],
                password=DB_CONFIG["password"],
                port=DB_CONFIG["port"],
            )
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT office_id, office_name, office_address, office_email, office_pic_name,
                               office_phone, district, municipality
                        FROM reference_grm_office_in_charge
                        """
                    )
                    rows = cur.fetchall()
            finally:
                conn.close()
            if rows:
                normalized: List[Dict[str, Any]] = []
                for r in rows:
                    d = {k: (v if v is not None else "") for k, v in dict(r).items()}
                    d["municipality"] = _norm_municipality(d.get("municipality"))
                    d["district"] = _norm_district(d.get("district"))
                    normalized.append(d)
                return normalized
        except Exception as e:
            self.logger.warning("reference_grm_office_in_charge unavailable (%s); using CSV", e)

        path = self.json_path_office_in_charge
        rows: List[Dict[str, Any]] = []
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for raw in reader:
                    row = {k.lower().strip(): (v or "") for k, v in raw.items()}
                    row["municipality"] = _norm_municipality(row.get("municipality"))
                    row["district"] = _norm_district(row.get("district"))
                    rows.append(row)
        except FileNotFoundError:
            self.logger.error("GRM office CSV not found: %s", path)
        return rows

    def _validate_location(self, location_string, qr_province=None, qr_district=None):
        """Validate location from a single string input and QR defaults."""
        # Preprocess input and generate possible names
        processed_text = self._preprocess(location_string)
        print(f"######## LocationValidator: Preprocessed text: {processed_text}")
        possible_names = self._generate_possible_names(processed_text)
        
        
        #check if QR code is provided
        if qr_province and qr_district:
            # Try matching with QR data first
            province, district, municipality = self._match_with_qr_data(
                possible_names, qr_province, qr_district
            )
        
        else:
            province, district, municipality = self._match_from_string(possible_names)

        
        # Format and return the result
        result = self._format_result(province, district, municipality)
        print(f"######## LocationValidator: Result: {result}")
        return result

            
    def _initialize_constants(self, language_code: str = DEFAULT_LANGUAGE_CODE):
        self.language_code = language_code
        self.locations = self.locations_both_language[language_code]
        self.max_words = self._calculate_max_words()
        self.provinces = [p["name"].strip("Province").strip("प्रदेश") for p in self.locations]
            
    def _normalize_locations(self, locations):
        """Normalize all names in the locations data to lowercase."""
        for province in locations:
            province["name"] = province["name"].title().strip("Province").strip("प्रदेश")
            for district in province.get("districts", []):
                district["name"] = district["name"].title().strip("District")
                for municipality in district.get("municipalities", []):
                    municipality["name"] = municipality["name"].title()
        return locations

    def _calculate_max_words(self):
        """Calculate the maximum number of words in any municipality name."""
        max_words = 0
        for province in self.locations:
            for district in province.get("districts", []):
                for municipality in district.get("municipalities", []):
                    words = len(municipality["name"].split())
                    max_words = max(max_words, words)
        return max_words

    def _get_common_suffixes(self):
        """Return list of common suffixes to remove."""
        return [
            "province", "district", "municipality", 
            "rural municipality", "metropolitan", 
            "sub-metropolitan", "submetropolitan",
            "metropolitan city", "rural mun", "mun", 
            "महानगरपालिका" , "प्रदेश", "जिल्ला", "गाउँपालिका" , "नगरपालिका" 
            
        ]

    def _preprocess(self, text):
        """Normalize user input to lowercase and remove common suffixes."""
        if not text:
            return None
        
        text = text.title().strip()
        for suffix in self._get_common_suffixes():
            text = text.replace(suffix.title(), "").strip()
        return text

    def _generate_possible_names(self, text):
        """Generate possible location names from input text."""
        if not text:
            return []
        
        words = text.split()
        possible_names = []
        for i in range(len(words)):
            for j in range(i + 1, min(i + self.max_words + 1, len(words) + 1)):
                possible_names.append(" ".join(words[i:j]))
        return possible_names

    def _find_best_match(self, input_value, options, score_cutoff=CUT_OFF_FUZZY_MATCH_LOCATION):
        """Find the best match using fuzzy matching."""
        if not input_value or not options:
            return None
        
        input_value = self._preprocess(input_value)
        match = process.extractOne(input_value, options, score_cutoff= CUT_OFF_FUZZY_MATCH_LOCATION)
        if match:
            print(f"######## LocationValidator: Score: {match[1]}")
        return match[0] if match else None

    def _get_province_data(self, province_name):
        """Get province data by name."""
        return next(
            (p for p in self.locations
             if p["name"] == province_name),
            None
        )

    def _get_district_data(self, province_data, district_name):
        """Get district data by name within a province."""
        return next(
            (d for d in province_data.get("districts", []) 
             if d["name"] == district_name),
            None
        )
        
    def _get_district_names(self, province_name):
        """Get district names by province name.
        Extract and process district names from province data for a chosen province name.
        """
        province_data = [province for province in self.locations if 
                         province["name"] == province_name][0]
        if not province_data:
            return []
        return [d["name"] for d in province_data.get("districts", [])]
        
    def _get_municipality_names(self, district_data: dict) -> list:
        """
        Extract and process municipality names from district data.
        
        Args:
            district_data (dict): Dictionary containing municipality list
            
        Returns:
            list: Processed municipality names with common suffixes removed
        """
        
        remove_words = DIC_LOCATION_WORDS["municipality"][self.language_code]
        if not district_data or "municipalities" not in district_data:  
            return []
        
        
        municipality_names = []
        for mun in district_data.get("municipalities", []):
            if not mun or "name" not in mun:
                continue
            
            name = mun["name"].title()
            # Remove each word and clean up extra spaces
            for word in remove_words:
                name = name.replace(word, "")
            name = name.strip()
            
            if len(name) > 2:  # Only add non-empty names
                municipality_names.append(name)
            
        return municipality_names

    def _match_with_qr_data(self, possible_names, qr_province, qr_district):
        """Try to match location using QR-provided data."""
        print(f"######## LocationValidator: QR")
        province_list = self.locations
        province_names = [p["name"] for p in province_list]
        
        # Match province from QR data
        matched_province = self._find_best_match(qr_province, province_names) if qr_province else None
        if not matched_province:
            return None, None, None
            
        # Get province data and match district
        province_data = self._get_province_data(matched_province)
        district_names = [d["name"] for d in province_data.get("districts", [])]
        matched_district = self._find_best_match(qr_district, district_names) if qr_district else None
        
        if not matched_district:
            return matched_province, None, None
            
        # Get district data and match municipality
        district_data = self._get_district_data(province_data, matched_district)
        municipality_names = self._get_municipality_names(district_data)
        
        # Try to match municipality from possible names
        for possible_name in possible_names:
            if municipality_names:
                print(f"######## LocationValidator: Municipality names: {municipality_names}")
            else:
                print(f"######## LocationValidator: No municipality names")
            matched_municipality = self._find_best_match(possible_name, municipality_names)
            if matched_municipality:
                return matched_province, matched_district, matched_municipality
                
        return matched_province, matched_district, None

    def _match_from_string(self, possible_names):
        """Try to match location from possible names without QR data."""
        print(f"######## LocationValidator: String")
        for province in self.locations:
            for district in province.get("districts", []):
                municipality_names = self._get_municipality_names(district)
                print(f"######## LocationValidator: Municipality names: {municipality_names}")
                
                # Try municipality match first
                for possible_name in possible_names:
                    matched_municipality = self._find_best_match(possible_name, municipality_names)
                    if matched_municipality:
                        return province["name"], district["name"], matched_municipality
        
        # If no municipality match, try district match
        for province in self.locations:
            district_names = [d["name"] for d in province.get("districts", [])]
            for possible_name in possible_names:
                matched_district = self._find_best_match(possible_name, district_names)
                if matched_district:
                    return province["name"], matched_district, None
        
        # Finally, try province match
        for possible_name in possible_names:
            matched_province = self._find_best_match(possible_name, self.provinces)
            if matched_province:
                return matched_province, None, None
                
        return None, None, None

    def _format_result(self, province, district, municipality):
        """Format the validation result with appropriate error messages."""
        if not province:
            return {"error": "Could not determine province."}
        if not district:
            return {
                "province": province,
                "error": f"Could not determine district in {province}."
            }
        if not municipality:
            return {
                "province": province,
                "district": district,
                "error": f"Could not determine municipality in {district}."
            }
        return {
            "province": province,
            "district": district,
            "municipality": municipality
        }

    def check_province(self, input_text):
        """Check if the province name is valid."""
        # Finally, try province match
        possible_names = self._generate_possible_names(input_text)
        for possible_name in possible_names:
            matched_province = self._find_best_match(possible_name, self.provinces)
            if matched_province:
                return matched_province
        return None
    
    def check_district(self, input_text, province_name):
        """Check if the district name is valid."""
        # Finally, try province match
        possible_names = self._generate_possible_names(input_text)
        district_names = self._get_district_names(province_name)
        for possible_name in possible_names:
            matched_district = self._find_best_match(possible_name, district_names)
            if matched_district:
                return matched_district
        return None
    
    def validate_municipality_input(
            self,
            input_text: str,
            qr_province: str,
            qr_district: str,
        ) -> str:
            """Validate new municipality input."""
            
            validation_result = self._validate_location(
                input_text.title(), 
                qr_province, 
                qr_district
            )
            
            municipality = validation_result.get("municipality")
            
            if not municipality:
                return None
            
            municipality = municipality.title()
            print(f"✅ Municipality validated: {municipality}")
            
            return municipality


    def validate_village_input(
        self,
        input_text: str,
        qr_municipality: str,
    ) -> tuple[Optional[str], Optional[str]]:
        """Match village + ward for a municipality using fuzzy matching on seeded rows."""
        qr_municipality = _norm_municipality(qr_municipality)

        mun_rows = [r for r in self.municipality_villages if r["municipality"] == qr_municipality]
        village_names = [r["village"] for r in mun_rows if r.get("village")]

        matched_village = self._find_best_match(input_text, village_names)
        print(f"######## LocationValidator: Matched village: {matched_village}")
        if matched_village:
            for r in mun_rows:
                if r["village"] == matched_village:
                    return matched_village, str(r["ward"])
        return None, None

    def get_office_in_charge_info(
        self, municipality: Optional[str] = None, district: Optional[str] = None, province: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Return first matching GRM office row (dict with lowercase keys), or None."""
        if not district and not municipality:
            return None

        rows = self._office_rows
        if not rows:
            return None

        mun_key = _norm_municipality(municipality) if municipality else None
        dist_key = _norm_district(district) if district else None

        candidates: List[Dict[str, Any]]
        if mun_key and dist_key:
            candidates = [r for r in rows if r.get("municipality") == mun_key and r.get("district") == dist_key]
        elif dist_key:
            candidates = [r for r in rows if r.get("district") == dist_key]
        elif mun_key:
            candidates = [r for r in rows if r.get("municipality") == mun_key]
        else:
            return None

        if not candidates:
            return None
        return dict(candidates[0])
