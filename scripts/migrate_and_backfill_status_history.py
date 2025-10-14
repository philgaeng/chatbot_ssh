import sys
from typing import Optional


def main() -> int:
    """
    Migrate grievance_status_history to the enhanced schema and backfill
    initial SUBMITTED entries for grievances missing history.
    """
    try:
        from backend.services.database_services.base_manager import BaseDatabaseManager, TableDbManager

        class MigrationRunner(BaseDatabaseManager):
            def migrate_enhanced_status_history_schema(self) -> bool:
                try:
                    self.logger.info("Starting schema migration for grievance_status_history...")
                    with self.get_connection() as conn:
                        with conn.cursor() as cur:
                            # Add enhanced columns if they don't exist
                            cur.execute(
                                """
                                ALTER TABLE grievance_status_history
                                  ADD COLUMN IF NOT EXISTS change_type TEXT NOT NULL DEFAULT 'status_change',
                                  ADD COLUMN IF NOT EXISTS field_changes JSONB,
                                  ADD COLUMN IF NOT EXISTS assigned_to TEXT,
                                  ADD COLUMN IF NOT EXISTS notes TEXT,
                                  ADD COLUMN IF NOT EXISTS created_by TEXT NOT NULL DEFAULT 'system';
                                """
                            )

                            # Ensure constraint matches the enhanced definition (drop and recreate)
                            cur.execute(
                                """
                                DO $$
                                BEGIN
                                  IF EXISTS (
                                    SELECT 1 FROM information_schema.table_constraints
                                    WHERE table_name='grievance_status_history'
                                      AND constraint_name='status_or_fields_check'
                                  ) THEN
                                    ALTER TABLE grievance_status_history DROP CONSTRAINT status_or_fields_check;
                                  END IF;
                                END$$;
                                """
                            )
                            cur.execute(
                                """
                                ALTER TABLE grievance_status_history 
                                  ADD CONSTRAINT status_or_fields_check CHECK (
                                    (change_type IN ('status_change','creation') AND status_code IS NOT NULL) OR
                                    (change_type IN ('field_update', 'complainant_update', 'system_update') AND field_changes IS NOT NULL)
                                  );
                                """
                            )

                            # Create helpful indexes
                            cur.execute(
                                """
                                CREATE INDEX IF NOT EXISTS idx_status_history_change_type ON grievance_status_history(change_type);
                                CREATE INDEX IF NOT EXISTS idx_status_history_field_changes ON grievance_status_history USING GIN(field_changes);
                                CREATE INDEX IF NOT EXISTS idx_status_history_grievance_change_type ON grievance_status_history(grievance_id, change_type);
                                """
                            )

                            conn.commit()
                            self.logger.info("Schema migration completed successfully")
                            return True
                except Exception as e:
                    self.logger.error(f"Schema migration failed: {e}")
                    return False

        migrator = MigrationRunner()
        backfill_manager = TableDbManager()

        # 1) Run schema migration
        if not migrator.migrate_enhanced_status_history_schema():
            print("❌ Schema migration failed. See logs for details.")
            return 1

        # 2) Backfill SUBMITTED entries for grievances without history
        print("Running backfill for grievances missing status history...")
        if backfill_manager.backfill_missing_status_history():
            print("✅ Backfill completed successfully!")
            return 0
        else:
            print("❌ Backfill failed. See logs for details.")
            return 2

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 3


if __name__ == "__main__":
    sys.exit(main())


