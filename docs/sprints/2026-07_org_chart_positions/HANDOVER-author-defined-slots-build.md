# Handover — author-defined slots: what shipped, what's next

**From:** session of 2026-08-04. **Branch:** `integration/stage`, 19 commits, nothing pushed.
**Suite:** 685 passed, 5 skipped. **Stack:** dev compose, `AUTH_MODE=bypass`.

---

## 0. Read first, in this order

1. [`DECISION-author-defined-slots.md`](DECISION-author-defined-slots.md) — **the plan you are executing.** §9 is the build order; §6 is the flow it buys.
2. [`DECISION-sensitive-workflows.md`](DECISION-sensitive-workflows.md) — SEAH is a workflow property, access is cast-only. Shipped except the rename.
3. [13 §5A/§5B/§7](../../ticketing_system/13_projects_and_packages.md) · [12 §2/§6](../../ticketing_system/12_workflows_configuration.md) — the specs those decisions amend.
4. [ui/05](../../ticketing_system/ui/05_ui_copy_style.md) — **binding on every user-facing string.** The user pulled me up on this twice; check copy against §2 + §4.1 before writing it, not after.

Wireframes: [`ui/04`](../../ticketing_system/ui/04_projects_packages_redesign.html) (project console) · [`ui/06`](../../ticketing_system/ui/06_workflows_step_cast_editor.html) (step editor). The two decks in *this* folder are **superseded** — they carry banners saying so.

---

## 1. What shipped

**Project console (ui/04).** The editor is no longer one long scroll: sticky rail fusing go-live status with navigation, one section at a time, Back/Next bar. `fdcee694` · `projectSections.ts` is the single list behind rail + router + Next order.

**Grievance workflows.** Card per workflow — admin-chosen name + published workflow + routing, default first, categories on the card, no separate Classifications section. `a56226f9`, spec'd in 13 §5B.

**Partner organizations.** Dropped the deprecated actor-role table for implementing agency + donors. `21176f5c` — *and the next slice replaces this again* with the type's `actor_roles` (§3 below).

**Sensitive workflows.** SEAH became a workflow property; case access is **cast-only** — no admin tier, not `super_admin`. Closed a real hole: the PII reveal had no policy check at all. `3ad44120`, `51144f04`.

**Binary go-live.** A1/D1/E1/C4/C1 promoted to blockers, everything else `info`. A project with no default workflow and no locations can no longer activate. `a327f221`.

**Author-named jobs.** `workflow_steps.tier_labels` + `required_tiers` (migration `j6l8n0p2`) — documented since June, built nowhere. Step editor authors them; staffing shows the author's label; go-live's level gate reads `required_tiers` and names the gap with the author's word. `9cfdf2b8`, `f0e6f844`.

**Project types.** `owner_organization_id` (migration `l8n0p2r4`); a type bound to any project refuses configuration writes with 409; `POST /project-types/{key}/duplicate` is the way out. `d6ddca35`.

---

## 2. Where the build order stands

| §9 step | State |
|---|---|
| 1 Model | ✅ both migrations applied |
| 2 Type authoring UI | ⬜ **next** |
| 3 Step editor | ✅ |
| 4 Consumption — staffing | ✅ · **Partner organizations ⬜** |
| 5 Creation flow (org → filtered types) | ⬜ |
| 6 Go-live A3/A5 deletion | ⬜ **blocked — see §4.1** |
| 7 Docs | partial (12 §2 and followup §6.1 closed) |

---

## 3. Next slice

### 3.1 Type authoring UI — `components/settings/ProjectTypesTab.tsx`
Today it only *counts* entries ("3 actor roles"). It needs to edit:

- **workflow bindings** — the same shape the project screen already edits (`display_label`, `workflow_id`, `is_default`, `classifications`, `intake_route`); reuse `ProjectWorkflowsEditor`'s card layout rather than inventing a second one.
- **organization roles** — `actor_roles[]`: label · description · required · required_package. This is the catalog the whole decision turns on.
- **`routing_org_role`** — a picker over the type's own `actor_roles` keys. It decides which organization a ticket is stamped with; it is **not** a hardcoded "implementing agency".
- **owner** — `org_admin` authors within its subtree; `super_admin` anywhere.
- **frozen state** — when `bound_project_count > 0`, show a read-only summary + **Use as template** (`POST /project-types/{key}/duplicate`), never a disabled form. The API already returns the count and enforces the 409.

### 3.2 Partner organizations renders the catalog
`ProjectPartnersSection.tsx` currently hardcodes agency + donors. Replace with one block per `actor_roles` entry, in `sort_order`: label as heading, description as help, `required` marked, filled from `project_organizations.org_role`. The `routing_org_role` slot is pre-filled by the creation flow. Officers are still not assigned here.

