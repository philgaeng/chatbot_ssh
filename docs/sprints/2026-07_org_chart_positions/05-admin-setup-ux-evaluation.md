# OC-06 — Admin-setup UX/UI evaluation (org → officers → workflow → projects)

> **Standing rule — keep [`PROGRESS.md`](PROGRESS.md) current.** Update it at **every commit** for this ticket: status, checklist ticks, deviations, and (for schema work) the migration-head table. A commit that changes sprint state without a matching PROGRESS update is incomplete. (Same rule in the sprint [README](README.md), [agents/README](agents/README.md), and [agents/BUILD-HANDOVER](agents/BUILD-HANDOVER.md).)

> Workstream: ux-evaluation · Branch `orgchart/oc-06-ux-eval` · **Runs FIRST** — its findings shape OC-05 and may reprioritize OC-01..04.
> This is a **doc-and-analysis deliverable**, not a code change. Output: a published evaluation report under `docs/ticketing_system/ui/` plus a triaged findings list.
> Requested explicitly by the sprint owner: evaluate *the whole UX/UI flow of setting up organizations, officers, workflows, and projects* — end to end, as a real government setup admin would experience it.

---

## 1. Why this evaluation exists

The primary users of the setup surface are **Government of Nepal civil servants with low IT literacy** (doc 16 §5.2 calls this out explicitly). The org-chart feature is being added precisely because the current flow forced admins to recreate the ministry hierarchy by minting one role per seat. Before we add *more* settings surface (OC-05), we evaluate whether the **end-to-end journey** — stand up an organization, staff it with officers, attach a workflow, launch a project — is coherent, discoverable, and hard to get wrong. The devil's-advocate reviews scored the portal's daily-driver UX at 48% and named a 4,717-line settings page as a structural risk; this evaluation is where that lands for the *admin* (not officer) journey.

## 2. Scope — the four setup journeys, as one flow

Evaluate the real path an admin takes, in order, across the settings tabs (`app/settings/page.tsx` main tabs: `org_officers`, `workflows_roles`, `projects`, `platform`):

1. **Organizations** — create org units; (post-OC-01) build the tree, set territories, CSV import. Specs: [10_settings_overview](../../ticketing_system/10_settings_overview.md), [16_org_chart](../../ticketing_system/16_org_chart_and_positions.md), [13_projects_and_packages](../../ticketing_system/13_projects_and_packages.md).
2. **Officers** — invite, assign role + jurisdiction/scope, (post-OC-03) pick a position that pre-fills. Specs: [07_officer_management_and_assignment](../../ticketing_system/07_officer_management_and_assignment.md), [11_roles_and_permissions](../../ticketing_system/11_roles_and_permissions.md). Code: `OfficersTab.tsx`, `OfficerModals.tsx`, `OfficerJurisdictionForm.tsx`, `OfficerScopeTable.tsx`; invite backend `users.py:1249-1317`.
3. **Workflows & roles** — configure the multi-stream workflow slots, roles, step→role bindings. Specs: [12_workflows_configuration](../../ticketing_system/12_workflows_configuration.md), [11_roles_and_permissions](../../ticketing_system/11_roles_and_permissions.md). Code: `WorkflowsTab` (inline, `page.tsx:1904`), `RolesTab` (inline, `page.tsx:397`).
4. **Projects & packages** — create a project, attach orgs/packages, staff actor roles, go-live. Specs: [13_projects_and_packages](../../ticketing_system/13_projects_and_packages.md), [`features/settings/settings_tab_projects_and_seah_contact_centers.md`](../../ticketing_system/features/settings/settings_tab_projects_and_seah_contact_centers.md). Code: `ProjectStaffingSection.tsx`, `ProjectOfficerModal.tsx`, `ProjectGoLivePanel.tsx`, `project_go_live.py`.

Evaluate the **seams between** these as hard as the tabs themselves — the failure mode for low-IT-literacy users is usually "I finished tab A, now what?", not a single broken screen.

## 3. Method (what the agent must actually do)

1. **Walk the flow on the running stack** (`docs/deployment/DOCKER.md`, bypass-auth mode) as each admin persona — `super_admin`, `org_admin` (standard), `org_admin` (seah), `project_admin`. Do a cold-start setup: empty-ish system → one org tree → officers → workflow → a launched project. Screenshot or note each step. Do **not** rely on reading code alone; experience the clicks.
2. **Map the journey** as a step-by-step diagram: every screen, every required field, every navigation jump between tabs, every point where the admin must remember a value from a previous tab (e.g. an org id, a role key, a location code).
3. **Score each journey** on: discoverability (can they find the next step unaided?), guidance (labels/help/empty-states for a non-technical user), error prevention (can they create an invalid/orphaned state — org with no parent, officer with no scope, workflow step bound to a non-existent role?), reversibility (can they undo/fix?), and Nepali readiness (is the surface translatable / are there English-only traps?).
4. **Persona & permission check:** verify each admin tier sees exactly the surface doc 11 §admin-ladder and doc 16 §7 grant — flag any tab/action visible to a tier that shouldn't have it, or hidden from one that should (a UX *and* a security finding).
5. **Cross-reference the known structural risks:** the 4,717-line settings page, the inline `WorkflowsTab`/`RolesTab`/`AdminAccessTab` vs the extracted `components/settings/*` (inconsistent architecture the admin never sees but that predicts bugs), and the location-code dialects noted in the specs review.
6. **Ground every finding in file:line or a screenshot** — this evaluation must be actionable by OC-05, not vibes.

## 4. Deliverable

Publish `docs/ticketing_system/ui/03_admin_setup_flow_evaluation.md` containing:

- **Journey map** (the 4-in-1 flow diagram with every inter-tab jump marked).
- **Scored findings table**: `id | journey | severity (blocker/major/minor) | finding | evidence (file:line/screenshot) | recommendation | owner (OC-05 / backlog / new-ticket)`.
- **Top-5 friction points for a low-IT-literacy admin**, ranked, each with a concrete fix.
- **Orphaned-state catalogue**: every invalid end-state the UI currently permits (and whether OC-01..04's server-side validation already closes it).
- **Nepali/i18n readiness note** for the admin surface (the specs review flagged the portal has zero i18n scaffolding — say concretely what that means for these four tabs).
- **A short "does the org-chart feature actually help?" verdict** — the whole premise of doc 16 §5.2 is that positions make officer setup *one comprehensible action*; evaluate whether the OC-05 design delivers that or just adds another tab.

## 5. Feed-forward (how this changes the rest of the sprint)

- File each **blocker/major** finding as either an OC-05 acceptance item (if it's UI) or a new backlog ticket (if it's backend/schema), recorded in [`PROGRESS.md`](PROGRESS.md) → Deviations/Findings.
- If the evaluation finds the invite pre-fill design (OC-03/OC-05) would *not* actually simplify the flow for the target user, **raise it before OC-05 starts** — cheaper to adjust the design than the built UI.

## Constraints

- **No code changes.** This ticket produces documentation and screenshots only. Fixes are other tickets.
- Evaluate the **as-built** state (plus the OC-01..04 additions where already merged) — not an idealized spec. Where spec and built UI disagree, that disagreement is itself a finding.
- Keep the report honest and adversarial in the devil's-advocate house style: real friction, ranked by user impact, strengths stated so the criticism is credible.

## Done means
`docs/ticketing_system/ui/03_admin_setup_flow_evaluation.md` published; findings table complete with evidence and owners; blockers/majors triaged into OC-05 or backlog in [`PROGRESS.md`](PROGRESS.md); the "does org-chart help?" verdict recorded before OC-05 begins.
