import sys
from datetime import datetime


def main() -> int:
    try:
        from backend.services.database_services.postgres_services import DatabaseManager

        db = DatabaseManager()

        # Dummy data
        data = {
            'complainant_full_name': 'Test User',
            'complainant_phone': '9800000000',
            'complainant_email': 'test.user@example.com',
            'complainant_province': 'Koshi',
            'complainant_district': 'Jhapa',
            'complainant_municipality': 'Birtamod Municipality',
            'complainant_village': 'Birtamod',
            'complainant_address': 'Test Street 123',
            'language_code': 'en',
            'source': 'bot',
            'grievance_description': 'Road dust and noise affecting family health',
            'grievance_categories': ['Environmental - Air Pollution', 'Environmental - Noise Pollution'],
            'grievance_summary': 'Dust and noise from nearby construction',
            'otp_verified': True,
        }

        # Create complainant
        complainant_id = db.create_complainant(data)
        print(f"Created complainant_id: {complainant_id}")
        data['complainant_id'] = complainant_id

        # Create grievance
        grievance_id = db.create_grievance(data)
        print(f"Created grievance_id: {grievance_id}")
        data['grievance_id'] = grievance_id

        # Submit full grievance (updates records and logs SUBMITTED status)
        ok = db.submit_grievance_to_db(data=data)
        print(f"submit_grievance_to_db: {'OK' if ok else 'FAILED'}")

        return 0 if ok else 2
    except Exception as e:
        print(f"❌ Error seeding dummy grievance: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())


