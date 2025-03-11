import re
import fileinput
from typing import Optional

def update_constants_file(province: str, district: str, constants_file: str = "actions/constants.py") -> bool:
    """
    Update the QR_PROVINCE and QR_DISTRICT values in constants.py
    
    Args:
        province: Province name from URL
        district: District name from URL
        constants_file: Path to constants.py file
    
    Returns:
        bool: True if update was successful, False otherwise
    """
    try:
        with fileinput.input(constants_file, inplace=True) as file:
            for line in file:
                if line.strip().startswith('QR_PROVINCE ='):
                    print(f'QR_PROVINCE = "{province.upper()}"')
                elif line.strip().startswith('QR_DISTRICT ='):
                    print(f'QR_DISTRICT = "{district}"')
                else:
                    print(line, end='')
        return True
    except Exception as e:
        print(f"Error updating constants.py: {e}")
        return False