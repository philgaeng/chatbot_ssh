# DECISION — SEAH becomes an ordinary workflow with a "sensitive" property

**Decided:** 2026-08-02 (Philippe). **Status:** locked. **The access slice is built** (2026-08-02) — §3 and §4 are as-built and pinned by `tests/ticketing/test_sensitive_workflow_access.py`; the **rename** (§6) and the report/retention/notification key changes are outstanding (§7).
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
- **`adb_hq_exec` (senior oversight) loses sensitive case read *as a standing privilege*** — and **this leaves no gap**: ADB has its own safeguards experts, and ADB staff who need sensitive cases are **cast onto the sensitive workflow** like any other officer (observer tier is enough for read-only oversight). Donor oversight of sensitive work is therefore explicit, per-person, and auditable rather than implied by a role name.
- A sensitive grievance with an **unstaffed** level is visible to nobody until an admin staffs it. Acceptable: the same admin can staff it without reading it.

## 4. PII reveal — the hole this decision closes ✅ **built 2026-08-02**

The hole: `POST /tickets/{id}/reveal` was gated only by `require_ticket_access`, and the backend policy check it calls **does not exist** — `clients/grievance_api.py` is a proto fallback that **always returns `granted: true`**. So any admin who could see a sensitive case could reveal its PII.

**Built:** `_require_sensitive_cast()` in `api/routers/tickets/pii.py` now gates **both** disclosure endpoints (`/pii` and `/reveal`) on cast membership. It duplicates what `require_ticket_access` enforces since §3 — deliberately, because this is the endpoint that discloses PII and the invariant must be stated where the disclosure happens, not only in a shared dependency someone could later relax. Ticketing remains the **only** gate on this path until the real `POST /api/grievance/{id}/reveal` lands in `backend/`.

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

## 7. Touch list

### ✅ Built 2026-08-02 — the access slice

| Area | What landed |
|---|---|
| **Access** | `can_see_seah_extended()` → **cast-only**; new `can_configure_sensitive_workflows()` carries the removed admin branches. `CurrentUser.can_configure_sensitive` added. The ticket/task/viewer/report/notification gates inherit the new rule through `can_see_seah` — no change needed at those call sites, which is the payoff of having one predicate. |
| **Catalog** | `api/routers/workflows.py` switched its six gates to `can_configure_sensitive` — an admin still authors, lists, clones and binds sensitive workflows while seeing none of their cases. |
| **Notifications** | `chart_behaviors.user_can_see_seah()` (per-user_id mirror) dropped `BOTH_WORKFLOWS_ROLES`, so `super_admin`/`adb_hq_exec` are no longer told a sensitive grievance exists. |
| **PII** | `_require_sensitive_cast()` on `/pii` and `/reveal` (§4). |
| **Routing** | `project_workflows.replace_project_workflows()` rejects a sensitive default (422). |
| **Go-live** | A2 deleted. |
| **Portal** | `/users/me/admin-context` now returns `can_see_seah` + `can_configure_sensitive`; `AuthProvider` stops deriving case access from role keys (it cannot see cast membership) and takes the server's answer; `ProjectEditor` passes the **configure** capability to the workflow editor. |
| **Tests** | `tests/ticketing/test_sensitive_workflow_access.py` (11 tests). `test_ticket_access_matrix.py` (`SEAH_ALLOW` no longer contains `super_admin`) and `test_pii_boundary.py` (masking asserted through a cast member; admin gets 403) updated to the new rule. Suite: **660 passed, 5 skipped**. |

**Not renamed yet** — the code still says `workflow_type='seah'` / `is_seah` / `workflow_track`. The *behaviour* is the decision's; the vocabulary follows in the rename below.

### Outstanding

**Model + migration** `models/workflow.py`, `models/ticket.py`, admin scope model · a migration mapping `workflow_type='seah'` → `is_sensitive=true`, keeping the old column readable for one release · then `services/seah_visibility.py`, `lib/trackFilter.ts`, `lib/labels.ts` rename with it.
**Reports / retention** `services/quarterly_report.py` (`include_seah` → `include_sensitive`), `report_export.py`, `pivot_table.py`, `archiving_policy.py`.
**Notifications** `tasks/notifications.py` (`should_notify(workflow_slug=…)` still keyed by track slug).
**Roles** `constants/grm_role_catalog.py`, `role_archetypes.py`, `models/user.py` (`SEAH_ROLES` legacy fast-path retires — cast membership replaces it).
**Workflow editor** the **Sensitive** checkbox itself (mocked in `ui/06`, not built).
**Backend** the real `POST /api/grievance/{id}/reveal` policy endpoint (§4).
**Docs** docs/seah/ still describes the track model.