### 3.3 Creation flow
`ProjectCreateModal.tsx`: organization first → only that organization's types (plus global) → create. The chosen organization fills the `routing_org_role` slot.

---

## 4. Traps — these cost me time, don't re-pay

### 4.1 Do not delete go-live A3/A5 yet
§7 says they dissolve into B1. **`ticketing.project_types` is empty and every project is untyped**, so B1 never runs and A3/A5 are the only organization gates that exist. Delete them in the same change that seeds a catalog carrying the equivalent required roles, and promote B1 back to a blocker. There is a comment at the check saying so.

### 4.2 Tests and the route snapshot live in the image
`make test-ticketing` runs pytest *inside* `ticketing_api`, which **copies** `tests/` at build time. A new test file silently doesn't run until you `build ticketing_api`. If the count didn't move, that's why.

`test_route_snapshot` fails on any new endpoint by design — regenerate `tests/ticketing/route_snapshot.txt` with the command in its own docstring, and rebuild.

### 4.3 `next build` does not catch everything
It typechecks and lints, and it still shipped `this workflow**can** see` — a missing space that JSX swallowed. **Drive the page and read the rendered text**, not the source. Playwright is installed on the host:

```python
pg.goto("http://localhost:3001/settings")
pg.get_by_text("Projects & packages", exact=False).first.click()
pg.get_by_text("Edit", exact=False).first.click()          # opens KL Road
pg.get_by_role("button", name="Project-wide staffing").first.click()
print(pg.inner_text("body"))                                # assert on THIS
```
The Workflows tab's step accordion resisted every selector I tried; verifying that half through the API was faster and tested the contract better.

### 4.4 Two staffing paths coexist and disagree
`officer_scopes` rows carry **two** `role_key` shapes: the staffing screen mints `wf:{workflow}:{step}:{tier}`, while seeds and the older invite flow use the step's **named role** — which is what go-live C1/C5 read. Before I reconciled it, the screen said "Not staffed" on every level of a project the checklist called fully staffed. `CastStaffing` now counts both and marks role-path coverage `· by role`. Anything new that reads staffing must handle both.

### 4.5 Ports, and don't sweep the working tree
UI **:3001** (`grm_ui`), API **:5002** (`ticketing_api`, `/docs` for OpenAPI), backend :5001, nginx :8080 (`/grm/` proxies to 3001). In bypass mode `curl` against :5002 works unauthenticated — that is how §5 below verifies things.

`docs/_starter_kit/` and `docs/engineering/` are the user's untracked work. **Never `git add -A docs/`** — I did, and had to reset. Stage paths explicitly.

---

## 5. Verify it still works

```bash
# author a job name + mark it required
curl -s -X PATCH localhost:5002/api/v1/workflows/00000000-0000-0000-0001-000000000001/steps/00000000-0000-0000-0001-000000000012 \
  -H 'Content-Type: application/json' \
  -d '{"tier_labels":{"supervisor":{"label":"Escalation Lead"}},"required_tiers":["supervisor"]}'

# → go-live blocks, in the author's words
curl -s localhost:5002/api/v1/projects/<id>/go-live | grep "Escalation Lead"
#   C5 fail  "No officer at: L2 (Escalation Lead)"

# "actor" is refused, not silently stored
curl -s -X PATCH …/steps/… -d '{"required_tiers":["actor"]}'      # 422

# restore afterwards — this is seeded demo data
curl -s -X PATCH …/steps/… -d '{"tier_labels":{},"required_tiers":[]}'
```

---

## 6. Open, not forgotten

- **The rename** ([sensitive-workflows §6](DECISION-sensitive-workflows.md)) — `workflow_type`→`is_sensitive`, `is_seah`→`is_sensitive`, `workflow_track`→a capability, `include_seah`→`include_sensitive`. Mechanical, wants its own pass.
- **Position-first picker** (13 §5A.2, LOCKED) — still a flat officer search. Needs an endpoint listing positions in a location scope with their holders; the positions API is per-user only. [followup §6.2](followups/workflow-stream-vocabulary-and-intake-route-labels.md).
- **`INTAKE_ROUTE_CATALOG` labels** — "File a grievance (safeguards GRM)" surfaces in the Chatbot menu picker and breaks ui/05.
- **Per-organization chatbots** — one accessor keyed by owning organization, no schema change today ([decision §6](DECISION-author-defined-slots.md)).
- **A project cannot move to an improved copy of its type.** Chosen, not deferred — read §8 of the decision before "fixing" it.
