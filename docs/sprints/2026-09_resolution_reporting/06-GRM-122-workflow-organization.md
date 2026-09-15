# `GRM-122` — an admin cannot say which organization a workflow belongs to

**Origin:** user request (owner, Q-10, 2026-09-15) · **Lane:** `resolution-reporting` · **Reported:** 2026-09-15
**Design:** [`DESIGN-resolution-reporting.md`](DESIGN-resolution-reporting.md) §3.1.1 ·
**Wireframe:** [`ui/08_resolution_actions_catalog.html`](../../ticketing_system/ui/08_resolution_actions_catalog.html) frame 4

> Opened 2026-09-15 from the owner's review of the resolution-action wireframe: *"we need to have a
> section in settings/workflow where we assign the right owner — for instance these workflows belong to
> PD-ADB and not the whole of DOR"*, and *"templates should be owned by organization as well."*
>
> **Why it exists.** Resolution actions belong to organizations (DESIGN §3.1.1), so a workflow can
> offer an action only if the workflow itself belongs to one. `GRM-116`'s migration gives every
> existing workflow and template **its projects' ministry** — the only safe automatic answer — but the
> right owner is often lower down: the KL Road workflows are PD-ADB's, not all of DOR's. Today the
> organization is stamped once, invisibly, at creation (`catalog_owner_for`), and a platform admin's
> workflow gets none at all.

## Kind

**`feature`** — question 1: no live spec lets an admin see or change a workflow's organization.

## Profile

| ✓ | Question | Fires |
|---|---|---|
| ✔ | Changes user-visible behaviour | `G-PRODUCT` · `G-SPEC` · `G-VERIFY` |
| ✔ | A UI surface changes shape | `G-DESIGN` — a *Belongs to* line and dialog in the workflow editor, a field in *New workflow*, the organization under each name in the list; `ui/08` frame 4 |
| ✗ | Schema changes | — `workflow_definitions.owner_organization_id` exists |
| ✔ | PII · auth · SEAH · complainant channel · new egress | `G-SENSITIVE` — ownership decides which ministry's admins can change a workflow and which actions it can offer |
| ✔ | API or event shape changes | `G-CONTRACT` — one new endpoint; `POST /workflows` and the list response gain a field |
| ✔ | Deployed | `G-RELEASE` |
| ■ | always | `G-TEST` |

> **profile:** `UI feature` +CONTRACT **+SENSITIVE** · **gates:** PRODUCT · DESIGN · SENSITIVE · CONTRACT · SPEC · TEST · VERIFY · RELEASE
> **model:** Opus · **size:** S

## Blocked by

**`GRM-116` merged** — workflows and templates already have organizations, and the availability test
exists. **Build it next:** until it ships, a platform admin's new workflow or template has no
organization, so it can offer no action and cannot be published.

## The change

### 1. *Belongs to* — in the workflow editor (frame 4)

On every workflow **and template**, beside *Type* and *Key* in the editor's meta line:
**Belongs to: Department of Roads · Change**.

**Change** opens a small dialog:

- a search over organizations **inside the admin's reach** (a platform admin: all);
- below it, for information only: *Projects using this workflow: KL Road*;
- **Save**.

**Refused, with the reason on the dialog** (the dialog stays open):

| When | Message (copy per `ui/05`) |
|---|---|
| An action on the list cannot be used by the new organization | *"Remove 'Culvert cleared' first — it belongs to Jhapa Division Road Office."* — one line per action |
| The new or the current organization is outside the admin's reach | *"You can only move workflows between organizations you manage."* |

Moving **down** (DOR → PD-ADB) never hits the first refusal; moving sideways, up, or to another
ministry can. **Local actions do not move** with the workflow — they stay with their organization.

A workflow with **no** organization (a platform admin's, before this item; or one whose organization
was deleted — its FK is `SET NULL`) shows **Belongs to: — Choose** in place of the line, and the
resolution panel says *"Choose the organization this workflow belongs to first."*

### 2. *New workflow* — the organization is chosen, not stamped

