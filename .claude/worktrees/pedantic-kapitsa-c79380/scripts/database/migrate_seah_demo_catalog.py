#!/usr/bin/env python3
"""Demo-safe SEAH catalog migration (no Alembic cutover)."""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, PROJECT_ROOT)
os.environ["PYTHONPATH"] = PROJECT_ROOT

from backend.services.database_services.postgres_services import db_manager


def main() -> int:
    print("Running SEAH demo catalog migration...")
    ok_projects = db_manager.table.ensure_projects_table()
    ok_project_seed = db_manager.table.seed_demo_project_kl_road()
    ok_contact_seed = db_manager.table.seed_demo_jhapa_contact_points()

    if not (ok_projects and ok_project_seed and ok_contact_seed):
        print("Migration failed. Check logs for details.")
        return 1

    print("Migration completed.")
    print("Seeded project_uuid: 7b0c4f10-0fd6-4fc0-9f2d-1b070d2f2d3d")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
