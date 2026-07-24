# Phase 1 reconciliation — tier-derived permissions vs. the current action gates

> Written during implementation of `DESIGN-cast-model-and-package-staffing.md` §7 Phase 1.
> The spec asks us to "reconcile with the current action gates … decide per-capability
> whether it's assignment-based or tier-permission-based and document it." This is that record.

## The finding that shapes Phase 1

**No request-time gate reads a role's `permissions[]`.** A full sweep of `ticketing/` found
the `Role.permissions` JSON is read only by the role-catalog CRUD in
`ticketing/api/routers/users.py` (list/create/update) — never by an authz gate. Enforcement
runs on three orthogonal axes, none of which consult `permissions[]`:

1. **Assignment identity** — `ticket.assigned_to_user_id == user` (+ admin flag).
2. **Admin plane** — `admin_scopes` (tier + `workflow_track`), entirely separate.
3. **Jurisdiction scope** — `officer_scopes` rows → ticket visibility + auto-assign.

So "tier-derived permissions" largely *formalises* what the runtime already does. There is
no request-time permission check to rewrite; the migration target is the CRUD/validation
sites (retired in Phase 5 with the rest of the archetype apparatus).

## Per-capability decision (which axis enforces each capability)

`TIER_PERMISSIONS` (in `ticketing/constants/tiers.py`) is the **source of the capability
definitions**. The *gating axis* differs per tier, and that is intentional:

| Capability | Tier(s) that define it | Enforcing axis | Gate today |
|---|---|---|---|
| `tickets:read` (view) | all four | **visibility** (`require_ticket_access`) | `ticket_access.py` |
| `tickets:note` | actor, supervisor, participant | **visibility** (any reader may note) | `actions.py` — NOTE not in `ASSIGNMENT_REQUIRED` |
| `tickets:acknowledge` | actor, supervisor | **assignment identity** (the assignee) | `actions.py` `ASSIGNMENT_REQUIRED` |
| `tickets:escalate` | actor, supervisor | **assignment identity** | `actions.py` `ASSIGNMENT_REQUIRED` |
| `tickets:resolve` | actor, supervisor | **assignment identity** (Actor) **or tier membership** (Supervisor) | `actions.py` `_can_resolve_ticket` |
| `tickets:reply` | actor, supervisor | **assignment identity** | `actions.py` `reply_to_complainant` |
| `tickets:reassign` | supervisor (default) | **tier membership** (Supervisor) / assignee-self when no supervisor | `crud.py` `_can_assign_ticket` (TP-12) → Phase 4 chain |

**Rule of thumb:** the **Actor** works one specific ticket, so Actor capabilities gate on
*being the assignee of that ticket* — not on merely holding the Actor role_key (many officers
share an Actor pool; only one is assigned). **Supervisor** oversight is pool-wide, so
Supervisor capabilities gate on *tier membership* (holding the step's `supervisor_role`).
**Participant/Observer** are informational, gated on *visibility*.

## What changed in code (behaviour-preserving)

- Added `ticketing/constants/tiers.py` (`TIERS`, `STEP_FIELD_BY_TIER`, `TIER_PRECEDENCE`,
  `TIER_PERMISSIONS`) and `ticketing/services/tier_permissions.py` (derivation +
  `capabilities_for_user_on_ticket`, which folds the three axes into one honest answer).
- Re-expressed the two tier-membership branches through the resolver, with **identical
  observable behaviour** (Supervisor-tier membership == `supervisor_role in role_keys`):
  - `actions.py::_can_resolve_ticket` — supervisor branch.
  - `crud.py::_can_assign_ticket` — supervisor branch + the assignee-Actor self-serve branch.

## Sequencing note (not a deferred debt — completed later in this same run)

- **"Stop writing new per-role permissions"** (§7 Phase 1): the *tier* is now the documented
  source of truth. The literal removal of the permission-writing paths
  (`permissions_for_archetype` / `validate_operational_permissions` in `create_role`/
  `update_role`) happens in **Phase 5**, when the whole custom-role create/edit surface and
  the archetype apparatus are removed. Doing it in Phase 1 would strand `test_roles_crud`
  (a Phase 5 rewrite target) and the still-live Roles tab. `roles.permissions` stays
  **readable** throughout the transition, exactly as the spec asks.
