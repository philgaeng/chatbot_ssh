# Follow-up — workflow "stream" vocabulary, intake-route labels, and the go-live severity gap

**Logged:** 2026-08-02 (during the Grievance-workflows screen redesign — [`ui/04`](../../../ticketing_system/ui/04_projects_packages_redesign.html), [13 §5B](../../../ticketing_system/13_projects_and_packages.md)).
**Severity:** low–medium — no correctness bug; stale spec vocabulary, jargon in user-facing strings, and one spec-vs-code gap on go-live severities.

## What triggered it

The Projects mockup showed **one row per "intake stream"** (safeguards · hazards · CA · SEAH) with a fixed slot vocabulary. That model **no longer exists in the code** — migration `c5e7f9a1_workflow_classifications` dropped `project_workflows.slot_key` and moved to `display_label` + `intake_route` + `classifications` + `is_default`. The mockup was following **doc 12**, which still described the dead model; "stream" is also not a word in the copy guide ([ui/05 §4](../../../ticketing_system/ui/05_ui_copy_style.md)).

**Fixed in this pass:** doc 12 §1/§2/§3/§4/§6/§7/§8/§11/§12 reconciled to as-built; doc 13 §1/§2/§5/§6 + new §5B; the mockup rebuilt (named cards, default first, categories merged onto the card, Classifications section removed).

## Open items

### 1. `INTAKE_ROUTE_CATALOG` labels carry jargon (user-facing)
`ticketing/constants/workflow_routing.py`:

| Key | Ships as | Should read (ui/05 §2) |
|---|---|---|
| `new_grievance` | "File a grievance (safeguards GRM)" | "File a grievance" |
| `road_hazard_grievance` | "Report a road hazard (fast path)" | "Report a road hazard" |
| `seah_intake` | "SEAH intake" | "SEAH report" |

These strings surface in the project editor's **Chatbot menu** picker, so they are governed by the copy guide. Ideally they mirror the chatbot's own menu wording — check `story_main` before renaming.

### 2. ~~Delete the "Classification coverage" go-live check~~ ✅ **done 2026-08-02**
Deleted, along with `workflow_routing.uncovered_classifications()` (its only caller). The `A4` ID collision with doc 13 §7 is gone. The go-live check copy was de-jargoned in the same pass — no "binding", "catch-all", "actors", "step", "scope", or `L1`/`L2` shorthand on screen; the panel says "Accepting grievances" rather than "Tickets OK". Original note below.


`project_go_live.py` emits check **`A4` "Classification coverage"** (warn) from `uncovered_classifications()`. A category no card claims routes to the **default** — that is the default's whole job — so an uncovered category is not a finding. Two problems:
- The check is noise on every project that doesn't enumerate all categories.
- Its ID **collides** with doc 13 §7's `A4` (required cast tiers staffed).

Fix: drop the check (and `uncovered_classifications()` if unused elsewhere), or keep it purely informational under a non-colliding ID.

### 3. Go-live is not binary yet (doc 13 §7 is target, not as-built)
Q-GL-1/2 locked "every check is a **Blocker** or **Optional**, no warning tier". As-built, `project_go_live.py` keeps `severity` ∈ `block` / `warn` / `info` and computes:

```python
_ACTIVATION_BLOCK_IDS = {"A3", "A5", "C5", "R1"}
```

So four checks the spec calls Blockers ship as warnings and **do not** stop activation:

| ID | Check | Spec | As-built |
|---|---|---|---|
| A1 | Default workflow chosen | Blocker | warn |
| D1 | ≥1 project location linked | Blocker | warn |
| E1 | Name + short code set | Blocker | warn |
| A2 / C4 | SEAH workflow published + L1 staffed | Blocker (if SEAH) | warn |

Fix: promote those four to blocking IDs, collapse `severity` to blocker/optional, and re-check the UI rail's blocker count.

### 4. No guard against a **sensitive workflow as the default**
`project_workflows.replace_project_workflows()` has **no SEAH special-casing**: a `workflow_type='seah'` workflow can be marked `is_default`. Consequences: every unmatched grievance enters the sensitive track (invisible to standard officers), and `_sync_legacy_columns()` writes it into `projects.standard_workflow_id`. Add a 422 (or at minimum a go-live blocker).

