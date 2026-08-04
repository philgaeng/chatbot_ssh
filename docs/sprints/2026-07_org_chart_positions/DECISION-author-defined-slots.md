# DECISION — the project type is the template: it names the slots, the project fills them

**Status:** decided 2026-08-04 (Philippe). Ready to build.
**Supersedes:** [`DECISION-project-participants-and-supervision.md`](DECISION-project-participants-and-supervision.md) (2026-07-10) on how a project's organizations are modelled — §4.
**Related:** [12 §6.2](../../ticketing_system/12_workflows_configuration.md) · [13 §3/§5A/§5B/§7](../../ticketing_system/13_projects_and_packages.md) · [14 platform settings](../../ticketing_system/14_platform_settings.md) · [followup §6](followups/workflow-stream-vocabulary-and-intake-route-labels.md)

---

## 1. The decision

**A project type is a complete, reusable template owned by a top-level organization.** It binds the workflows a project runs, names the organizations it must have, and routes categories. Creating a project is: **pick the organization → pick one of its types → allocate the remaining organizations.** Everything else comes from the template.

**A typed project cannot deviate from its type.** If the configuration is wrong, you fix the type — not the project. (Q4, 2026-08-04.)

### Why this is the right layer
It is the only place that can express *"a donor-funded road project has a sensitive workflow; a municipal one doesn't"* once, for every project of that kind. And it lets a technocrat use the words on their contract — "Executing Agency", "Ward Office", "Concessionaire" — instead of the words we picked.

## 2. What already exists

`ticketing.project_types` is ~90% of this, built and unused:

```python
workflow_bindings   # [{display_label, workflow_id, is_default, classifications, intake_route, sort_order}]
actor_roles         # [{key, label, description, required, required_package, scope}]
routing_org_role    # WHICH named role anchors the ticket — an author-chosen key from actor_roles
```

`required_project_role_keys()` / `package_required_role_keys()` already drive go-live **B1** / **B3**. What is missing: the **authoring UI** (`ProjectTypesTab` only counts entries), **org ownership**, the **project screens consuming it**, and un-deprecating the catalog.

`routing_org_role` matters: the anchor is **a key the author picks from their own catalog**, so nothing is hardcoded as "the implementing agency" and no boolean flag is needed.

## 3. Model changes

### 3.1 Project types belong to a top-level organization
```
ticketing.project_types
  owner_organization_id  String(64)  → ticketing.organizations   # the top-level org (Q2)
```
- Browsing: **New project** asks for the organization first, then offers only that organization's types (plus any global ones seeded by `super_admin`).
- Authoring: **`org_admin` may author types within its own subtree** (Q3); `super_admin` may author any. Same gate as workflow authoring, since a type is mostly a bundle of workflows.

### 3.2 Jobs at a level stay on the workflow
```
ticketing.workflow_steps
  tier_labels     JSON  {tier: {label, description}}   # the author's name for each job
  required_tiers  JSON  ["supervisor", "informed"]     # actor always required, never listed
```
These are per-level and belong to the workflow, not the template. They are the **only genuinely missing model** in this decision — documented in [12 §2](../../ticketing_system/12_workflows_configuration.md), depended on by [13 §5A](../../ticketing_system/13_projects_and_packages.md), and absent from every migration, model, schema and endpoint.

### 3.3 The organization slots keep their existing store
Filled values live in **`project_organizations` (`organization_id`, `org_role`)** — deprecated by the July decision, never dropped, now primary again. `org_role` holds the type's `actor_roles[].key`.

## 4. What this supersedes

[DECISION 2026-07-10](DECISION-project-participants-and-supervision.md) replaced the catalog with two fixed concepts — `implementing_agency_org_id` + `project_donors` — because routing and the donor guardrail needed a *known* organization. Re-checked against the code, **neither reason holds**:

- **Routing never used it.** `workflow_engine._scope_candidates`: *"organization_id is accepted for call-site compatibility but is not used to filter candidates — assignment is by workflow role + jurisdiction only."* `ticket.organization_id` feeds a list filter, report columns and counts. `resolve_ticket_organization()` already resolves it through `routing_org_role`.
- **The donor guardrail is just a required slot.** The author puts the named organization role in the **last level's kept-informed** job and marks it **required**; the generic check enforces it. **A5 is deleted, not reimplemented.**

