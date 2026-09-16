# Build sheet — Frame 04 · Workflows & roles (guided flow / step cast)

> RB-0 deliverable. Grounds wireframe Frame 04 + atlas Surface 04 in the NOW-REAL API. Direct input to RB-2/3/4.
> Spec: DESIGN §4.3 (step cast) + §4.4 (catalog) + §7.B2/B3/B4 (authoring, SLA, template, link). IA: Workflows & roles (Tab 2). Data owner: **SH-2** (step→role validation), **SH-7** (org-scoped catalog picker), workflows model.

---

## 1. Visual ref

- **Wireframe:** `settings-wireframes.html` Frame 04 (lines 792–898). **Atlas:** `settings-state-atlas.html` Surface 04 (lines 485–534).
- **Layout:** One merged surface `workflow → steps → bind role`. Header = workflow name + track chip ("Standard grievances") + Draft/Published badge + `Manage roles →` cross-link (to Frame 08). A **Levels** strip (chips 1–4 + `+ Add a level` + drag-reorder + ⋯-remove). The selected step renders a **cast** grid of 4 slots: **Handles it** / **Oversees** / **Kept informed** / **Can view**, each with a plain-language note ("owns & works the case", "escalate / reassign", "view + notes", "read-only"). Below the cast: **Time limit before escalating** (SLA) + read-only escalation target ("goes up to the next step's Handles-it people"). A **valid-only role picker** lists in-track roles ticked, then a `Not shown (N)` divider with greyed rows each carrying a **why-excluded** reason ("wrong track — SEAH", "bound at L3 only", "owned by Jhapa district — not here").
- **States (atlas 04):** _empty_ (no roles for track → "No Standard-track roles yet · Create a role" cross-link, not a bare select); _error_ (publish rejected wrong track → ErrorNotice names offending step + re-opens it); _draft_ ("Not published — won't appear on any project yet · Publish"); _bilingual_ (role labels EN / देवनागरी, "was site_safeguards_focal_person"). Variants: clone-a-template cards (Standard GRM 4-level / SEAH) as the primary new-workflow path.

---

## 2. Component subtree (DESIGN §3, `components/settings/workflows/`)

```
WorkflowsRolesFlow            [new]      merged guided-flow container (D5, S1) — wraps List+Editor+Catalog+Notifications sub-nav
  WorkflowList                [extract]  ← page.tsx WorkflowsTab (1910) list/search/template-cards/new-modal
  WorkflowEditor              [extract]  ← page.tsx WorkflowEditor (1374) — header (Draft/Published), Levels strip, publish/archive
    StepEditor                [extract]  ← page.tsx StepForm (766–1091) — cast grid + SLA + escalation-target display (B2)
      StepCast                [new]      the 4-slot cast (Handles it/Oversees/Kept informed/Can view) — §4.3
        StepRoleBinder        [new]      valid-only picker + "why excluded" per slot (S1, F2-surface, D5)
  RoleCatalog / RoleEditor    [extract]  cross-linked via "Manage roles →" → Frame 08
  NotificationRules           [new]      per-track grid → Frame 09
```

**Replaces (god-file):** `WorkflowsTab` (page.tsx:1910), `WorkflowEditor` (1374), `StepForm` (766), `workflowTrackOf` (1092), `wfRoleOptions` memo (1975–1984). The cast today is buried inside `StepForm` as flat tier inputs (supervisorRole / informedRoles[] / observerRoles[], page.tsx:791–795) — StepCast makes the four-slot reality first-class.

---

## 3. Governing interaction rules

**Cast ↔ schema (as-built `ticketing/models/workflow.py:72-83`; verified in StepPayload `lib/api.ts:652-665`):**

| UI slot | Field | Cardinality | Notification tier (§4.5) |
|---|---|---|---|
| Handles it | `assigned_role_key` | one, **required** | `actor` |
| Oversees | `supervisor_role` | one | `supervisor` |
| Kept informed | `informed_roles[]` | many | `informed` |
| Can view | `observer_roles[]` | many | `observer` (silent) |

