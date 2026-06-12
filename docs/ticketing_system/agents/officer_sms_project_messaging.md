# Agent: Project-level officer SMS (assignment alerts)

**Copy this entire file into a new Cursor agent session and run in one pass.**

## Mission

Implement **project-level officer SMS** on assignment at configurable workflow levels (L1–Ln), per locked spec [../06_messaging_rules_whatsapp_sms.md](../06_messaging_rules_whatsapp_sms.md).

Country admins enable SMS under Settings → Projects & packages → project editor → **Messaging**. When a ticket is assigned to an officer at an enabled level, send a link-only SMS (no PII) via the existing messaging API.

**Do not** modify forbidden paths in root `CLAUDE.md` (`backend/api/`, `docker-compose.yml`, etc.). All new backend code stays under `ticketing/`; UI under `channels/ticketing-ui/`.

---

## Read first (in order)

| File | Why |
|------|-----|
| [../06_messaging_rules_whatsapp_sms.md](../06_messaging_rules_whatsapp_sms.md) | Locked product rules (this feature) |
| [../13_projects_and_packages.md](../13_projects_and_packages.md) | Project editor layout |
| `docs/sprints/claude-tickets/PROGRESS.md` | Update when done |
| `docs/sprints/claude-tickets/TODO.md` | Close related gap if listed |
| `ticketing/tasks/notifications.py` | Existing `notify_assignment` (in-app only) |
| `ticketing/clients/messaging_api.py` | `send_sms()` |
| `ticketing/services/keycloak_users.py` | `profiles_for_user_ids()` for phone lookup |
| `ticketing/services/project_go_live.py` | Add check F1 |
| `ticketing/services/ticket_intake.py` | Create + assign hook |
| `ticketing/engine/escalation.py` | Escalation assign hook |
| `ticketing/api/routers/tickets.py` | Manual reassign / escalate hooks |
| `channels/ticketing-ui/app/settings/page.tsx` | `ProjectEditor` — add Messaging section |

---

## Implementation checklist

Execute **all** steps below in one session. Do not commit unless the user asks.

### Phase 1 — Database + models

1. **Alembic migration** (`ticketing/migrations/versions/`):
   - Header: `# Safe to run: only creates/modifies ticketing.* tables`
   - Add `officer_messaging JSONB NOT NULL` to `ticketing.projects` with server default:
     ```json
     {"sms_enabled": false, "sms_levels": [], "whatsapp_levels": []}
     ```
   - `include_object` / `version_table_schema="ticketing"` unchanged.

2. **`ticketing/models/project.py`**: map `officer_messaging` column (`JSON`, default factory matching spec).

3. **Pydantic schemas** (new file `ticketing/api/schemas/project_messaging.py` or extend `locations.py` schemas):
   - `OfficerMessagingConfig`: `sms_enabled: bool`, `sms_levels: list[int]`, `whatsapp_levels: list[int] = []`
   - `ProjectMessagingResponse`: config + `max_levels: int`
   - `ProjectMessagingPatch`: same fields; validate `sms_levels` are unique positive ints ≤ `max_levels`

### Phase 2 — Service layer

4. **`ticketing/services/officer_messaging.py`** (new):

   ```python
   def max_workflow_levels_for_project(db, project_id) -> int:
       # MAX(step_order) across all workflows in project_workflows for project

   def get_officer_messaging(db, project_id) -> OfficerMessagingConfig

   def update_officer_messaging(db, project_id, patch) -> OfficerMessagingConfig

   def resolve_project_id(db, ticket: Ticket) -> str | None:
       # ticket.project_code → projects.short_code, or future project_id column

   def build_officer_sms_body(ticket: Ticket, *, event: str = "assignment") -> str:
       # grievance_id + short categories/location + URL
       # URL: settings.ticketing_public_base_url.rstrip("/") + f"/tickets/{ticket.ticket_id}"

   def should_send_officer_sms(config, step_order: int) -> bool

   def notify_officer_assignment_sync(db, ticket_id, assigned_to_user_id, step_id) -> dict:
       # Full gate + send + TicketEvent audit; return {sent, skipped, reason}
   ```

   Phone lookup: `profiles_for_user_ids([assigned_to_user_id])` → `phone_number`.

5. **`ticketing/tasks/notifications.py`**:
   - Add Celery task `notify_officer_assignment` calling `notify_officer_assignment_sync`.
   - Update `notify_assignment` to **also** `.delay()` officer SMS task (or merge into one task that does in-app + SMS).
   - Keep in-app `ASSIGNMENT_NOTIFICATION` event unchanged.

### Phase 3 — API

6. **`ticketing/api/routers/locations.py`** (projects router) or new `project_messaging.py` router:
   - `GET /api/v1/projects/{project_id}/messaging`
   - `PATCH /api/v1/projects/{project_id}/messaging`
   - Auth: `require_country_admin_or_super` (match project PATCH patterns in `ticketing/services/admin_access.py`)
   - On PATCH: if `sms_enabled` and `sms_levels` empty, allow (means master on but no levels — no sends) OR normalize; document behaviour in code comment.

7. Register router in `ticketing/api/main.py` if new file.

8. Optionally expose `officer_messaging` on `ProjectResponse` from `GET /projects/{id}`.

### Phase 4 — Wire assignment hooks