`implementing_agency_org_id` and `project_donors` become **legacy reads** for pre-existing projects and stop being written. Dropping them is later cleanup.

## 5. Creating a project (the flow this buys)

1. **Organization** — pick the top-level organization. It fills the type's `routing_org_role` slot automatically, so the creator never allocates it by hand.
2. **Type** — pick from that organization's types. The project inherits its workflows, category routing, and organization slots.
3. **Allocate the remaining organizations** — one picker per named slot; required ones block go-live.
4. **Locations** and **staffing** — still per-project, and still go-live blockers. A template cannot know which district or which people.

Picking a type removes the **configuration** from project creation; it does not build the project. Locations and officers are the work that remains, and they are the work that actually needs local knowledge.

## 6. Categories and intake — today one chatbot, tomorrow several

Category→workflow routing lives on the type (`workflow_bindings[].classifications`) — already built.

The **category catalog itself** stays global for now (`public.grievance_classification_taxonomy`, owned by the chatbot side and what the LLM classifies against). But a top-level organization will eventually run **its own chatbot and its own intake routes** (Q1), so new code must not assume a single global catalog:

- Resolve the category catalog and the intake-route catalog **for the owning organization**, through one accessor that today returns the single global list.
- Keep `intake_route` values opaque to ticketing (`story_main` strings) so a second chatbot can define its own.

That is the whole forward-compatibility cost today: **one accessor, no schema change.** The per-organization chatbot/catalog split is a separate build when a second chatbot exists.

## 7. Go-live after this change

| Was | Becomes |
|---|---|
| A3 implementing agency set | *(gone)* — covered by required organization slots |
| A5 donor informed at last step | *(gone)* — the author marks that slot required |
| B1 required project actors | **required organization slots filled** (same check, author-defined set) |
| B3 required package actors | unchanged in shape (per-lot required slots) |
| A4 required cast tiers staffed | **now real** — reads `required_tiers`, which finally exists |

## 8. Consequences to build deliberately

- **The Grievance workflows section becomes read-only on a typed project** (Q4), with one line saying where to change it and a link to the type. The card layout stays — it is now a summary, not an editor. Untyped/legacy projects keep editing inline.
- **Partner organizations renders the type's `actor_roles`** — one block per named slot, required ones marked, the anchor slot pre-filled from step 1.
- **A type in use is frozen** (2026-08-04). The moment a type is bound to **any** project it becomes read-only — no edit, no delete. This is what stops one click from re-configuring twenty live projects, and it means the answer to "what does this project run?" never changes underneath anyone.
  - **Editing a bound type is offered as "Use as template"** — clone it under a new name, in the same owning organization, and edit the copy freely. The original and its projects are untouched.
  - **Frozen means the configuration**: workflows, organization roles, category routing, `routing_org_role`, labels. `is_active` and `sort_order` stay editable — retiring a type from the New-project list is not a configuration change.
  - **Bound = any project row referencing the type**, active or not. A deactivated project still runs on its type.
  - **Consequence to accept:** an existing project cannot be moved forward to the improved copy. Its config is frozen with its type — deliberately. The only way to move it would be an explicit *change this project's type* action, which re-applies the new template. **Not in this build** — it needs a diff-and-confirm flow of its own (what gets added, what gets orphaned), and it is the one thing that could silently restaff a live project.

## 9. Build order

1. **Model** — migration: `project_types.owner_organization_id`, `workflow_steps.tier_labels`, `workflow_steps.required_tiers`. Schemas + TS types.
2. **Type authoring UI** — workflows bound, organization roles (label · description · required), category routing, `routing_org_role` picker. `org_admin` scoped to subtree. **Frozen when bound** (§8): the editor becomes a read-only summary with **Use as template**, and the API refuses config writes to a bound type (409, not a client-side disable).
3. **Step editor** — name/description/required per job ([`ui/06`](../../ticketing_system/ui/06_workflows_step_cast_editor.html) mocks it).
4. **Consumption** — staffing reads `tier_labels`/`required_tiers`; Partner organizations renders `actor_roles`; Grievance workflows goes read-only when typed.
5. **Creation flow** — organization → filtered types → create; anchor slot pre-filled.
6. **Go-live** — delete A3/A5; B1 reads the type's required set; A4 reads `required_tiers`.
7. **Docs** — 02/03/04/12/13/14, amend the July DECISION, close followup §6.

Steps 1+3 (the workflow half) are independent of 2+5 (the type half).
