#!/usr/bin/env python3
"""
Seed reference_municipality_villages, reference_grm_office_in_charge,
and grievance_classification_taxonomy from backend/dev-resources CSVs.

Run from repo root:
  python dev-scripts/seed_reference_data.py

Uses POSTGRES_* from env.local / .env (same as the app). Creates tables if missing.
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_batch

REPO_ROOT = Path(__file__).resolve().parent.parent
DEV_RES = REPO_ROOT / "backend" / "dev-resources"


def _connect():
    load_dotenv(REPO_ROOT / "env.local")
    load_dotenv(REPO_ROOT / ".env")
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        database=os.getenv("POSTGRES_DB", "grievance_db"),
        user=os.getenv("POSTGRES_USER", "nepal_grievance_admin"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        port=os.getenv("POSTGRES_PORT", "5432"),
    )


def _ensure_tables(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reference_municipality_villages (
            id SERIAL PRIMARY KEY,
            municipality TEXT NOT NULL,
            ward TEXT NOT NULL,
            village TEXT NOT NULL,
            CONSTRAINT uq_ref_mv UNIQUE (municipality, ward, village)
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_ref_mv_municipality ON reference_municipality_villages (municipality)"
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reference_grm_office_in_charge (
            id SERIAL PRIMARY KEY,
            office_id TEXT,
            office_name TEXT,
            office_address TEXT,
            office_email TEXT,
            office_pic_name TEXT,
            office_phone TEXT,
            district TEXT,
            municipality TEXT
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_ref_grm_dist_mun ON reference_grm_office_in_charge (district, municipality)"
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS grievance_classification_taxonomy (
            category_key TEXT PRIMARY KEY,
            generic_grievance_name TEXT,
            generic_grievance_name_ne TEXT,
            short_description TEXT,
            short_description_ne TEXT,
            classification TEXT,
            classification_ne TEXT,
            description TEXT,
            description_ne TEXT,
            follow_up_question_description TEXT,
            follow_up_question_description_ne TEXT,
            follow_up_question_quantification TEXT,
            follow_up_question_quantification_ne TEXT,
            high_priority BOOLEAN DEFAULT FALSE
        )
        """
    )


def main() -> int:
    mv_csv = DEV_RES / "location_dataset_municipality_villages.csv"
    office_csv = DEV_RES / "location_dataset_GRM_list_office_in_charge.csv"
    class_csv = DEV_RES / "grievances_categorization_v1.1.csv"
    lookup_path = DEV_RES / "lookup_tables" / "list_category.txt"

    for p, label in ((mv_csv, "municipality_villages"), (office_csv, "GRM office"), (class_csv, "classification")):
        if not p.exists():
            print(f"Missing {label} file: {p}", file=sys.stderr)
            return 1

    conn = _connect()
    cur = conn.cursor()
    try:
        _ensure_tables(cur)
        conn.commit()
    except Exception as e:
        cur.close()
        conn.close()
        print(f"Failed to ensure tables: {e}", file=sys.stderr)
        return 1

    cur = conn.cursor()
    try:
        cur.execute("TRUNCATE reference_municipality_villages RESTART IDENTITY")
        cur.execute("TRUNCATE reference_grm_office_in_charge RESTART IDENTITY")
        cur.execute("TRUNCATE grievance_classification_taxonomy")

        with mv_csv.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            mv_rows = []
            for row in reader:
                m = row.get("Municipality") or row.get("municipality") or ""
                w = row.get("Ward") or row.get("ward") or ""
                v = row.get("Village") or row.get("village") or ""
                mv_rows.append((str(m).strip(), str(w).strip(), str(v).strip()))
        execute_batch(
            cur,
            "INSERT INTO reference_municipality_villages (municipality, ward, village) VALUES (%s, %s, %s)",
            mv_rows,
            page_size=500,
        )

        with office_csv.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            off_rows = []
            for row in reader:
                d = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
                off_rows.append(
                    (
                        d.get("office_id", ""),
                        d.get("office_name", ""),
                        d.get("office_address", ""),
                        d.get("office_email", ""),
                        d.get("office_pic_name", ""),
                        d.get("office_phone", ""),
                        d.get("district", ""),
                        d.get("municipality", ""),
                    )
                )
        execute_batch(
            cur,
            """
            INSERT INTO reference_grm_office_in_charge (
                office_id, office_name, office_address, office_email, office_pic_name, office_phone, district, municipality
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            off_rows,
            page_size=200,
        )

        cat_rows = []
        with class_csv.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ck = (
                    f"{row['classification'].replace('-', ' ').title()} - "
                    f"{row['generic_grievance_name'].replace('-', ' ').title()}"
                )
                hp = (row.get("high_priority") or "").lower() == "true"
                cat_rows.append(
                    (
                        ck,
                        row.get("generic_grievance_name", ""),
                        row.get("generic_grievance_name_ne", ""),
                        row.get("short_description", ""),
                        row.get("short_description_ne", ""),
                        row.get("classification", ""),
                        row.get("classification_ne", ""),
                        row.get("description", ""),
                        row.get("description_ne", ""),
                        row.get("follow_up_question_description", ""),
                        row.get("follow_up_question_description_ne", ""),
                        row.get("follow_up_question_quantification", ""),
                        row.get("follow_up_question_quantification_ne", ""),
                        hp,
                    )
                )
        execute_batch(
            cur,
            """
            INSERT INTO grievance_classification_taxonomy (
                category_key, generic_grievance_name, generic_grievance_name_ne,
                short_description, short_description_ne, classification, classification_ne,
                description, description_ne, follow_up_question_description,
                follow_up_question_description_ne, follow_up_question_quantification,
                follow_up_question_quantification_ne, high_priority
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            cat_rows,
            page_size=200,
        )

        conn.commit()
        print(
            f"Seeded {len(mv_rows)} municipality_village rows, "
            f"{len(off_rows)} GRM office rows, {len(cat_rows)} classification rows."
        )

        lookup_path.parent.mkdir(parents=True, exist_ok=True)
        cats = sorted({r[0] for r in cat_rows})
        lookup_path.write_text("\n".join(cats) + "\n", encoding="utf-8")
        print(f"Wrote {lookup_path} ({len(cats)} categories)")
    finally:
        cur.close()
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
