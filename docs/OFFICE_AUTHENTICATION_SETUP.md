# Office Authentication Setup Guide

This guide explains how to set up role-based access control for the Google Sheets monitoring system.

## Overview

The system now supports authentication and filtering based on office locations:

- **Admin Users**: `pd_office` and `adb_hq` can see all grievances
- **Office Users**: Each office can only see grievances from their municipality
- **Authentication**: Username/password based authentication via Google Sheets

## User Accounts

The following user accounts are created:

| Username  | Password | Access Level | Municipality       |
| --------- | -------- | ------------ | ------------------ |
| pd_office | 1234     | Admin        | All municipalities |
| adb_hq    | 1234     | Admin        | All municipalities |
| office_1  | 1234     | Office User  | Birtamod           |
| office_2  | 1234     | Office User  | Mechinagar         |
| office_3  | 1234     | Office User  | [As configured]    |
| office_4  | 1234     | Office User  | [As configured]    |
| office_5  | 1234     | Office User  | [As configured]    |

## Setup Instructions

### 1. Create Office Management Table

Run the database setup script:

```bash
cd /home/philg/projects/nepal_chatbot
python scripts/database/create_office_management_table.py
```

This script will:

- Create the `office_management` table (without municipality column)
- Create the `office_municipality_ward` junction table
- Populate `office_management` with data from `location_dataset_GRM_list_office_in_charge.csv`
- Populate `office_municipality_ward` with data from `location_dataset_office_municipality_ward.csv`
- Create user accounts in the `office_user` table

### 2. Configure Google Sheets

#### Option A: Using Named Ranges (Recommended)

1. In your Google Sheet, create named ranges:
   - Create a cell with username (e.g., `office_1`)
   - Select the cell and go to **Data > Named ranges**
   - Name it `USERNAME`
   - Repeat for password with name `PASSWORD`

#### Option B: Using Script Properties

1. In Google Apps Script, go to **Project Settings** (gear icon)
2. Add script properties:
   - `DEFAULT_USERNAME`: `office_1`
   - `DEFAULT_PASSWORD`: `1234`

#### Option C: Hardcoded (For Testing)

The script defaults to `pd_office` with password `1234` for testing.

### 3. Test the System

1. **Test Admin Access**:

   - Set username to `pd_office`
   - Run the script - should see all grievances

2. **Test Office Access**:

   - Set username to `office_1`
   - Run the script - should only see Birtamod grievances

3. **Test Office 2**:
   - Set username to `office_2`
   - Run the script - should only see Mechinagar grievances

## API Usage

### Authentication

The API now accepts authentication via the `Authorization` header:

```javascript
headers: {
  "Authorization": "Bearer office_1",
  "Content-Type": "application/json"
}
```

### Filtering

The API automatically filters grievances based on the authenticated user:

- **Admin users** (`pd_office`, `adb_hq`): See all grievances
- **Office users**: Only see grievances from their municipality

## Database Schema

### office_management Table

```sql
CREATE TABLE office_management (
    office_id TEXT PRIMARY KEY,
    office_name TEXT NOT NULL,
    office_address TEXT,
    office_email TEXT,
    office_pic_name TEXT,
    office_phone TEXT,
    district TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### office_municipality_ward Table (Junction Table)

```sql
CREATE TABLE office_municipality_ward (
    id SERIAL PRIMARY KEY,
    office_id TEXT NOT NULL,
    municipality TEXT NOT NULL,
    ward INTEGER NOT NULL,
    village TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (office_id) REFERENCES office_management(office_id) ON DELETE CASCADE,
    UNIQUE(office_id, municipality, ward, village)
);
```

### office_user Table (Updated)

The existing `office_user` table is used for authentication:

```sql
-- User accounts are created with:
-- user_login = office_id (e.g., 'office_1')
-- user_password = '1234'
-- user_role = 'admin' or 'office_user'
-- user_office_id = office_id
```

## Security Considerations

1. **Password Management**: Consider implementing proper password hashing
2. **Token-based Auth**: For production, implement JWT tokens
3. **Audit Logging**: All access is logged for security auditing
4. **Fail-safe**: On authentication errors, the system defaults to showing all data

## Troubleshooting

### Common Issues

1. **No Data Returned**:

   - Check if user exists in `office_management` table
   - Verify municipality names match exactly
   - Check API logs for authentication errors

2. **Authentication Errors**:

   - Verify username is correct (case-sensitive)
   - Check if user account exists in `office_user` table

3. **Wrong Municipality Filter**:
   - Check `office_management` table for correct municipality mapping
   - Verify municipality names in grievances match office assignments

### Debug Commands

```sql
-- Check user accounts
SELECT * FROM office_user WHERE user_login IN ('pd_office', 'office_1', 'office_2');

-- Check office management
SELECT * FROM office_management;

-- Check office municipality ward mapping
SELECT * FROM office_municipality_ward;

-- Check municipality distribution
SELECT complainant_municipality, COUNT(*)
FROM complainants c
JOIN grievances g ON c.complainant_id = g.complainant_id
GROUP BY complainant_municipality;
```

## Future Enhancements

1. **JWT Token Authentication**: Implement proper token-based auth
2. **Password Encryption**: Hash passwords in database
3. **Role-based Permissions**: More granular permission system
4. **Audit Trail**: Track all data access and modifications
5. **Multi-level Filtering**: Filter by district, province, etc.
