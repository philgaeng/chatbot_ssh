# actions/helpers.py

import os  # For file path operations
import logging  # For logging errors
import csv  # For reading CSV files
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)

# Default file paths
LOOKUP_FILE_PATH = "/home/ubuntu/nepal_chatbot/data/lookup_tables/list_category.txt"
DEFAULT_CSV_PATH = "/home/ubuntu/nepal_chatbot/resources/grievances_categorization_v1.csv"
# File to store the last grievance ID
COUNTER_FILE = "/home/ubuntu/nepal_chatbot/data/grievance_counter.txt"

def load_categories_from_lookup():
    """Loads categories from the lookup table file (list_category.txt)."""
    try:
        with open(LOOKUP_FILE_PATH, "r", encoding="utf-8") as file:
            category_list = [line.strip() for line in file if line.strip()]  # Remove empty lines
        return category_list
    except FileNotFoundError:
        logger.error(f"⚠ Lookup file not found: {LOOKUP_FILE_PATH}")
        return []
    except Exception as e:
        logger.error(f"⚠ Error loading categories from lookup table: {e}")
        return []  # Return empty list on failure

def load_classification_data(csv_path=DEFAULT_CSV_PATH):
    """
    Loads grievance classification data from a CSV file, updates the lookup table,
    and returns a unique sorted list of categories.
    """
    categories = []

    try:
        with open(csv_path, "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Normalize case and format as "Classification - Grievance Name"
                category = f"- {row['Classification'].title()} ; {row['Generic Grievance Name'].title()}"
                categories.append(category)

        # Remove duplicates and sort
        unique_categories = sorted(set(categories))

        # Update lookup table
        update_lookup_table(unique_categories)

        return unique_categories

    except FileNotFoundError:
        logger.error(f"⚠ Classification CSV file not found: {csv_path}")
        return []
    except Exception as e:
        logger.error(f"⚠ Error loading classification data: {e}")
        return []

def update_lookup_table(categories):
    """Writes the latest category list to the lookup table file (list_category.txt)."""
    try:
        with open(LOOKUP_FILE_PATH, "w", encoding="utf-8") as file:
            for category in categories:
                file.write(f"{category}\n")
        logger.info("✅ Lookup table successfully updated.")
    except Exception as e:
        logger.error(f"⚠ Error updating lookup table: {e}")

def get_next_grievance_number():
    # Get today's date in YYmmDD format
    today_date = datetime.now().strftime("%y%m%d")

    # Initialize grievance ID if the file doesn't exist or is empty
    if not os.path.exists(COUNTER_FILE) or os.stat(COUNTER_FILE).st_size == 0:
        initial_id = f"GR-{today_date}-0001"
        with open(COUNTER_FILE, "w") as f:
            f.write(initial_id)
        return initial_id

    # Read the last grievance ID
    with open(COUNTER_FILE, "r") as f:
        last_grievance_id = f.read().strip()

    try:
        # Validate format and parse the date and counter from the last grievance ID
        if not last_grievance_id.startswith("GR-"):
            raise ValueError(f"Invalid format in counter file: {last_grievance_id}")
        
        parts = last_grievance_id.split("-")
        if len(parts) != 3:
            raise ValueError(f"Invalid format in counter file: {last_grievance_id}")

        _, last_date, last_counter = parts
        last_counter_number = int(last_counter)

        # If the date is different from today, reset the counter
        if last_date != today_date:
            new_grievance_id = f"GR-{today_date}-0001"
        else:
            # Increment the counter if the date is the same
            new_counter_number = last_counter_number + 1
            new_grievance_id = f"GR-{today_date}-{new_counter_number:04d}"

    except Exception as e:
        # Handle any parsing error by resetting the counter
        print(f"Error parsing grievance ID: {e}. Resetting counter.")
        new_grievance_id = f"GR-{today_date}-0001"

    # Save the new grievance ID to the file
    with open(COUNTER_FILE, "w") as f:
        f.write(new_grievance_id)

    return new_grievance_id