# DECISION — SEAH becomes an ordinary workflow with a "sensitive" property

**Decided:** 2026-08-02 (Philippe). **Status:** locked — specs updated; code change outstanding (see §7).
**Supersedes:** the `workflow_type ∈ {standard, seah}` track model wherever the two disagree.
**Related:** [12_workflows_configuration.md](../../ticketing_system/12_workflows_configuration.md) · [13 §5B](../../ticketing_system/13_projects_and_packages.md) · [11_roles_and_permissions.md](../../ticketing_system/11_roles_and_permissions.md) · [docs/seah/](../../seah/) · [followup](followups/workflow-stream-vocabulary-and-intake-route-labels.md) §5

---

## 1. The decision

**SEAH is not a system concept. It is the name someone gives a workflow.** What makes that workflow special is a single property set when the workflow is authored: **sensitive**.

1. **One flag.** `workflow_definitions.workflow_type ∈ {standard, seah}` → **`workflow_definitions.is_sensitive`** (boolean, set in the Workflows step editor). Everything that keyed off `workflow_type` keys off this.
2. **One default.** A project has exactly one default workflow. A sensitive workflow **cannot** be it (422) — otherwise every unmatched grievance would silently enter the restricted track.
3. **Sensitive workflows are optional.** A project may have none. Go-live check **A2** ("SEAH workflow configured") is **removed**.
4. **The quarterly report excludes sensitive cases** (today's `include_seah = False` default, renamed and kept).
5. **Only officers cast on a sensitive workflow may see its grievances or their PII.** Being an admin — of any tier, including `super_admin` — grants **no** access to a sensitive case.

## 2. What "sensitive" means — the contract, stated once

A workflow marked sensitive gives its grievances two properties, and only these:

| | Rule |
|---|---|
| **Access** | Only officers **cast on one of this workflow's steps** (actor / supervisor / participant / observer) can see that the grievance exists, open it, or act on it. Everyone else — including every admin and every oversight role — gets nothing: not a row, not a count in their queue. |
| **PII** | Complainant contact is **masked in the case view** and readable only through a **vault reveal**, which is available to the same cast and is **logged every time**, granted or denied. |

Everything else about a sensitive workflow — levels, SLAs, escalation, staffing, notifications, categories, its position in the project's workflow list — behaves exactly like any other workflow.

## 3. Configure ≠ read (the admin-track question, resolved)

Today `workflow_track = seah` on an admin scope does **two unrelated jobs at once**:

- **(a) configure** — create/edit SEAH workflows, invite SEAH officers, staff SEAH levels;
- **(b) read** — `can_see_seah_extended()` hands that admin visibility of every SEAH **case**.

**(b) is wrong and is removed.** An admin sets up who handles sensitive grievances; that is not a reason to read them. The two split cleanly:

| Capability | Who has it | Grants case access? |
|---|---|---|
| **Configure sensitive workflows** — author them, staff them, invite officers onto them | an admin scope flagged for it (today's `workflow_track = seah`, renamed to a capability, e.g. `may_manage_sensitive`) | **No** |
| **Work sensitive grievances** — see, open, act, reveal PII | **only** officers cast on that workflow's steps | Yes |

`can_see_seah_extended()` therefore loses **three** of its four branches — `super_admin`, `adb_hq_exec`, and `admin_scopes.workflow_track == 'seah'` — leaving cast membership (`seah_visibility.user_is_seah_track_member`) as the **single** source of access. Doc 11 §2.2's "Read tickets in subtree ✅ SEAH only" row is struck.

### Consequences, accepted
- **`super_admin` loses blanket visibility of sensitive cases.** Break-glass is to **staff themselves onto the workflow** — an explicit, audited assignment rather than an invisible standing privilege. This is the point, not a side effect.
- **`adb_hq_exec` (senior oversight) loses sensitive case read.** Oversight of sensitive work is by aggregate only — and per §1.4 the quarterly report excludes it, so oversight of sensitive cases is a deliberate gap to be filled, if ever, by a separate report for the cast.
- A sensitive grievance with an **unstaffed** level is visible to nobody until an admin staffs it. Acceptable: the same admin can staff it without reading it.

## 4. PII reveal — an open hole this decision closes

As-built, `POST /tickets/{id}/reveal` is gated only by `require_ticket_access`, and the backend policy check it calls **does not exist yet**: `clients/grievance_api.py` is a proto fallback that **always returns `granted: true`**. So today anyone who can see a sensitive case can reveal its PII, admins included.

Required: the reveal must check **cast membership on the sensitive workflow**, deny otherwise, and log both outcomes. Until the real `POST /api/grievance/{id}/reveal` lands in `backend/`, the check belongs in ticketing.

## 5. What does not change

- The vault / `grievance_parties` privacy model ([docs/seah/](../../seah/)).
- The chatbot's separate sensitive intake path (`seah_intake`) — an intake route like any other ([12 §1](../../ticketing_system/12_workflows_configuration.md)).
- `validate_step_roles` isolation: a role scoped to non-sensitive work cannot be cast on a sensitive step.
- The word **SEAH** on screen, where it is the *name of the workflow* — not the name of a mode ([ui/05 §4](../../ticketing_system/ui/05_ui_copy_style.md)).

## 6. Naming

| Old | New |
|---|---|
| `workflow_definitions.workflow_type` (`standard` \| `seah`) | `workflow_definitions.is_sensitive` (bool) |
| `tickets.is_seah` | `tickets.is_sensitive` (still **derived** from the bound workflow at intake) |
| `admin_scopes.workflow_track` (`standard` \| `seah`) | a capability flag, e.g. `may_manage_sensitive` |
| `quarterly_report.include_seah` | `include_sensitive` (default **false**) |
| `archiving.seah_years_before_archiving` | `sensitive_years_before_archiving` |
| UI: "SEAH track / SEAH officer" | the workflow's own name; the property reads **Sensitive** |

## 7. Touch list (code change outstanding)

**Model + migration** `models/workflow.py`, `models/ticket.py`, admin scope model · a migration mapping `workflow_type='seah'` → `is_sensitive=true`, keeping the old column readable for one release.
**Access** `services/admin_access.py` (`can_see_seah_extended` → cast-only), `api/dependencies.py`, `api/routers/tickets/crud.py` (visibility predicate), `services/seah_visibility.py` (rename, keep the logic — it is already right).
**PII** `api/routers/tickets/pii.py` + `clients/grievance_api.py` (§4 — the reveal gate).
**Routing** `services/project_workflows.py` (reject a sensitive default; drop the SEAH branch in `_sync_legacy_columns`), `services/workflow_routing.py`.
**Go-live** `services/project_go_live.py` (delete A2).
**Reports / retention** `services/quarterly_report.py`, `report_export.py`, `pivot_table.py`, `archiving_policy.py`.
**Notifications** `tasks/notifications.py` (`should_notify(workflow_slug=…)` keyed by track).
**Roles** `constants/grm_role_catalog.py`, `role_archetypes.py`, `models/user.py` (`SEAH_ROLES` legacy fast-path retires — cast membership replaces it).
**UI** `lib/trackFilter.ts`, `lib/labels.ts`, workflow editor (the **Sensitive** checkbox), officers/admin screens.
**Docs** 09, 11, 12, 13, ui/04, ui/06, docs/seah/.
