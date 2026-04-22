#!/usr/bin/env python3
"""Import demo SEAH project + contact-point CSV seeds into Postgres."""

import csv
import os
import sys
from typing import Dict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, PROJECT_ROOT)
os.environ["PYTHONPATH"] = PROJECT_ROOT

from backend.services.database_services.postgres_services import db_manager


def _to_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "t"}


def ensure_tables() -> None:
    if not db_manager.table.ensure_projects_table():
        raise RuntimeError("Failed ensuring projects table")
    # Leverage existing SEAH DDL initializer
    db_manager._ensure_seah_contact_points_table()


def import_projects(csv_path: str) -> int:
    upsert_sql = """
        INSERT INTO projects (
            project_uuid, country, administrative_layer_level_1, administrative_layer_level_2,
            administrative_layer_level_3, name_en, name_local, project_short_denomination, adb, inactive_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (project_uuid)
        DO UPDATE SET
            country = EXCLUDED.country,
            administrative_layer_level_1 = EXCLUDED.administrative_layer_level_1,
            administrative_layer_level_2 = EXCLUDED.administrative_layer_level_2,
            administrative_layer_level_3 = EXCLUDED.administrative_layer_level_3,
            name_en = EXCLUDED.name_en,
            name_local = EXCLUDED.name_local,
            project_short_denomination = EXCLUDED.project_short_denomination,
            adb = EXCLUDED.adb,
            inactive_at = EXCLUDED.inactive_at,
            updated_at = CURRENT_TIMESTAMP
    """
    count = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            db_manager.execute_update(
                upsert_sql,
                (
                    row["project_uuid"],
                    row["country"],
                    row["administrative_layer_level_1"],
                    row["administrative_layer_level_2"],
                    row["administrative_layer_level_3"],
                    row["name_en"],
                    row["name_local"],
                    row["project_short_denomination"],
                    _to_bool(row["adb"]),
                    (row.get("inactive_at") or None),
                ),
            )
            count += 1
    return count


def import_contact_points(csv_path: str) -> int:
    upsert_sql = """
        INSERT INTO seah_contact_points (
            seah_contact_point_id, province, district, municipality, ward, project_uuid,
            seah_center_name, address, phone, opening_days, opening_hours, is_active, sort_order
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (seah_contact_point_id)
        DO UPDATE SET
            province = EXCLUDED.province,
            district = EXCLUDED.district,
            municipality = EXCLUDED.municipality,
            ward = EXCLUDED.ward,
            project_uuid = EXCLUDED.project_uuid,
            seah_center_name = EXCLUDED.seah_center_name,
            address = EXCLUDED.address,
            phone = EXCLUDED.phone,
            opening_days = EXCLUDED.opening_days,
            opening_hours = EXCLUDED.opening_hours,
            is_active = EXCLUDED.is_active,
            sort_order = EXCLUDED.sort_order
    """
    count = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            db_manager.execute_update(
                upsert_sql,
                (
                    row["seah_contact_point_id"],
                    row["province"],
                    row["district"],
                    row["municipality"],
                    row["ward"],
                    row["project_uuid"],
                    row["seah_center_name"],
                    row["address"],
                    row["phone"],
                    row["opening_days"],
                    row["opening_hours"],
                    _to_bool(row["is_active"]),
                    int(row["sort_order"]),
                ),
            )
            count += 1
    return count


def main() -> int:
    seed_dir = os.path.join(SCRIPT_DIR, "seeds")
    projects_csv = os.path.join(seed_dir, "projects_demo.csv")
    contacts_csv = os.path.join(seed_dir, "seah_contact_points_jhapa_demo.csv")

    ensure_tables()
    project_count = import_projects(projects_csv)
    contact_count = import_contact_points(contacts_csv)
    print(f"Imported/updated projects rows: {project_count}")
    print(f"Imported/updated seah_contact_points rows: {contact_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