[`NewWorkflowModal.tsx`](../../../channels/ticketing-ui/components/settings/workflows/NewWorkflowModal.tsx)
gains **Belongs to**: **required** for a platform admin; for an `org_admin`, pre-filled with its
organization (`catalog_owner_for`) and changeable within its reach. The template picker then lists
**only templates of that organization or an organization above it** (DESIGN §3.1.1), so everything a
template copies is usable by construction. *Save as template* gives the template the workflow's
organization.

### 3. The workflow list

Each workflow and template in
[`WorkflowsTab.tsx`](../../../channels/ticketing-ui/components/settings/workflows/WorkflowsTab.tsx)
shows its organization under the name — the same small grey line *Project types* uses (*"For
Department of Roads"*).

### 4. API (G-CONTRACT)

| Endpoint | Does |
|---|---|
| `PATCH /workflows/{id}/organization` `{organization_id}` | change it — reach on both organizations; refused (422, naming each action) while the list holds one the new organization cannot use; written to `admin_audit_log` with the old and new organization |
| `POST /workflows` | gains `owner_organization_id` — required when the caller is a platform admin; otherwise defaults to `catalog_owner_for` and must be inside reach. Templates included (`GRM-116` stopped stamping `NULL` on them) |
| `GET /workflows` | each row gains `owner_organization_id` and `owner_name` |
| `GET /workflows?is_template=true&for_organization_id=` | templates owned by that organization or one above it — **ancestor-aware**, unlike `apply_catalog_scope`, which omits organizations above the viewer |

Loads through `_load_workflow`, so a sensitive workflow's organization is changed only by those who
may configure sensitive workflows.

**Deliberately not checked:** whether the projects using a workflow sit under its new organization.
No catalog enforces that today; the dialog shows the projects so the admin can see it, and the
question is logged on `GRM-120`.

## Files it may touch

- `ticketing/api/routers/workflows.py` · `ticketing/api/schemas/workflow.py` (or wherever `WorkflowCreate` lives)
- `ticketing/services/resolution_catalog.py` (the usable-by-new-organization check) · `ticketing/services/admin_access.py` (reach helpers only)
- `channels/ticketing-ui/components/settings/workflows/WorkflowEditor.tsx` · `NewWorkflowModal.tsx` · `WorkflowsTab.tsx` · `lib/api.ts`
- Specs (G-SPEC, same PR): `12` (a workflow's organization — how it is set and changed, and why it matters to resolution actions) · `11` §3.3 (templates are owned; the platform admin chooses)

## Gates — evidence

- **G-DESIGN** — `ui/08` frame 4. Copy against `ui/05`.
- **G-SENSITIVE** — an `org_admin` cannot move a workflow into or out of an organization outside its
  reach; a move can never leave a workflow offering an action its new organization cannot use; a
  sensitive workflow's organization is unchangeable without the sensitive-configuration capability.
- **G-TEST** —
  - move DOR → PD-ADB with DOR shared actions on the list → 200; PD-ADB → sibling office with a PD-ADB local action on the list → 422 naming it; to another ministry with any action → 422
  - PD-ADB admin moving a DOR workflow → 403; DOR admin moving it to PD-ADB → 200 and an audit row
  - `POST /workflows` as platform admin without `owner_organization_id` → 422; as `org_admin` with an organization outside reach → 403
  - template picker for PD-ADB lists DOR's and PD-ADB's templates, not a sibling's or another ministry's
  - *Save as template* → template owned by the workflow's organization
- **G-VERIFY** — e2e: as DOR's `org_admin`, open *KL Road – 4-Level Standard GRM Workflow*, see
  *Belongs to: Department of Roads*, move it to a fixture *PD-ADB* under DOR, see the list line update;
  try moving it to another ministry with actions on its list and read the refusal.

## Non-goals

Moving local actions with a workflow. Checking project bindings against the new organization
(`GRM-120`). Bulk reassignment. Ownership of position types, roles and project types (`GRM-120`).

## Register line

```
| `GRM-122` — an admin cannot say which organization a workflow belongs to | feature | ui-feature+CONTRACT+SENSITIVE | `blocked` | S | resolution-reporting | … |
```
