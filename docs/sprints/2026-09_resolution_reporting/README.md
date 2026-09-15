# Lane — Resolution reporting (September 2026)

**Audience:** internal — excluded from the public repository (lifecycle §10.4).
**Lane id:** `resolution-reporting` · **Origin:** user request (client, 2026-09-15).

> **Status:** 📋 **Specified — every question answered (Q-01 … Q-10, 2026-09-15). ⚠ `GRM-116` has an
> uncommitted implementation in the working tree that predates Q-10 and needs the rework listed in its item.**
> Tier 3 per [`engineering/06_documentation_lifecycle.md`](../../engineering/06_documentation_lifecycle.md) §1.
> **Read first:** [`DESIGN-resolution-reporting.md`](DESIGN-resolution-reporting.md), then [`QUESTIONS.md`](QUESTIONS.md).
> ⭐ **Redesigned after the first commit, before any build:** SEAH records nothing (Q-06); actions live
> in one org-scoped catalog instead of a list copied onto each workflow (Q-07, Q-08); and the owner
> chose to build the whole lane in a row, which brought catalog authoring and the duplicate-check
> agent into it (Q-09). ⭐ **Then simplified by the owner's wireframe review (Q-10):** one panel per
> workflow, **at most 8 actions**, lists copied never inherited, no global actions — every local action
> **counts as** a ministry's shared action — and **every workflow and template belongs to an
> organization** (`GRM-122`, new). Catalog screen, retire, widening and merge cut (→ `GRM-123`).

## Goal, in one sentence

**Managers can see from the Excel what was done about each case and which office did it, without
the file holding anything that names a person — and the list of actions can grow without filling up
with duplicates.**

## Why this and not what was asked

The client asked for the whole case summarised in the Excel. That would put free-text narrative —
names included — into a file that is emailed and forwarded outside every access control we have.
What managers need from it is two answers per case, and both can be picked from lists instead of
typed. DESIGN §1 has the full reasoning; use it when explaining the decision to the client.

## Items — built in this order, one PR each

| # | Item | Kind | Profile | Size | State |
|---|---|---|---|---|---|
| [`GRM-116`](01-GRM-116-resolution-actions-per-workflow.md) | Every case resolves from the same five outcomes, whatever its workflow | feature | UI feature +DATA +CONTRACT +SENSITIVE | L | `ready` — ⚠ in-progress build needs Q-10 rework |
| [`GRM-122`](06-GRM-122-workflow-organization.md) | An admin cannot say which organization a workflow belongs to | feature | UI feature +CONTRACT +SENSITIVE | S | `blocked` — `GRM-116` |
| [`GRM-117`](02-GRM-117-resolution-actor.md) | A resolved case does not record which office took the action | feature | UI feature +CONTRACT +SENSITIVE | M | `ready` — after `GRM-116` (same form) |
| [`GRM-118`](03-GRM-118-report-resolution-columns.md) | The Excel says how a case was classified, not what was done or by whom | feature | Backend feature +CONTRACT +SENSITIVE | S | `blocked` — `GRM-116`, `GRM-117` |
| [`GRM-119`](04-GRM-119-resolution-catalog-authoring.md) | The resolution-action catalog can only grow by a migration | feature | UI feature +CONTRACT +SENSITIVE | M | `blocked` — `GRM-116` |
| [`GRM-121`](05-GRM-121-duplicate-check-and-promotion.md) | Nothing stops an admin creating the same resolution action twice | feature | UI feature +CONTRACT +SENSITIVE | S | `blocked` — `GRM-119` |

**Why this order.** `GRM-116` creates the catalog everything else reads, and gives every workflow an
organization. `GRM-122` comes straight after: until it ships, a platform admin's new workflow has no
organization and cannot be published. `GRM-117` edits the same form and `RESOLVE` branch as
`GRM-116`, so it follows rather than runs alongside. `GRM-118` reads what both write. `GRM-119` and
`GRM-118` are independent — either may go first. `GRM-121` puts the check in `GRM-119`'s dialog.

**Wireframe:** [`ui/08_resolution_actions_catalog.html`](../../ticketing_system/ui/08_resolution_actions_catalog.html)
— the Settings surfaces of `GRM-119`, `GRM-121` and `GRM-122` (rule 9a.4: they exist on no shipped screen). The
resolve-form changes of `GRM-116`/`GRM-117` are a delta on a shipped modal, drawn in DESIGN §4.

## Opened on the way through

| Id | Kind | What |
|---|---|---|
| [`GRM-120`](followups/seed-catalog-is-global.md) | debt | DOR's seeded catalog is global — found answering Q-08. **Narrowed by Q-10**: workflows and templates are now owned in this lane; position types, roles, project types, the delete rule and the write guards remain. Trigger: onboarding a second ministry |
| [`GRM-123`](followups/resolution-actions-merge-and-cleanup.md) | debt | Unused and duplicate resolution actions have no way out of the catalog — retire, restore and merge cut by Q-10 for admin simplicity. Safe because local actions count as shared ones, so national totals stay right. Trigger: search hard to use, a catalog past 50, or a second ministry |

## Things the spec found in the code

1. ⭐ **The resolution list already exists twice** — in Python and hand-copied in the UI
   (`lib/resolution.ts`). `GRM-116` deletes both in favour of the catalog.
2. ⭐ **A SEAH case today must pick from the general five** — including *"Complainant demand
   rejected"*. `GRM-116` removes the requirement rather than giving SEAH a list of its own.
3. ⭐ **No project on the dev DB binds a road-hazard workflow**, so today a road-hazard report
   resolves in the general workflow. Per-workflow selections make that visible; they do not paper
   over it.
4. ⭐ **The key `resolution_category` is persisted in three places** a rename would break silently —
   append-only events, saved quarterly templates, the action API. Hence Q-05: keep it.
5. ⭐ **Catalog `owner_organization_id` columns are `ON DELETE SET NULL`** — deleting an org turns its
   items global. The resolution catalog deliberately uses `RESTRICT` (DESIGN §3.3); the other kinds
   are `GRM-120`'s to decide.
6. ⭐ **`apply_catalog_scope` omits items owned *above* a scoped admin**, though the ownership rule
   makes them usable there. After Q-10 the resolution panel picks by the *workflow's* organization and
   never uses it; `GRM-122`'s template picker needs an ancestor-aware list. Whether other catalogs'
   pickers share the gap is noted on `GRM-120`, not checked.
7. ⭐ **Workflow writes check the track, not the owner** (`can_mutate_workflow`), and every seeded
   workflow is global — so a district `org_admin` can edit a workflow every ministry binds. Found in
   the wireframe review. Q-10's answer removes the global workflow instead of guarding it: every
   workflow and template gets an organization (`GRM-116`, `GRM-122`), and the resolution endpoints
   check reach on it. The step editor's older gap is logged on `GRM-120`.
8. ⭐ **Only published workflows can be bound to a project** (`validate_workflow_binding`) — which is
   what makes *"a new workflow starts empty and cannot be published"* safe: a case never meets an
   empty non-sensitive list.
9. ⭐ **The dev DB has no organization under DOR**, so every test of a *local* action must create one.

## Live specs this lane will amend

`08_ticket_resolution_and_case_summary.md` · `09_reports_and_report_builder.md` ·
`10_settings_overview.md` · `11_roles_and_permissions.md` §3.3 · `12_workflows_configuration.md` ·
`04_ticketing_schema.md` · `engineering/05_frontend.md` §9a — each by the item that makes the change
true, in the same PR.
