# Follow-up — StepCast: full "why-excluded" reasons + role bilingual (`_ne`)

> **Status:** open (unstarted) · **Owner:** settings/workflows · **Priority:** low (v1 ships the derivable subset; nothing is broken)
> **Origin:** built `StepCast` (the first-class 4-slot step cast — DESIGN §4.3 / build-sheet `frame-04.md`) during the manual review that reached parity on the *step* cast. Two of the wireframe's affordances were consciously **not** built because they are not derivable on the client today; `frame-04.md` §6 flagged both as GAPs and recommended the v1 subset. This file **is** the ticket for the remainder.

## What shipped (for context)

`components/settings/workflows/StepCast.tsx` — the step editor now presents the step as an explicit cast (**Handles it / Oversees / Kept informed / Can view** = `assigned_role_key` / `supervisor_role` / `informed_roles[]` / `observer_roles[]`), states that every slot is a **role** (removing the role-vs-position ambiguity now that a Positions surface exists), shows cardinality + plain-language notes, greys **wrong-track** roles with the reason, and shows a read-only escalation-target line ("next step's Handles-it"). Data plumbed by adding `scope` to `WorkflowRoleOption` and passing the *unfiltered* catalog + track + next-step handler down through `WorkflowsTab → WorkflowEditor → StepForm → StepCast`.

The underlying model was already current and load-bearing — the org-chart refactor **kept** `supervisor_role` and demoted the position `reports_to_*` line to HR-only (`DECISION-project-participants-and-supervision.md` §5). So this was a UI-parity gap, not a data-model change.

## Deferral 1 — the other two "why-excluded" reasons (needs a backend endpoint)

The wireframe's `Not shown (N)` list carries three reasons; only **one** is client-derivable:

| Reason | Derivable? | Why |
|---|---|---|
| `wrong track` | ✅ shipped | client-computes from the role's `workflow_scope` via `lib/trackFilter` |
| `owned by another office` | ❌ | owner-scoped roles are filtered out **server-side** by `apply_catalog_scope` (`users.py`), so the client never receives them — it cannot grey-and-explain what it never got |
| `bound at L3 only` | ❌ | a per-step business rule with **no endpoint** to express it |

**To close:** add a picker endpoint that returns in-scope **and** out-of-scope roles, each flagged with a machine reason (`wrong_track` / `out_of_owner_scope` / `bound_elsewhere`), so `StepCast` can render the full greyed list. Then extend `renderOffTrack()` to key off the reason rather than assuming wrong-track. Until then, v1 greys the derivable case only — which is `frame-04.md` §6 GAP1's recommended path (b).

## Deferral 2 — role labels are English-only (no `_ne`)

`ticketing.roles` has **no `display_name_ne`** column (`models/user.py`), and `RoleResponse` omits it. `StepCast` (and every role picker) therefore renders role labels EN-only; `<Bilingual>` would degrade to EN for roles. `frame-04.md` §6 GAP3. **To close:** add `display_name_ne` to the role model + `RoleResponse` + the seed catalog, then wire `<Bilingual>` on role labels in the cast and the role catalog. This is part of the broader RB-1 i18n effort, not StepCast-specific.

## Explicitly out of scope (not debt from this change)

The 2026-07 settings redesign also specified a larger `WorkflowsRolesFlow` container and a separate `StepRoleBinder` sub-component. Those are a broader restructure of the whole workflows-cluster IA; this change delivered the **step cast** piece (`StepCast`) inside the existing `StepForm`/`WorkflowEditor`, which is the part the manual review was about. `NotificationRules` already exists as `WorkflowNotificationsPanel`.
