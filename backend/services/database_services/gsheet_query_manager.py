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
        """Get grievances for Google Sheets monitoring with optional filters and user-based access control"""
        
        # Get user's municipality access
        municipality_filter = self._get_user_municipality_filter(username)
        
        query = """
            WITH latest_status AS (
                SELECT DISTINCT ON (grievance_id) 
                    grievance_id,
                    status_code as grievance_status,
                    created_at as grievance_status_update_date,
                    notes
                FROM grievance_status_history
                ORDER BY grievance_id, created_at DESC
            )
            SELECT 
                g.grievance_id,
                g.complainant_id,
                c.complainant_full_name,
                c.complainant_phone,
                c.complainant_municipality,
                c.complainant_village,
                c.complainant_address,
                g.grievance_description,
                g.grievance_summary,
                g.grievance_categories,
                g.grievance_sensitive_issue,
                g.grievance_high_priority,
                g.grievance_creation_date,
                g.grievance_timeline,
                ls.grievance_status as status,
                ls.grievance_status_update_date,
                ls.notes
            FROM complainants c
            INNER JOIN grievances g ON c.complainant_id = g.complainant_id
            LEFT JOIN latest_status ls ON g.grievance_id = ls.grievance_id
            WHERE g.grievance_description IS NOT NULL
        """
        params = []

        # Apply municipality filter based on user access
        if municipality_filter:
            validated_municipalities = self._validate_municipality_names(municipality_filter)
            if validated_municipalities:
                query += self._get_municipality_filter_clause(validated_municipalities)
                # Add % wildcards for ILIKE matching
                ilike_params = [f"%{municipality}%" for municipality in validated_municipalities]
                params.extend(ilike_params)

        if status:
            query += " AND ls.grievance_status = %s"
            params.append(status)
        if start_date:
            query += " AND g.grievance_creation_date >= %s"
            params.append(start_date)
        if end_date:
            query += " AND g.grievance_creation_date <= %s"
            params.append(end_date)

        query += " ORDER BY g.grievance_creation_date DESC, ls.grievance_status_update_date DESC"

        try:
            return self._execute_query_with_selective_decryption(query, params)
        except Exception as e:
            self.logger.error(f"Error fetching grievances for GSheet: {str(e)}")
            raise Exception(f"Failed to fetch grievances: {str(e)}")
    
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
            return " AND c.complainant_municipality ILIKE %s"
        else:
            conditions = []
            for _ in validated_municipalities:
                conditions.append("c.complainant_municipality ILIKE %s")
            return f" AND ({' OR '.join(conditions)})"

# --- End moved classes --- 