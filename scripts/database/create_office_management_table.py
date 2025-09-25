#!/usr/bin/env python3
"""
Script to create office management table and populate it with office data
"""

import sys
import os
import pandas as pd
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.services.database_services.postgres_services import db_manager
import logging

def create_office_management_table():
    """Create office_management and office_municipality_ward tables and populate with CSV data"""
    
    logger = logging.getLogger(__name__)
    
    try:
        # Create the office_management table
        create_office_table_query = """
        CREATE TABLE IF NOT EXISTS office_management (
            office_id TEXT PRIMARY KEY,
            office_name TEXT NOT NULL,
            office_address TEXT,
            office_email TEXT,
            office_pic_name TEXT,
            office_phone TEXT,
            district TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        # Create the office_municipality_ward junction table
        create_junction_table_query = """
        CREATE TABLE IF NOT EXISTS office_municipality_ward (
            id SERIAL PRIMARY KEY,
            office_id TEXT NOT NULL,
            municipality TEXT NOT NULL,
            ward INTEGER NOT NULL,
            village TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (office_id) REFERENCES office_management(office_id) ON DELETE CASCADE,
            UNIQUE(office_id, municipality, ward, village)
        )
        """
        
        # Use a single transaction for table creation and data insertion
        with db_manager.transaction() as conn:
            with conn.cursor() as cur:
                # Create tables
                cur.execute(create_office_table_query)
                logger.info("Created office_management table successfully")
                cur.execute(create_junction_table_query)
                logger.info("Created office_municipality_ward table successfully")
                
                # Read office management CSV data
                office_csv_path = project_root / "backend" / "resources" / "location_dataset_GRM_list_office_in_charge.csv"
                office_df = pd.read_csv(office_csv_path)
                
                # Clean and prepare office data
                office_df.columns = office_df.columns.str.lower()
                office_df['district'] = office_df['district'].str.title().str.replace(' District', '').str.strip()
                
                # Insert office data into database
                insert_office_query = """
                INSERT INTO office_management 
                (office_id, office_name, office_address, office_email, office_pic_name, office_phone, district)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (office_id) DO UPDATE SET
                    office_name = EXCLUDED.office_name,
                    office_address = EXCLUDED.office_address,
                    office_email = EXCLUDED.office_email,
                    office_pic_name = EXCLUDED.office_pic_name,
                    office_phone = EXCLUDED.office_phone,
                    district = EXCLUDED.district,
                    updated_at = CURRENT_TIMESTAMP
                """
                
                for _, row in office_df.iterrows():
                    cur.execute(insert_office_query, (
                        row['office_id'],
                        row['office_name'],
                        row['office_address'],
                        row['office_email'],
                        row['office_pic_name'],
                        row['office_phone'],
                        row['district']
                    ))
                logger.info(f"Inserted/updated {len(office_df)} office records")
        
                # Read office-municipality mapping CSV data
                office_municipality_csv_path = project_root / "backend" / "resources" / "location_dataset_office_municipality_ward.csv"
                office_municipality_df = pd.read_csv(office_municipality_csv_path)
                
                # Clean and prepare office-municipality data
                office_municipality_df.columns = office_municipality_df.columns.str.lower()
                office_municipality_df['municipality'] = office_municipality_df['municipality'].str.title().str.strip()
                
                logger.info(f"Office-municipality mapping data: {len(office_municipality_df)} records")
                logger.info(f"Sample data: {office_municipality_df.head().to_dict('records')}")
                
                # Insert office-municipality data into junction table
                insert_junction_query = """
                INSERT INTO office_municipality_ward 
                (office_id, municipality, ward, village)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (office_id, municipality, ward, village) DO NOTHING
                """
                
                junction_count = 0
                for _, row in office_municipality_df.iterrows():
                    office_id = row['office_name']  # office_name column contains the office_id
                    municipality = row['municipality']
                    ward = row['ward'] if pd.notna(row['ward']) and row['ward'] != '' else None
                    village = None  # No village data in this CSV
                    
                    cur.execute(insert_junction_query, (
                        office_id,
                        municipality,
                        ward,
                        village
                    ))
                    junction_count += 1
                    logger.debug(f"Mapped {office_id} to {municipality} (ward: {ward})")
                
                logger.info(f"Inserted/updated {junction_count} office-municipality records")
        
        # Create user accounts for each office
        create_user_accounts(office_df)
        
        logger.info("Office management setup completed successfully")
        
    except Exception as e:
        logger.error(f"Error setting up office management: {str(e)}")
        raise

def create_user_accounts(office_df):
    """Create user accounts for office access"""
    
    # Define special users
    special_users = [
        {'office_id': 'pd_office', 'office_name': 'PD Office'},
        {'office_id': 'adb_hq', 'office_name': 'ADB Headquarters'}
    ]
    
    # Combine office data with special users
    all_users = []
    
    # Add office users
    for _, row in office_df.iterrows():
        all_users.append({
            'office_id': row['Office_id'],  # Use capital O from CSV
            'office_name': row['Office_name']  # Use capital O from CSV
        })
    
    # Add special users
    all_users.extend(special_users)
    
    # Create user accounts
    insert_user_query = """
    INSERT INTO office_user 
    (id, us_unique_id, user_name, user_login, user_password, user_role, user_status, user_office_id)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (id) DO UPDATE SET
        user_name = EXCLUDED.user_name,
        user_password = EXCLUDED.user_password,
        user_role = EXCLUDED.user_role,
        user_status = EXCLUDED.user_status,
        user_office_id = EXCLUDED.user_office_id
    """
    
    with db_manager.transaction() as conn:
        with conn.cursor() as cur:
            for user in all_users:
                # Generate user ID
                user_id = f"USER-{user['office_id'].upper()}-001"
                
                # Determine role based on office
                if user['office_id'] in ['pd_office', 'adb_hq']:
                    user_role = 'admin'
                else:
                    user_role = 'office_user'
                
                cur.execute(insert_user_query, (
                    user_id,
                    user['office_id'],  # Use office_id as unique login
                    user['office_name'],
                    user['office_id'],  # username = office_id
                    '1234',  # Default password
                    user_role,
                    'active',
                    user['office_id']
                ))
    
    print(f"Created {len(all_users)} user accounts")

if __name__ == "__main__":
    create_office_management_table()