- **Only Handles it is required.** All others optional. `informed_pii_access` (bool) rides with the Informed slot.
- **Templates pre-fill the whole cast (B4).** New workflow's primary path = clone a template; `createWorkflow({clone_from_id})` copies steps + full cast + SLAs server-side (`workflows.py:257-304`). "Blank" is the advanced escape. Built-in templates: `__builtin_default_grm`, `__builtin_default_seah` (`workflows.py:44-65`).
- **Valid-only picker + track filter.** Each slot lists only roles whose `workflow_scope` matches the workflow track. Single-source the predicate in **`lib/trackFilter.ts`** (mirrors server `role_scope_matches_track`, `ticketing/services/role_scope.py:28-30`: `None`/`"Both"` valid on any track; `"Standard"`→standard only; `"SEAH"`→seah only). Kills the duplicated inline filter at `page.tsx:1978-1982` (WorkflowsTab) and `page.tsx:414-418` (RolesTab).
- **"Why excluded".** Excluded roles shown greyed with reason, not hidden. "wrong track" is client-derivable from `workflow_scope`. See §6 GAP for the other two reasons.
- **SLA + escalation (B2).** `response_time_hours` + `resolution_time_days` on the step (StepPayload). Escalation target is **read-only, derived** ("next step's Handles-it pool") — no field; the reporting line never redirects it (doc 16).
- **Publish gate.** Publishing runs SH-2 over every active step (`workflows.py:346-363`): 422 if any step missing `assigned_role_key`, or any tier role non-existent / wrong-track. Draft workflows don't appear on projects — surface "Not published · Publish" (F04 draft variant).
- **Org-scoped catalog (SH-7, §4.4).** The picker's role list is already narrowed server-side to `owner IS NULL OR owner ∈ subtree` — see `listRoles` below.

---

## 4. Concrete endpoints (real — `ticketing/api/routers/workflows.py`, roles in `users.py`; wrappers `lib/api.ts`)

| Action | Method + path | Payload | Response | Wrapper |
|---|---|---|---|---|
| List workflows | `GET /api/v1/workflows?workflow_type=&status=&is_template=` | — | `{items: WorkflowDefinition[], total}` (SEAH hidden if `!can_see_seah`; SH-7 `apply_catalog_scope`) | `listWorkflows` (593) |
| List templates | `GET /api/v1/workflows/templates` | — | built-ins + DB templates | `listTemplates` (606) |
| Get workflow | `GET /api/v1/workflows/{id}` | — | `WorkflowDefinition` (with `steps[]`, `assignments[]`) | `getWorkflow` (622) |
| Create / clone | `POST /api/v1/workflows` | `{display_name, workflow_type, description?, clone_from_id?, is_template?}` | `WorkflowDefinition` (201); owner stamped via `catalog_owner_for` | `createWorkflow` (618) |
| Update meta | `PATCH /api/v1/workflows/{id}` | `{display_name?, description?, workflow_key?}` | `WorkflowDefinition` | `updateWorkflow` (636) |
| Publish | `POST /api/v1/workflows/{id}/publish` | — | `WorkflowDefinition`; **422** SH-2 | `publishWorkflow` (640) |
| Archive | `POST /api/v1/workflows/{id}/archive` | — | `WorkflowDefinition` | `archiveWorkflow` (644) |
| Save as template | `POST /api/v1/workflows/{id}/save-as-template` | `{display_name?}` | `WorkflowDefinition` (201) | `saveWorkflowAsTemplate` (626) |
| Delete | `DELETE /api/v1/workflows/{id}` | — | 204; **409** if tickets reference it | `deleteWorkflow` (648) |
| Add step | `POST /api/v1/workflows/{id}/steps` | `StepPayload` | `WorkflowStep` (201); **422** SH-2 on write | `addStep` (667) |
| Edit step | `PATCH /api/v1/workflows/{id}/steps/{stepId}` | `Partial<StepPayload>` | `WorkflowStep`; **422** SH-2 on set fields | `updateStep` (671) |
| Delete step | `DELETE /api/v1/workflows/{id}/steps/{stepId}` | — | 204; **422** if active tickets on step (soft-delete) | `deleteStep` (675) |
| Reorder | `POST /api/v1/workflows/{id}/steps/reorder` | `{step_ids: string[]}` | `WorkflowStep[]` | `reorderSteps` (679) |
| Roles for picker | `GET /api/v1/roles?kind=operational&workflow_track=standard\|seah` | — | `GrmRole[]` (SH-7 scoped + SH-2 track filter, `users.py:154-159`) | `listRoles` (754) |
| Inline create role | `POST /api/v1/roles` | see Frame 08 | `GrmRole` (201) | `createRole` (774) |
| Project link (B3) | `PUT /api/v1/projects/{id}/workflows` | `{standard_workflow_id?, seah_workflow_id?}` (published only) | `ProjectWorkflowItem[]` (`locations.py:1400`) | `replaceProjectWorkflows` (1879) |