### 5. ~~Open design question~~ → **DECIDED 2026-08-02: [`DECISION-sensitive-workflows.md`](../DECISION-sensitive-workflows.md)**
**Decided as recommended below, plus:** the quarterly report **excludes** sensitive cases, and — the admin-track question — **configuring a sensitive workflow grants no access to its grievances or PII**, for any admin tier including `super_admin`. Access is **cast-only**. `can_see_seah_extended()` loses its `super_admin`, `adb_hq_exec`, and `workflow_track=='seah'` branches. Code change outstanding (DECISION §7); note §4 above is now part of it — the reveal endpoint's policy check **does not exist** (`clients/grievance_api.py` always returns `granted: true`), so today any admin who can see a sensitive case can reveal its PII.

The original question and analysis, kept for the record. The design intent: SEAH is an ordinary optional workflow; the only real difference is **how PII is displayed**, which could be a property set when authoring the workflow — leaving **one** kind of default and SEAH optional like any other.

**How close the engine already is:**

| Behaviour | As-built |
|---|---|
| Ticket SEAH-ness | **Derived from the bound workflow** — `ticket.is_seah = workflow_is_seah(workflow)` (`workflow_type=='seah'`) |
| Who can see a SEAH case | **Track-derived from the cast** — `seah_visibility.py`: *"you can see a SEAH case because you are cast on a SEAH-track workflow's step"*, explicitly *not* a hardcoded role list |
| Project link rules | **None** — `project_workflows.py` treats a SEAH link like any other |

**What still hangs off the `standard` \| `seah` enum (so a "sensitive" checkbox would have to carry it):**

1. **Row-level visibility** — `tickets/crud.py` hides `is_seah` rows from non-members. This is stronger than "hide PII" and is the flag's main job.
2. **Step role isolation** — `role_scope.validate_step_roles()` rejects a standard-scoped role on a SEAH step.
3. **Admin scoping** — `org_admin.workflow_track` ∈ standard/seah; `canSeeSeah` gates workflow CRUD and the workflow picker.
4. **Notifications** — `should_notify(workflow_slug=…)` keyed by track; SEAH omits `grc_convened` + `quarterly_report` ([12 §9](../../../ticketing_system/12_workflows_configuration.md)).
5. **Reports** — `quarterly_report.include_seah` (default `False`); pivots/report export segregate.
6. **Archiving** — `seah_years_before_archiving` policy key.
7. **Donor guardrail** — SEAH-suppressed ([13 §7 A5](../../../ticketing_system/13_projects_and_packages.md)).
8. **Go-live A2** — warns when a project has **no** SEAH link, i.e. today SEAH is treated as expected-on-every-project rather than optional.
9. **Intake + vault** — separate `seah_intake` chatbot menu, `grievance_parties` + PII vault ([docs/seah/](../../../seah/)).

**Recommendation.** Keep one flag, rename its meaning: replace `workflow_type ∈ {standard, seah}` with a workflow property (e.g. `is_sensitive`) whose contract is stated once — *only officers cast on this workflow can see these grievances, and complainant PII is vault-gated* — and have items 1–7 key off it. Then SEAH is genuinely "just another optional workflow", **A2 drops** (a project needs no sensitive workflow), and the only default is **the** default. The migration is mostly mechanical; the parts needing real decisions are the **admin track** (item 3 — does `workflow_track` become per-workflow permission?) and the **quarterly report** default.

## Touch list

`ticketing/constants/workflow_routing.py` (labels) · `ticketing/services/project_go_live.py` (A4 delete, severities, `_ACTIVATION_BLOCK_IDS`) · `ticketing/services/workflow_routing.py` (`uncovered_classifications`) · `channels/ticketing-ui/components/settings/workflows/ProjectWorkflowsEditor.tsx` + `ProjectGoLivePanel.tsx` · docs 12 §7 / 13 §7.
