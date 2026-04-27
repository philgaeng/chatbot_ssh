import uuid
import logging
import os
from typing import Dict, List, Optional, Any
import traceback
from icecream import ic
from .base_manager import BaseDatabaseManager
from rapidfuzz import process
from backend.shared_functions.helpers_repo import helpers_repo


class GSheetDbManager(BaseDatabaseManager):
    
    def get_grievances_for_gsheet(self, status: Optional[str] = None, 
                                 start_date: Optional[str] = None, 
                                 end_date: Optional[str] = None,
                                 username: Optional[str] = None) -> List[Dict]:
        """Deprecated: Google Sheets monitoring is retired in favor of ticketing UI."""
        msg = (
            "Google Sheets monitoring is deprecated. "
            "Use the standalone ticketing system instead."
        )
        self.logger.warning(msg)
        raise RuntimeError(msg)
    
    def _get_user_municipality_filter(self, username: Optional[str]) -> Optional[List[str]]:
        """Get municipality filter based on user access level"""
        if not username:
            # No username provided - return all data (for backward compatibility)
            return None
        
        try:
            # Check if user is admin (pd_office or adb_hq)
            if username in ['pd_office', 'adb_hq']:
                self.logger.info(f"Admin user {username} - returning all municipalities")
                return None
            
            # For office users, get all municipalities they have access to
            query = """
                SELECT DISTINCT omw.municipality 
                FROM office_municipality_ward omw
                WHERE omw.office_id = %s
                ORDER BY omw.municipality
            """
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (username,))
                    results = cur.fetchall()
                    
                    if results:
                        municipalities = [result[0] for result in results]
                        self.logger.info(f"User {username} - raw municipalities from CSV mapping: {municipalities}")
                        return municipalities
                    else:
                        self.logger.warning(f"User {username} not found in office_municipality_ward - no filter applied")
                        return None
                        
        except Exception as e:
            self.logger.error(f"Error getting municipality filter for user {username}: {str(e)}")
            # On error, return None to allow all data (fail-safe)
            return None
    
    def _validate_municipality_names(self, municipality_filter: List[str]) -> List[str]:
        """Validate municipality names using the same logic used when storing data."""
        validated_municipalities = []
        for municipality in municipality_filter:
            try:
                validation_result = helpers_repo.validate_municipality_input(municipality)
                if validation_result and 'municipality' in validation_result:
                    validated_municipalities.append(validation_result['municipality'])
                    self.logger.debug(f"Municipality '{municipality}' -> validated as '{validation_result['municipality']}'")
                else:
                    validated_municipalities.append(municipality)
                    self.logger.warning(f"Validation failed for municipality '{municipality}', using original")
            except Exception as e:
                # For now, use ILIKE matching instead of exact validation due to validation function issues
                self.logger.warning(f"Validation error for municipality '{municipality}': {str(e)}, using ILIKE matching")
                validated_municipalities.append(municipality)
        
        validated_municipalities = list(set(validated_municipalities))  # Remove duplicates
        self.logger.info(f"Municipalities for filtering (with ILIKE matching): {validated_municipalities}")
        return validated_municipalities
    
    def _get_municipality_filter_clause(self, validated_municipalities: List[str]) -> str:
        """Get municipality filter SQL clause using ILIKE for partial matching."""
        if len(validated_municipalities) == 1:
            return " AND COALESCE(c.level_3_name, c.complainant_municipality) ILIKE %s"
        else:
            conditions = []
            for _ in validated_municipalities:
                conditions.append("COALESCE(c.level_3_name, c.complainant_municipality) ILIKE %s")
            return f" AND ({' OR '.join(conditions)})"

# --- End moved classes --- 