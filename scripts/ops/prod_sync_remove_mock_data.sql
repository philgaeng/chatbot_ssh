-- Run after AWS → prod pg_restore. Removes seeded demo tickets (mock_tickets.py).
-- Safe to run: only deletes GRV-2025-* / CPL-2025-* rows.

BEGIN;

CREATE TEMP TABLE _mock_tickets ON COMMIT DROP AS
  SELECT ticket_id, grievance_id
  FROM ticketing.tickets
  WHERE grievance_id LIKE 'GRV-2025-%';

-- ticketing.* (children without FK cascade first)
DELETE FROM ticketing.ticket_context_cache
  WHERE ticket_id IN (SELECT ticket_id FROM _mock_tickets);

DELETE FROM ticketing.ticket_resolved_summaries
  WHERE grievance_id LIKE 'GRV-2025-%'
     OR ticket_id IN (SELECT ticket_id FROM _mock_tickets);

DELETE FROM ticketing.ticket_files
  WHERE ticket_id IN (SELECT ticket_id FROM _mock_tickets);

DELETE FROM ticketing.tickets
  WHERE grievance_id LIKE 'GRV-2025-%';

-- public.* (mock rows may be absent if demo existed only in ticketing)
DELETE FROM grievance_sensitive_access_audit
  WHERE grievance_id LIKE 'GRV-2025-%';

DELETE FROM grievance_reveal_sessions
  WHERE grievance_id LIKE 'GRV-2025-%';

DELETE FROM grievance_vault_payloads
  WHERE grievance_id LIKE 'GRV-2025-%';

DELETE FROM grievance_parties
  WHERE grievance_id LIKE 'GRV-2025-%'
     OR complainant_id LIKE 'CPL-2025-%';

DELETE FROM task_entities
  WHERE entity_id LIKE 'GRV-2025-%'
     OR entity_id LIKE 'CPL-2025-%';

DELETE FROM file_attachments
  WHERE grievance_id LIKE 'GRV-2025-%';

DELETE FROM grievance_status_history
  WHERE grievance_id LIKE 'GRV-2025-%';

DELETE FROM grievances
  WHERE grievance_id LIKE 'GRV-2025-%';

DELETE FROM complainants
  WHERE complainant_id LIKE 'CPL-2025-%';

COMMIT;
