# `GRM-119` — the resolution-action catalog can only grow by a migration

**Origin:** user request (client, 2026-09-15) · **Lane:** `resolution-reporting` · **Reported:** 2026-09-15
**Design:** [`DESIGN-resolution-reporting.md`](DESIGN-resolution-reporting.md) §3.1.1, §3.3, §6 ·
**Wireframe:** [`ui/08_resolution_actions_catalog.html`](../../ticketing_system/ui/08_resolution_actions_catalog.html) frames 1, 2, 3, 5

> **Scheduled 2026-09-15, same day it was deferred.** First logged as `debt` (the owner chose no editor
> in this lane, Q-04). The owner then decided to build the whole lane in a row (Q-09), so it is
> reclassified `feature` ([07 §2.4](../../engineering/07_work_items.md): classification is revisable).
>
> **Simplified 2026-09-15 by the owner's wireframe review (Q-10) — size L → M.** *"The level of
> complexity is too high for the future admins."* The earlier draft had two places (a panel and a
> catalog sub-tab), an ownership choice, retire/restore with replacement mapping, and four ownership
> rules the admin had to understand. **Now: one panel per workflow, at most 8 actions, and the admin
> never chooses an owner.** The one field added is *what a local action counts as nationally*, so DOR's
> statistics stay whole. The catalog sub-tab, retire, restore, widening and merge are cut — merge and
> clean-up are logged as `GRM-123`.

## Kind

**`feature`** — question 1: no live spec describes authoring resolution actions.

## Profile

| ✓ | Question | Fires |
|---|---|---|
| ✔ | Changes user-visible behaviour | `G-PRODUCT` · `G-SPEC` · `G-VERIFY` |
| ✔ | A UI surface changes shape | `G-DESIGN` — a new panel in the workflow editor and its dialog; **`.html` wireframe committed** (rule 9a.4: no shipped screen to baseline against) |
| ✗ | Schema changes | — `GRM-116` creates both tables, `counts_as_code` included |
| ✔ | PII · auth · SEAH · complainant channel · new egress | `G-SENSITIVE` — org-scoped writes across ministries; the sensitive-workflow rule |
| ✔ | API or event shape changes | `G-CONTRACT` — new endpoints below |
| ✔ | Deployed | `G-RELEASE` |
| ■ | always | `G-TEST` |

> **profile:** `UI feature` +CONTRACT **+SENSITIVE** · **gates:** PRODUCT · DESIGN · SENSITIVE · CONTRACT · SPEC · TEST · VERIFY · RELEASE
> **model:** Opus · **size:** M

## Blocked by

**`GRM-116` merged** — the catalog, `resolution_catalog.set_workflow_actions`, the limit of 8, and
workflows that belong to organizations. Not blocked by `GRM-122`, but a *local* action can only be
created on a workflow owned below a ministry, which on today's data needs `GRM-122` (or a test fixture).

## The change

### 1. The panel — one place, in the workflow editor (frame 1)

Below *Notifications* in
[`WorkflowEditor.tsx`](../../../channels/ticketing-ui/components/settings/workflows/WorkflowEditor.tsx),
**on workflows and on templates**.

- Heading *What officers can choose when closing a case* and **"n of 8"**.
- One row per action, in order: **↑↓**, the name, **Edit** (only when the viewer may edit that
  action), **Remove**. A local action shows a small second line: *counts as Hazard repaired*.
- **+ Add an action** opens a search over the actions **this workflow can use** that it does not
  already offer. When the typed text matches nothing, the last line is **+ Create "…"** (frame 2a).
- **Every change saves at once** and applies to the next case closed — no Save button, no
  "unsaved changes" state. The selection is read live, **not** versioned by *Publish*.
- **States** (frame 3): **8 of 8** — *Add* disabled, *"A workflow can offer at most 8 actions. Remove
  one to add another."*; **empty draft** — *"Add at least one action before publishing."* (the
  publish gate is `GRM-116`'s); **SEAH** — the one-line message, no list; **read-only** for a viewer
  who may not change this workflow — list only.

### 2. Create and edit — one dialog (frame 2b)

| Field | When shown |
|---|---|
| **Action** | always |
| **Default text for the officer** | always |
| **In national reports, count this as** — the shared actions of the workflow's ministry | when the workflow's organization is **not** the ministry itself. Required |
| … its extra first choice **A new national action** | only to an admin who manages the ministry (or a platform admin) |

**No owner field.** The server decides: the new action belongs to **the workflow's organization** —
or to **its ministry** when *A new national action* is chosen — and is added to the list in the same
request. When the workflow's organization *is* the ministry, the action is shared and the national
field is not shown. The similarity suggestion (`GRM-121`) sits in this dialog and pre-fills the
national field; in this item the dialog saves directly.

**Edit** is the same dialog, filled in. Editing a shared action shows *"Used by N workflows — the
change applies to all of them."* before saving.

### 3. The rules — all enforced on the server; the UI renders flags it is given

*Reach* = the organizations an admin administers on the standard track
(`admin_org_scope_ids(db, user, "standard")`); a platform admin reaches everything.

