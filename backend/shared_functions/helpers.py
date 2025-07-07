# actions/helpers.py

import os  # For file path operations
import logging  # For logging errors
import csv  # For reading CSV files 
from rasa_sdk import Tracker
from datetime import datetime
import json  # For loading JSON files
from rapidfuzz import process
from typing import Optional, Dict, Any, Tuple, List
import re
from icecream import ic

# Direct access to constants
from ..config.constants import (    
    LOCATION_FOLDER_PATH,
    CUT_OFF_FUZZY_MATCH_LOCATION,
    USE_QR_CODE,
    DIC_LOCATION_WORDS,
    EMAIL_PROVIDERS_NEPAL_LIST
)

# Set up logging
logger = logging.getLogger(__name__)



class ContactLocationValidator:
    """
    Validate and normalize location names using fuzzy matching.
    Use the cleaned json file for validation located in the resources/location_dataset folder.
    The json file should be named as <language_code>_cleaned.json
    """
    def __init__(self, 
                 tracker = Tracker, 
                 json_path=LOCATION_FOLDER_PATH):
    
        json_path_en = f"{json_path}_en_cleaned.json"
        json_path_ne = f"{json_path}_ne_cleaned.json"
        self.locations_both_language = dict()
        ic(json_path)
        if USE_QR_CODE:
            with open(json_path_en, "r") as file:
                self.locations_both_language["en"] = self._normalize_locations(json.load(file))
            with open(json_path_ne, "r") as file:
                self.locations_both_language["ne"] = self._normalize_locations(json.load(file))

            
    def _initialize_constants(self, tracker):
        language_code = 'en'
        if tracker and isinstance(tracker, Tracker) and "language_code" in tracker.slots:
            language_temp = tracker.get_slot("language_code")
            if language_temp:
                language_code = language_temp
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
        ic(province_name)
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

    def _check_province(self, input_text):
        """Check if the province name is valid."""
        # Finally, try province match
        possible_names = self._generate_possible_names(input_text)
        ic(self.provinces)
        for possible_name in possible_names:
            matched_province = self._find_best_match(possible_name, self.provinces)
            if matched_province:
                return matched_province
        return None
    
    def _check_district(self, input_text, province_name):
        """Check if the district name is valid."""
        # Finally, try province match
        possible_names = self._generate_possible_names(input_text)
        district_names = self._get_district_names(province_name)
        for possible_name in possible_names:
            matched_district = self._find_best_match(possible_name, district_names)
            if matched_district:
                return matched_district
        return None
    
    def _validate_municipality_input(
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

    def _validate_string_length(self, text: str, min_length: int = 2) -> bool:
        """Validate if the string meets minimum length requirement."""
        return bool(text and len(text.strip()) >= min_length)
    
    def _is_valid_phone(self, phone: str) -> bool:
        """Check if the phone number is valid."""
        # Add your phone validation logic here
        #Nepalese logic
        # 1. Must be 10 digits and start with 9
        if re.match(r'^9\d{9}$', phone):
            return True
        #Matching PH number format for testing
        if re.match(r'^09\d{9}$', phone) or re.match(r'^639\d{8}$', phone):
            return True
        return False
    
    def _email_extract_from_text(self, text: str) -> Optional[str]:
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        email_match = re.search(email_pattern, text)
        return email_match.group(0) if email_match else None

    def _email_is_valid_nepal_domain(self, email: str) -> bool:
        email_domain = email.split('@')[1].lower()
        return email_domain in EMAIL_PROVIDERS_NEPAL_LIST or email_domain.endswith('.com.np')

    # ✅ Validate user contact email
    def _email_is_valid_format(self, email: str) -> bool:
        """Check if email follows basic format requirements."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    
    