`StepPayload` (`lib/api.ts:652-665`): `display_name`, `assigned_role_key`, `step_key?`, `response_time_hours?`, `resolution_time_days?`, `stakeholders?`, `expected_actions?`, `supervisor_role?`, `informed_roles?`, `observer_roles?`, `informed_pii_access?`.

---

## 5. Tokens / labels contract

- **Labels not slugs (F11):** every role shown via `RoleLabel` → catalog `display_name` (`lib/labels.ts` for step_key / track glosses). Never `site_safeguards_focal_person`. Atlas 04 "was" hint documents the mapping.
- **Single-source track filter:** `lib/trackFilter.ts` replaces `page.tsx:414-418` + `1978-1982` (and mirrors server `role_scope.py`). Every slot picker + RolesTab filter consume it.
- **Friendly errors:** publish-422 ("Step 2 is bound to a SEAH role, but this workflow is Standard") + delete-409/422 routed through `lib/user-messages.ts formatUserFacingError` via `ErrorNotice`; the notice names the offending step and re-opens that slot (atlas 04 error tile).
- **Colors via `design-tokens.ts`:** track chips (blue Standard / red SEAH) and Draft/Published `SeverityBadge` — no raw Tailwind color literals, no `ORG_ROLE_COLORS` (banned purple/indigo/orange/teal at `page.tsx:280-290`), no emoji.
- **`<Bilingual>`** on role labels where `_ne` present (EN fallback, never fabricate) — see §6 GAP (roles carry no `_ne` yet).
- **Track glossed** as "Standard grievances / SEAH" with a one-time tooltip (§7.C); "acts as" kept and glossed.

---

## 6. Data owner + open gaps / risks

**Owners:** step→role referential+track validation = **SH-2** (`ticketing/services/role_scope.py`, called from `workflows.py:355,487,544`). Org-scoped catalog picker = **SH-7** (`admin_access.apply_catalog_scope` / `catalog_owner_for`, `workflows.py:134,250` + `users.py:154`). Workflow/step CRUD = workflows model.

**GAPs / risks for RB-2/3/4:**
1. **`[GAP]` "why excluded" reasons are not all derivable.** "wrong track" is client-computable from `workflow_scope`. But **"owned by another office"** roles are *filtered out server-side* by `apply_catalog_scope` (`users.py:155`) — the client never receives them, so it cannot grey-and-explain them. And **"bound at L3 only"** is a per-step business rule with no endpoint. To render the wireframe's full `Not shown (N)` list, either (a) add a picker endpoint that returns in-scope + out-of-scope roles flagged with a reason, or (b) scope the "why excluded" UI to the derivable "wrong track" case only and drop the owner/level reasons. Recommend flagging to product; safest RB path = (b) for v1.
2. **`[GAP]` No escalation-target endpoint.** The read-only "goes up to the next step's Handles-it people" line is derived client-side from step order; fine, but note there is no server field/route confirming it.
3. **`[GAP]` Role bilingual (`_ne`).** `ticketing.roles` has **no `display_name_ne`** (model `user.py:57-76`; RoleResponse omits it). The atlas bilingual tile ("Site Safeguards Focal / स्थल सुरक्षा फोकल") cannot be populated until a `_ne` column + response field land. `<Bilingual>` degrades to EN-only for roles meanwhile.
4. **Assignments vs project-link duplication.** Legacy `POST/DELETE /workflows/{id}/assignments` (org/location/project/priority tuple, `workflows.py:646-718`) coexists with the newer `PUT /projects/{id}/workflows` slot model (B3). DESIGN §7.B3 uses the latter; RB should not surface the old assignment tuple UI in Frame 04.
5. **Draft template steps** returned by `/workflows/templates` use synthetic ids (`__builtin_*`); `openEditor` already guards them (`page.tsx:1944`) — keep that guard when extracting.
