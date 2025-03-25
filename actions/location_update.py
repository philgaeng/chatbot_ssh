import os
import json
import requests
from pathlib import Path
import pandas as pd
from typing import Dict, List, Any

# GitHub repository URL and paths
GITHUB_URL = "https://raw.githubusercontent.com/sagautam5/local-states-nepal/master/dataset"
BASE_DIR = Path.cwd()
RESOURCES_DIR = BASE_DIR / "resources"
LOCATION_FILE = RESOURCES_DIR / "nepal_location_en_ne.json"

# Dataset paths
DATASET_DIR = BASE_DIR / "dataset"
PROVINCES_EN = DATASET_DIR / "provinces" / "en"
PROVINCES_NE = DATASET_DIR / "provinces" / "np"
DISTRICTS_EN = DATASET_DIR / "districts" / "en"
DISTRICTS_NE = DATASET_DIR / "districts" / "np"
MUNICIPALITIES_EN = DATASET_DIR / "municipalities" / "en"
MUNICIPALITIES_NE = DATASET_DIR / "municipalities" / "np"

def setup_dataset_directories():
    """Create the dataset directory structure."""
    directories = [
        DATASET_DIR / "provinces" / "en",
        DATASET_DIR / "provinces" / "np",
        DATASET_DIR / "districts" / "en",
        DATASET_DIR / "districts" / "np",
        DATASET_DIR / "municipalities" / "en",
        DATASET_DIR / "municipalities" / "np"
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

def download_dataset_file(file_path: Path, relative_url: str):
    """Download a dataset file from GitHub."""
    url = f"{GITHUB_URL}/{relative_url}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"Downloaded: {file_path}")
    except Exception as e:
        print(f"Error downloading {url}: {e}")

def setup_dataset_files():
    """Download all dataset files."""
    files_to_download = [
        (PROVINCES_EN, "provinces/en/provinces.json"),
        (PROVINCES_NE, "provinces/np/provinces.json"),
        (DISTRICTS_EN, "districts/en/districts.json"),
        (DISTRICTS_NE, "districts/np/districts.json"),
        (MUNICIPALITIES_EN, "municipalities/en/municipalities.json"),
        (MUNICIPALITIES_NE, "municipalities/np/municipalities.json")
    ]
    
    for file_path, relative_url in files_to_download:
        download_dataset_file(file_path, relative_url)

def load_json_file(file_path: Path) -> List[Dict[str, Any]]:
    """Load data from a JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return []
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {file_path}")
        return []

def create_combined_location_data() -> Dict[str, Any]:
    """Create combined English-Nepali location data structure."""
    # Load all data files
    provinces_en = load_json_file(PROVINCES_EN)
    provinces_ne = load_json_file(PROVINCES_NE)
    districts_en = load_json_file(DISTRICTS_EN)
    districts_ne = load_json_file(DISTRICTS_NE)
    municipalities_en = load_json_file(MUNICIPALITIES_EN)
    municipalities_ne = load_json_file(MUNICIPALITIES_NE)

    # Create province lookup dictionaries
    provinces_en_dict = {p['id']: p for p in provinces_en}
    provinces_ne_dict = {p['id']: p for p in provinces_ne}

    # Create district lookup dictionaries
    districts_en_dict = {d['id']: d for d in districts_en}
    districts_ne_dict = {d['id']: d for d in districts_ne}

    # Create municipality lookup dictionaries
    municipalities_en_dict = {m['id']: m for m in municipalities_en}
    municipalities_ne_dict = {m['id']: m for m in municipalities_ne}

    # Create the combined structure
    combined_data = {"provinceList": []}

    # Process provinces
    for province_id in sorted(set(provinces_en_dict.keys()) | set(provinces_ne_dict.keys())):
        province_data = {
            "id": province_id,
            "en": provinces_en_dict.get(province_id, {}).get('name', ''),
            "ne": provinces_ne_dict.get(province_id, {}).get('name', ''),
            "districtList": []
        }

        # Process districts for this province
        province_districts_en = [d for d in districts_en if d['province_id'] == province_id]
        province_districts_ne = [d for d in districts_ne if d['province_id'] == province_id]

        for district_id in sorted(set(d['id'] for d in province_districts_en) | set(d['id'] for d in province_districts_ne)):
            district_data = {
                "id": district_id,
                "en": districts_en_dict.get(district_id, {}).get('name', ''),
                "ne": districts_ne_dict.get(district_id, {}).get('name', ''),
                "municipalityList": []
            }

            # Process municipalities for this district
            district_municipalities_en = [m for m in municipalities_en if m['district_id'] == district_id]
            district_municipalities_ne = [m for m in municipalities_ne if m['district_id'] == district_id]

            for municipality_id in sorted(set(m['id'] for m in district_municipalities_en) | set(m['id'] for m in district_municipalities_ne)):
                municipality_data = {
                    "id": municipality_id,
                    "en": municipalities_en_dict.get(municipality_id, {}).get('name', ''),
                    "ne": municipalities_ne_dict.get(municipality_id, {}).get('name', '')
                }
                district_data["municipalityList"].append(municipality_data)

            province_data["districtList"].append(district_data)

        combined_data["provinceList"].append(province_data)

    return combined_data

def save_combined_location_data(data: Dict[str, Any]) -> bool:
    """Save the combined location data to the JSON file."""
    try:
        with open(LOCATION_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving location data: {e}")
        return False

def update_province_data(province_id: int, province_data: Dict[str, Any]) -> bool:
    """Update data for a specific province."""
    data = load_json_file(LOCATION_FILE)
    
    if not data or 'provinceList' not in data:
        print("Invalid location data structure")
        return False
    
    # Find and update the province
    for province in data['provinceList']:
        if province['id'] == province_id:
            province.update(province_data)
            return save_combined_location_data(data)
    
    print(f"Province with ID {province_id} not found")
    return False

def update_district_data(province_id: int, district_id: int, district_data: Dict[str, Any]) -> bool:
    """Update data for a specific district within a province."""
    data = load_json_file(LOCATION_FILE)
    
    if not data or 'provinceList' not in data:
        print("Invalid location data structure")
        return False
    
    # Find the province and update the district
    for province in data['provinceList']:
        if province['id'] == province_id:
            if 'districtList' not in province:
                province['districtList'] = []
            
            for district in province['districtList']:
                if district['id'] == district_id:
                    district.update(district_data)
                    return save_combined_location_data(data)
            
            print(f"District with ID {district_id} not found in province {province_id}")
            return False
    
    print(f"Province with ID {province_id} not found")
    return False

def update_municipality_data(province_id: int, district_id: int, municipality_id: int, municipality_data: Dict[str, Any]) -> bool:
    """Update data for a specific municipality within a district."""
    data = load_json_file(LOCATION_FILE)
    
    if not data or 'provinceList' not in data:
        print("Invalid location data structure")
        return False
    
    # Find the province, district, and update the municipality
    for province in data['provinceList']:
        if province['id'] == province_id:
            if 'districtList' not in province:
                print(f"No districts found in province {province_id}")
                return False
            
            for district in province['districtList']:
                if district['id'] == district_id:
                    if 'municipalityList' not in district:
                        district['municipalityList'] = []
                    
                    for municipality in district['municipalityList']:
                        if municipality['id'] == municipality_id:
                            municipality.update(municipality_data)
                            return save_combined_location_data(data)
                    
                    print(f"Municipality with ID {municipality_id} not found in district {district_id}")
                    return False
            
            print(f"District with ID {district_id} not found in province {province_id}")
            return False
    
    print(f"Province with ID {province_id} not found")
    return False

if __name__ == "__main__":
    # Setup dataset structure and download files
    print("Setting up dataset directories...")
    setup_dataset_directories()
    print("Downloading dataset files...")
    setup_dataset_files()
    
    # Create the initial combined location data
    print("Creating combined location data...")
    combined_data = create_combined_location_data()
    # print("Saving combined location data...")
    # save_combined_location_data(combined_data)
    
    # print("Done!")
    
    # # Example usage for updates
    # province_data = {
    #     "id": 1,
    #     "en": "Koshi Province",
    #     "ne": "कोशी प्रदेश"
    # }
    # update_province_data(1, province_data)
    
    # district_data = {
    #     "id": 1,
    #     "en": "Taplejung",
    #     "ne": "ताप्लेजुङ"
    # }
    # update_district_data(1, 1, district_data)
    
    # municipality_data = {
    #     "id": 1,
    #     "en": "Fattanglung Rural Municipality",
    #     "ne": "फत्ताङलुङ गाउँपालिका"
    # }
    # update_municipality_data(1, 1, 1, municipality_data) 