9. After successful commit paths that set `assigned_to_user_id`, enqueue notification:

   | File | Function / area |
   |------|-----------------|
   | `ticketing/services/ticket_intake.py` | End of `create_ticket_from_intake` when `auto_assigned_id` set |
   | `ticketing/engine/escalation.py` | After `new_assigned` set on ticket |
   | `ticketing/api/routers/tickets.py` | Reassign action (~`assign_to_user_id`), manual escalate that changes assignee |

   Pattern:
   ```python
   from ticketing.tasks.notifications import notify_officer_assignment
   notify_officer_assignment.delay(ticket.ticket_id, assigned_user_id, ticket.current_step_id)
   ```

   Call **after** `db.commit()` (or use `on_commit` hook) so ticket state is visible to the task.

10. **Do not** call for assignment changes that don't change `assigned_to_user_id`.

### Phase 5 — Go-live

11. **`ticketing/services/project_go_live.py`**:
    - Check **F1**: when `officer_messaging.sms_enabled` and non-empty `sms_levels`, for each level get `assigned_role_key` from **any** linked workflow that has that step (use longest workflow / union of roles per level).
    - WARN if no scoped officer with phone for that role on project (reuse patterns from C1/C4 checks + Keycloak `list_grm_officer_profiles` or `profiles_for_user_ids`).
    - `section="messaging"` for go-live panel jump.

12. **`ProjectGoLivePanel`** (if section map needed): add `messaging` jump key in project editor `sectionRefs`.

### Phase 6 — Frontend

13. **`channels/ticketing-ui/lib/api.ts`** (or projects helper):
    - `getProjectMessaging(projectId)`
    - `patchProjectMessaging(projectId, body)`

14. **`channels/ticketing-ui/app/settings/page.tsx`** — `ProjectEditor`:
    - New section **Messaging** after Grievance workflows (~line 3097), before Actor roles.
    - Load messaging config + `max_levels` on mount.
    - Master toggle: "Officer SMS enabled".
    - Checkboxes L1…L{max_levels} (disabled when master off).
    - WhatsApp row: greyed "Coming soon" per level (optional visual only).
    - Save button → `PATCH .../messaging`.
    - `canEdit`: `isSuperAdmin || isCountryAdmin` (not `project_admin`).
    - `ref` for go-live: `sectionRefs.current.messaging`.

15. **Types**: extend `ProjectItem` if embedding messaging on project GET.

### Phase 7 — Tests

16. **`tests/ticketing/test_officer_messaging.py`** (new):
    - `should_send_officer_sms` gate logic (master, levels).
    - `build_officer_sms_body` contains grievance_id and `/tickets/` URL; no complainant name.
    - PATCH messaging validation (level > max_levels → 422).
    - Go-live F1 warn when SMS on + no phones (mock Keycloak profiles).

17. Run: `pytest tests/ticketing/test_officer_messaging.py -q` (and any affected existing tests).

### Phase 8 — Docs + progress

18. Update [../13_projects_and_packages.md](../13_projects_and_packages.md) §5 table: insert Messaging row (#4), renumber following sections.

19. Update `docs/sprints/claude-tickets/PROGRESS.md` — note officer SMS implemented.

20. Update `docs/sprints/claude-tickets/TODO.md` — strike related open item if present.

---

## Message template (locked)

```
New case: {grievance_id} ({category_snippet}, {location_snippet}). Open: {url}
```

- `category_snippet`: first category from `grievance_categories` or `"General"`.
- `location_snippet`: `grievance_location` or ticket `location_code` or `"—"`.
- On escalation/reassign, prefix may be `Escalation:` or `Assigned:` — all allowed per spec §2.1.
- Max ~160 chars desirable; truncate snippet with `…` if needed.

---

## Hard constraints

- **No PII** in SMS body or `OFFICER_SMS_*` event payloads.
- **No** `ticketing.*` joins into `public.*`.
- Officer SMS **not** gated by global `notification_rules`.
- SMS failure must **not** roll back ticket assignment.
- Use `requirements.grm.txt` for new Python deps (prefer stdlib / existing deps only).
- Do **not** touch `backend/api/routers/messaging.py` — call via HTTP client only.

---

## Verification (manual)

1. Docker stack up per `docs/sprints/claude-tickets/DOCKER.md`.
2. As country admin: open project → Messaging → enable SMS for L1 only → save.
3. Create ticket (webhook or API) assigned to L1 officer with phone in Keycloak.
4. Confirm `OFFICER_SMS_SENT` event + SMS in messaging logs (or mocked client in dev).
5. Escalate to L2 with SMS disabled for L2 → no second SMS.
6. Enable L2, escalate → SMS to new assignee.
7. Go-live panel shows F1 warn when L1 SMS on and officer has no phone.

---

## Suggested file list (create / modify)

| Action | Path |
|--------|------|
| Create | `ticketing/migrations/versions/*_project_officer_messaging.py` |
| Modify | `ticketing/models/project.py` |
| Create | `ticketing/services/officer_messaging.py` |
| Modify | `ticketing/tasks/notifications.py` |
| Modify | `ticketing/api/routers/locations.py` (or new router) |
| Modify | `ticketing/api/main.py` |
| Modify | `ticketing/services/ticket_intake.py` |
| Modify | `ticketing/engine/escalation.py` |
| Modify | `ticketing/api/routers/tickets.py` |
| Modify | `ticketing/services/project_go_live.py` |
| Modify | `channels/ticketing-ui/app/settings/page.tsx` |
| Modify | `channels/ticketing-ui/lib/api.ts` |
| Create | `tests/ticketing/test_officer_messaging.py` |
| Modify | `docs/ticketing_system/13_projects_and_packages.md` |
| Modify | `docs/sprints/claude-tickets/PROGRESS.md` |

---

## Done when

All §9 acceptance criteria in [../06_messaging_rules_whatsapp_sms.md](../06_messaging_rules_whatsapp_sms.md) pass and tests are green.
