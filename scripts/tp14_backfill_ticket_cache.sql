-- TP-14 one-off: copy summary/categories/location from public.grievances into ticketing.tickets
-- when ticket cache is empty but grievance has data.

UPDATE ticketing.tickets t
SET
    grievance_summary = g.grievance_summary,
    grievance_categories = g.grievance_categories::text,
    grievance_location = COALESCE(g.grievance_location, t.grievance_location),
    updated_at = NOW()
FROM public.grievances g
WHERE t.grievance_id = g.grievance_id
  AND t.is_deleted = false
  AND (t.grievance_summary IS NULL OR TRIM(t.grievance_summary) = '')
  AND g.grievance_summary IS NOT NULL
  AND TRIM(g.grievance_summary) <> '';