| Action | Allowed when |
|---|---|
| **Pick** an action for a workflow | the action is active and **usable by the workflow** — owned by the workflow's organization or one above it (`GRM-116`) |
| **Change a workflow's list** (add, remove, reorder, create into it) | the workflow's organization is inside the admin's reach · the workflow is not sensitive · the result has ≤ 8 actions |
| **Create** | as *change a list*, plus: *A new national action* only when the ministry is inside reach |
| **Edit** an action (label, default text, what it counts as) | the action's owner is inside reach |
| **Counts as** | required for a local action, refused for a shared one; the target must be an **active shared action of the same ministry** |

`project_admin`, `officer_admin` and officers author nothing: the panel is read-only wherever they
can open the workflow (doc 11 §3.3).

*Why the panel picks by the workflow and not by the viewer's scope:* the question the panel answers
is *what can this workflow offer*, which depends only on the workflow's organization. So
`apply_catalog_scope` (the viewer's scope, which also omits organizations above the viewer) is **not**
used here, and no ancestor-aware variant is needed.

### 4. API (G-CONTRACT) — behind the existing admin guards

| Endpoint | Does |
|---|---|
| `GET /workflows/{id}/resolution-actions` | `{actions: [{code, label, default_wording, counts_as_label?, can_edit}], can_change, max: 8, national_choices: [{code, label}], can_create_national}` |
| `GET /workflows/{id}/resolution-actions/available?q=` | actions this workflow can use and does not offer, active, matching `q` |
| `PUT /workflows/{id}/resolution-actions` `{codes: [...]}` | replace the list — `set_workflow_actions` (sensitive, unusable, inactive, > 8, empty-when-published all refused) |
| `POST /workflows/{id}/resolution-actions/new` `{label, default_wording, counts_as_code?, national?: bool}` | create **and append**, one transaction. Refused **before** creating anything when the list is already at 8, so a refusal never leaves an unused action behind. Code generated server-side; a `code` in the body is ignored |
| `PATCH /resolution-actions/{code}` `{label?, default_wording?, counts_as_code?}` | edit; the response carries `used_by_count` |

Workflow endpoints load through `_load_workflow` (the sensitive-workflow gate) and
`_require_workflow_write` (the track), **then** the reach check on the workflow's organization — the
track check alone lets any `org_admin` through.

## Files it may touch

- `ticketing/api/routers/workflows.py` (or a new `routers/resolution_actions.py`) · `ticketing/api/main.py` · `ticketing/api/schemas/resolution_action.py` *(new)*
- `ticketing/services/resolution_catalog.py` — `can_change_list`, `can_edit_action`, `create_action`, `validate_counts_as`
- `channels/ticketing-ui/components/settings/workflows/WorkflowEditor.tsx`
- `channels/ticketing-ui/components/settings/resolution/` *(new)* — `ResolutionPanel.tsx`, `ResolutionActionDialog.tsx`
- `channels/ticketing-ui/lib/api.ts`
- Specs (G-SPEC, same PR): `12` (section *Resolution actions* — the panel, the rules above and why) · `11` §3.3 (authoring resolution actions) · `engineering/05_frontend.md` §9a (the `ui/08` row: built)

## Gates — evidence

- **G-DESIGN** — `ui/08` frames 1, 2, 3, 5. Direction against `ui/02`; copy against `ui/05` (the
  wireframe binds neither). **Implementation contract frozen before build:** the API table, the rules
  table, and the two component names.
- **G-SENSITIVE** — DESIGN §6 checks 6 and 7, plus: a scoped `org_admin` cannot change a list or edit
  an action outside its reach, cannot create *A new national action* without the ministry in reach,
  and cannot point *counts as* at another ministry's action; the panel on a sensitive workflow exposes
  no endpoint that writes.
- **G-TEST** — with admins at DOR, at PD-ADB (under DOR), at a sibling office, and at another ministry:
  - list change: PD-ADB admin on a PD-ADB workflow 200; on a DOR workflow 403; sibling 403; DOR admin on the PD-ADB workflow 200
  - **the limit:** `PUT` with 9 codes 422; `new` on a list at 8 → 422 **and no action row created**
  - create on a PD-ADB workflow: without `counts_as_code` 422; counting as a PD-ADB (local) action 422; as another ministry's action 422; as a DOR shared action → created, owned by PD-ADB, appended
  - create on a DOR workflow: `counts_as_code` sent → 422; created shared
  - *A new national action* by the PD-ADB admin 403; by the DOR admin → owned by DOR, no `counts_as_code`
  - edit: PD-ADB admin cannot edit a DOR shared action; DOR admin can, and the response carries `used_by_count`; changing `counts_as_code` follows the same validation
  - `available` lists only actions the workflow can use, never another ministry's, never ones already on the list
  - codes are server-generated and unique; a `code` in the body is ignored
- **G-VERIFY** — e2e. **Fixture:** dev has no organization under DOR, so create *PD-ADB* under DOR
  and a workflow it owns. As DOR's `org_admin` on that workflow: see *n of 8*; create *Culvert cleared*
  counting as *Hazard repaired*; see it listed with *counts as*; resolve a case with it; fill the list
  to 8 and see *Add* disabled with its message.

## Non-goals

A catalog screen. Retire, restore, merge, widening, clean-up of unused actions (`GRM-123`). Choosing
an action's owner. Inheriting lists. The similarity check (`GRM-121`). Choosing a workflow's
organization (`GRM-122`). Bulk edit. Translating action labels.

## Register line

```
| `GRM-119` — the resolution-action catalog can only grow by a migration | feature | ui-feature+CONTRACT+SENSITIVE | `blocked` | M | resolution-reporting | … |
```
