# Design — What was done, and who did it: resolution fields for the manager's Excel (September 2026)

**Audience:** internal — excluded from the public repository (lifecycle §10.4).
**Governed by:** [`engineering/07_work_items.md`](../../engineering/07_work_items.md) ·
[`engineering/05_frontend.md`](../../engineering/05_frontend.md) §9a (the design gate) ·
[`ticketing_system/ui/05_ui_copy_style.md`](../../ticketing_system/ui/05_ui_copy_style.md) (all on-screen wording) ·
[D-007](../../DECISIONS.md#d-007--seah-is-a-property-of-a-workflow-not-a-concept-in-the-system) (SEAH is a workflow, not a mode).
**Origin:** user request (client, 2026-09-15). **Lane:** `resolution-reporting`.
**Amends (at build, per item):** [`08_ticket_resolution_and_case_summary.md`](../../ticketing_system/08_ticket_resolution_and_case_summary.md) §2.2, §2.3, §2.4, §2.5, §2.6, §3.4 ·
[`09_reports_and_report_builder.md`](../../ticketing_system/09_reports_and_report_builder.md) §4 ·
[`12_workflows_configuration.md`](../../ticketing_system/12_workflows_configuration.md) (new section: resolution actions) ·
[`04_ticketing_schema.md`](../../ticketing_system/04_ticketing_schema.md) (`resolution_actions`, `workflow_resolution_actions`) ·
[`11_roles_and_permissions.md`](../../ticketing_system/11_roles_and_permissions.md) §3.3 (a fifth org-scoped catalog item).

> The shared design note for `GRM-116` … `GRM-119`, `GRM-121` and `GRM-122`. Six items, one design, one questions register.
> ✅ **Q-01 … Q-07 answered by the owner 2026-09-15** ([`QUESTIONS.md`](QUESTIONS.md)). Two answers
> reshaped the design after its first commit: **SEAH is out of the lane** (§3.1.3), and **actions live
> in one catalog** rather than a copied list per workflow (§3.1). ✅ **Q-08** — who owns a catalog
> entry when several ministries share the platform (§3.1.1) — answered as recommended. ✅ **Q-09** —
> where in Settings the catalog is managed — answered: a panel in each workflow plus a catalog sub-tab (`GRM-119`, wireframe `ui/08`) — **the sub-tab later cut by Q-10**. The owner builds the lane in a row.
> ⭐ **Wireframe reviewed with the owner 2026-09-15 — Q-10, the lane simplified:** one panel per
> workflow and nothing else; **at most 8 actions per workflow**; lists copied, never inherited; no
> global actions — shared actions belong to a ministry, and every local action **counts as** one of
> them for national statistics; **every workflow and template belongs to an organization**, set in
> *Settings → Workflows* (`GRM-122`, new). Catalog sub-tab, retire, widening and merge are cut
> (merge and clean-up → `GRM-123`, debt). §3.1.1 is the current model.

---

## 1. Brief — what the client asked for, and what we are building instead

**The ask.** The client's managers do not open the ticketing screens. They read the Excel report.
They asked for **the whole case, summarised, in the Excel file.**

**Why we are not building that.** A case summary in a spreadsheet is a privacy breach, not a
reporting feature:

| A case summary in Excel would… | Because… |
|---|---|
| carry names | the officer's resolution text is free text, and officers write names into it (*"Mr X of ward 4 was paid"*) — nothing redacts it |
| leave every control behind | an `.xlsx` is emailed, forwarded and stored on laptops. The ticketing screens have a JWT, a jurisdiction gate and an audit log; the file has none of them |
| undo a deliberate rule | [`CLAUDE.md`](../../../CLAUDE.md) data rule 4 keeps the raw narrative out of `ticketing.*` precisely so it does not spread to **search, reports and backups** |
| re-identify people even without names | on a SEAH row, *what was done* + ward-level location + date points at one survivor and one worker in a small community |

**What the managers actually need** is to answer two questions across many cases without reading
any of them: **what was done**, and **which office did it**. Both can be recorded as **structured
choices** — picked from a list, never typed — so the Excel gains the answer and gains no PII.

**Three changes, in order:**

1. **The resolution list depends on the workflow.** Today there is one fixed list of five outcomes
   for every case. A road-hazard case needs different ones, and a SEAH case should record none.
   Actions live in one org-scoped catalog; each workflow selects from it. (`GRM-116`)
2. **The officer records who took the action**, when it was not the grievance officer — except on
   SEAH cases. (`GRM-117`)
3. **Both go into the Excel** as *Resolution action* and *Resolved by*. (`GRM-118`)

**Who uses the resolve screen.** A Nepali government officer, English as a second language, not
technical ([`ui/05`](../../ticketing_system/ui/05_ui_copy_style.md)). **Who reads the Excel.** A
project manager at DOR or ADB, comparing offices and quarters.

---

## 2. What exists today — measured 2026-09-15

| Fact | Where |
|---|---|
| **One hard-coded list of five categories** (`CLASSIFIED`, `DEMAND_REJECTED`, `ACCEPTED_MONETARY`, `ACCEPTED_RELOCATION`, `ACCEPTED_OTHER`), each with a label and default wording | [`ticketing/constants/resolution.py`](../../../ticketing/constants/resolution.py) |
| ⚠ **A second copy of the same list in the UI**, kept in step by hand | [`channels/ticketing-ui/lib/resolution.ts`](../../../channels/ticketing-ui/lib/resolution.ts) |
| `RESOLVE` requires `resolution_category` + `note` (≥ 12 chars) and writes **two events**: a `NOTE_ADDED` resolution record and a `RESOLVED` status event, both carrying `resolution_category` in `payload` | [`ticketing/engine/ticket_actions.py`](../../../ticketing/engine/ticket_actions.py) ~L299–L389 |
| The Excel's *Resolution category* column reads the **latest `RESOLVED` event's payload** and maps the code to a label through the Python list | [`ticketing/services/report_rows.py`](../../../ticketing/services/report_rows.py) `_fetch_auxiliary_maps`, `build_report_row` |
| The column is in the **default** columns (overview + quarterly 4-sheet), the **all-data** export, the **public share** columns, and the pivot **group-by** keys | same file, `DEFAULT_REPORT_COLUMNS` · `ALL_DATA_EXPORT_COLUMNS` · `PUBLIC_REPORT_COLUMNS` · `GROUP_BY_KEYS` |
| Saved quarterly report templates **store column keys as strings** in settings | [`ticketing/api/schemas/reports.py`](../../../ticketing/api/schemas/reports.py) `QuarterlyReportTemplate.columns` |
| The category label also reaches the **Summary tab pie**, the **resolved case summary**, the **complainant closure page + PDF**, and the **mobile thread** | `report_summary.py` · `resolved_summary_builder.py` · `closure_pdf.py` · `app/closure/[token]/page.tsx` · `lib/mobile-constants.ts` |
| **Nothing records who acted.** The resolved summary carries `resolved_by_display_name` — the officer who clicked, a person, not an office | `resolved_summary_builder.py` |
| A ticket knows its workflow (`tickets.current_workflow_id`) and the chatbot menu path (`tickets.intake_route`) | [`ticketing/models/ticket.py`](../../../ticketing/models/ticket.py) |
| An officer's office is recorded: `officer_positions(user_id, organization_id, is_active)` | [`ticketing/models/officer_position.py`](../../../ticketing/models/officer_position.py) |
| **Any signed-in officer** can search the organization directory: `GET /api/v1/organizations?q=` | [`ticketing/api/routers/locations.py`](../../../ticketing/api/routers/locations.py) L362 |

### 2.1 "Track" in this note means *workflow*

The request says *"parametered by the track (today default, seah or road works)"*. In the code those
three are the three **chatbot menu paths** (`intake_route`: `new_grievance`, `seah_intake`,
`road_hazard_grievance`), each of which a project binds to a **workflow**. "Track" and "stream"
are retired words ([`12`](../../ticketing_system/12_workflows_configuration.md) §1, D-007); the
on-screen word is **workflow**. This note says *workflow* from here on.

⚠ **Measured on the dev DB:** `KL_ROAD` binds only two workflows (*General grievances* default,
*SEAH* on `seah_intake`). **No project here binds a road-hazard workflow**, so a road-hazard
report lands in the default workflow today. This matters for §3.1.

---

## 3. The design

### 3.1 One catalog of resolution actions; each workflow picks from it (Q-04, Q-07)

> **Revised 2026-09-15 (Q-07 answer).** The first draft copied a list onto each workflow. The owner
> wants lists to **grow naturally without filling up with duplicates**, ideally with an agent
> checking each new entry against what exists. Copies make that impossible: the same action ends up
> under several codes, labels drift apart between copies, and there is no single list to check a new
> entry against. So the actions live in **one catalog**, and a workflow holds an ordered selection of
> catalog codes.

A case offers the actions selected by **the workflow it is in** (`tickets.current_workflow_id`) at
the moment of resolving.

**Why selected by the workflow, and not keyed on the chatbot menu path:**

- D-007 says SEAH is *the name of a workflow*, not a mode of the system. A list keyed on
  `seah_intake` would reintroduce the mode.
- Re-classification moves a case between workflows. The list should follow the case to its new
  workflow; the menu path the complainant took on day one does not change.
- The consequence, stated plainly: **a project that wants road-works actions must bind a road-hazard
  workflow.** On `KL_ROAD` today, a road-hazard report resolves with the general list. That is the
  honest reading of the configuration, not a defect — and it is visible to the admin, which a
  menu-path lookup would not be.

#### 3.1.1 Many ministries on one platform — every action and every workflow belongs to one organization

> **Revised 2026-09-15, twice, the same day — read this version.** The first answer to Q-08 kept
> *global* actions (`owner IS NULL`, usable by every ministry) and left the seeded workflows global.
> Reviewing the wireframe with the owner found that this made authoring unexplainable to a future
> admin, and let a district change a workflow every ministry binds. **The owner's decisions (Q-10):**
> shared actions live **under one organization**; **every workflow and every template belongs to an
> organization**, reassignable in Settings; a workflow offers **at most 8** actions; lists are
> **copied, never inherited**; and every local action says **what it counts as nationally**. The rules
> below are the result. The superseded version is readable in git history, not here.

*The owner's question: what happens when the Ministry of Interior, or Customs, is plugged into the
same GRM software?* The org-scoped catalog rule ([`11`](../../ticketing_system/11_roles_and_permissions.md)
§3.3) answers it — an item owned by an organization is usable at that organization and below — with
**one change for resolution actions: nothing is global.**

| Rule | What it means |
|---|---|
| **Every action belongs to one organization** (`owner_organization_id NOT NULL`) | There is no "for every organization" action. A Customs officer never sees *Hazard repaired* |
| **Shared action** = owned by a **top organization** (a ministry — no parent, e.g. DOR) | DOR's shared actions are DOR's national vocabulary, usable by every workflow under DOR |
| **Local action** = owned by an organization **below** its ministry (e.g. PD-ADB, a division office) | Usable by that organization's workflows and those below it. **Must *count as* one shared action of its own ministry** (`counts_as_code`) |
| **Every workflow and template belongs to one organization** | Set on creation; changed in *Settings → Workflows* (`GRM-122`) — e.g. the KL Road workflows belong to PD-ADB, not all of DOR |
| An action is **usable by a workflow** when it is owned by the workflow's organization or one **above** it | A PD-ADB workflow can offer DOR's shared actions and PD-ADB's local ones; a DOR workflow cannot offer PD-ADB's |

**National statistics.** A report grouped *nationally* counts each case under its action's shared
action — the action itself when shared, its `counts_as_code` when local (`GRM-118`). Two districts'
*Culvert cleared* and *Drain cleaned* both count as DOR's *Hazard repaired*, so DOR's totals are right
the day a local action is created, without a merge. The row's own cell still says what the officer
chose. **Ministries are deliberately not comparable** — no shared vocabulary crosses a ministry.

**Creating an action** (the panel, `GRM-119`) — the admin never chooses an owner:

- it belongs to **the workflow's organization**, automatically;
- if that organization is a ministry, the action is shared and needs nothing more;
- otherwise the dialog asks **"In national reports, count this as"** — a shared action of that
  ministry, pre-filled by the similarity check (`GRM-121`). An admin who manages the ministry itself
  also sees **"A new national action"**, which makes it a shared action owned by the ministry instead.

**At most 8 actions per workflow, and per template** (`MAX_RESOLUTION_ACTIONS = 8`, a constant, not
a setting). An officer chooses from a short list, often on a phone, in a second language; and a list
that cannot pass 8 cannot fill up with near-duplicates. Enforced in `set_workflow_actions`, so no
screen, API call, copy or template can exceed it.

**A workflow's list is its own.** It is **copied** when a workflow is created from a template or from
another workflow, **never inherited**: a later change to the source does not reach the copy. *Why:*
with inheritance, a shared list growing past a full local list would have to either block the
ministry, break the limit of 8, or silently drop local actions. A copy never forces that choice. The
cost, accepted: a new action added to a template does not appear in workflows already made from it.

**A template is offered only to workflows of its organization or below**, so everything it copies is
usable by construction. The built-in code templates (`BUILT_IN_TEMPLATES`) belong to no organization
and carry **no list**.

**Where a workflow's organization comes from.** `GRM-116`'s migration assigns every existing
workflow and template to **the ministry of the projects that use it** (the top organization above each
project's implementing agency). ⚠ **Measured on the dev DB 2026-09-15:** all three workflows have no
owner; both projects using them are implemented by `DOR`, so all three become DOR's. A workflow no
project uses goes to the one ministry that implements projects, if there is exactly one; a workflow
used by projects of **two** ministries, or an unused one when there are several, **stops the
migration and names it** — a guess would silently hand one ministry's workflow to another. Admins then
move a workflow **down** to where it belongs (PD-ADB) in *Settings → Workflows* (`GRM-122`). A
platform admin picks the organization when creating a workflow; an org admin's workflows get its
organization, as today (`catalog_owner_for`).

**Moving a workflow to another organization is refused while its list holds an action the new
organization cannot use**, and the refusal names the action (`GRM-122`). Moving down (DOR → PD-ADB)
never hits this; moving sideways or up can.

**Who authors** — unchanged from doc 11 §3.3: `super_admin` and `org_admin` (within its reach) change
workflows' lists and create actions; `project_admin` and officers consume them. An `org_admin` changes
a workflow's list, its organization, or an action only where that organization is inside its reach.

**What this still does not solve.** Position types, roles and project types keep their global seed
rows, and workflow writes elsewhere in the editor still check only the track — `GRM-120`, narrowed.

#### 3.1.2 Starter actions

Seeded by the migration as **shared actions of the ministry found above** (DOR on every database
today). On an empty database there is no ministry yet, so the migration seeds nothing and
`kl_road_standard.py` creates them under DOR. **The general five are today's five, with codes
unchanged**, so every historical event still resolves. ⚠ Codes are platform-unique, so a second
ministry's starter actions will need their own codes — `GRM-120`.

**General** — unchanged:

| Code | Label |
|---|---|
| `CLASSIFIED` | Grievance classified |
| `DEMAND_REJECTED` | Complainant demand rejected |
| `ACCEPTED_MONETARY` | Grievance accepted — monetary compensation |
| `ACCEPTED_RELOCATION` | Grievance accepted — relocation |
| `ACCEPTED_OTHER` | Grievance accepted — other remedy |

**Road works** — draft, confirmed by the owner 2026-09-15 as the starting set (Q-06):

| Code | Label | Default wording |
|---|---|---|
| `ROAD_REPAIRED` | Hazard repaired | The reported hazard was inspected and repaired. |
| `ROAD_MADE_SAFE` | Made safe — signs, barriers or traffic control | The site was made safe with warning signs, barriers or traffic control. A permanent repair is planned. |
| `ROAD_DUST_NOISE_CONTROLLED` | Dust or noise controlled | The contractor was instructed to control dust or noise, for example by spraying water or limiting working hours. |
| `ROAD_NOT_PROJECT_ROAD` | Not on a project road — passed on | The location is not on a project road. The report was passed to the authority responsible for it. |
| `ROAD_NO_HAZARD_FOUND` | No hazard found on inspection | The site was inspected and no hazard was found. |

**Codes are the catalog's primary key**: unique platform-wide, immutable, never reused. A code
alone names an action wherever it appears.

**Backfill — which workflow selects which starter set:**

| Workflow | Selects |
|---|---|
| sensitive (`lower(workflow_type) = 'seah'`) | **nothing** — §3.1.3 |
| bound on any project with `intake_route = 'road_hazard_grievance'` | the road-works five |
| any other, templates included | the general five |

**A workflow created afterwards:** from a template or another workflow → a copy of its list; from a
built-in template or from scratch → **no actions**, and it **cannot be published** until it has at
least one.

**Invariants**, enforced in the service that writes lists, not by convention: a non-sensitive
**published** workflow offers **1 to 8** active actions; a sensitive workflow offers **none**; every
action on a list is usable by the workflow's organization.

#### 3.1.3 SEAH records neither what was done nor who did it (Q-06 answer)

> **Decided 2026-09-15.** The first draft carried a SEAH list. The owner chose to leave sensitive
> workflows out of this lane entirely.

**Why.** Every structured value about a SEAH case is a re-identification risk in a spreadsheet:
*Resolved by: Police* says criminal referral as clearly as any action label does. And today a SEAH
case is **forced** to pick one of the general five — including *"Complainant demand rejected"* — which
is the harmful outcome this lane should remove, not preserve.

**So, for a case in a sensitive workflow:**

- the resolve form shows **only the resolution text** — no *What was done*, no *Who took the action?*;
- `RESOLVE` does not require `resolution_category`, and **refuses** it or any actor field (422);
- the Excel's two columns are **blank** for that row;
- the service **refuses** selecting any action for a sensitive workflow, so this cannot be undone by
  configuration — if SEAH ever needs a list, it is a decision that changes one rule, visibly.

**Historical SEAH resolutions are left as they are.** Cases already resolved carry a general code
in their events, and the Excel keeps showing it. Rewriting append-only history to hide a label is not
this lane's call; new SEAH resolutions simply stop producing one.

**Authoring in Settings** is `GRM-119` (the panel), **which organization a workflow belongs to** is
`GRM-122`, and **the similarity check** is `GRM-121` — all in this lane, built after `GRM-116`.

### 3.2 Who took the action (Q-02, Q-03)

For a case in a **non-sensitive** workflow (§3.1.3), the resolve form asks **who took the action**,
with three answers:

| Answer | Stored | Shown as *Resolved by* |
|---|---|---|
| **I did** (the default) | the officer's **office**, derived (§3.2.1) | that office's name, e.g. *Jhapa Division Road Office* |
| **Another office** | an organization from the directory | that organization's name |
| **An outside body** | one key from a fixed list | its label |

**The outside-body list** (fixed in code, no free text):

| Key | Label |
|---|---|
| `police` | Police |
| `local_government` | Municipality or ward office |
| `contractor` | Contractor |
| `court` | Court |
| `users_committee` | Users' committee *(Q-06, added 2026-09-15)* |
| `other_government` | Other government office |

**No free text anywhere in this field.** The whole point is that the Excel column cannot hold a
person's name, and a free-text "Other" is exactly where one would be typed.

**"I did" still names an office, never a person** (Q-03). That makes every resolved row comparable
by office, whether the officer acted or someone else did — a manager filtering *Resolved by = Jhapa
Division Road Office* sees both.

#### 3.2.1 Deriving "my office"

Among the resolving officer's **active** `officer_positions`:

1. exactly one → its organization;
2. several → the one whose organization is linked to the case's project (`project_organizations`,
   or `package_organizations` for the case's package, including a parent of a linked org); if
   still several, **the officer chooses** among their own offices in the form;
3. none (an officer provisioned before positions existed) → the case's `tickets.organization_id`.

The derived office is **shown in the form before confirming** ("I did — *Jhapa Division Road
Office*"), so a wrong derivation is visible to the one person who can see it is wrong.

#### 3.2.2 Picking another office

A search box over the organization directory (existing `GET /organizations?q=`, active only). Before
the officer types, it lists **the organizations linked to this case's project** as suggestions —
the office that acted is almost always one of them.

### 3.3 What is stored

**Per resolution — no new table.** Same two events as today. Both gain the same fields in
`payload` (sensitive workflows: none of the six keys are written):

```jsonc
{
  "resolution_category": "ROAD_REPAIRED",               // unchanged key — see Q-05
  "resolution_category_label": "Hazard repaired",       // NEW: snapshot at resolve time
  "resolution_actor_kind": "self",                      // NEW: self | organization | external
  "resolution_actor_organization_id": "org-jhapa-dro",  // NEW: set for self and organization
  "resolution_actor_external": null,                    // NEW: set for external only
  "resolution_actor_label": "Jhapa Division Road Office" // NEW: snapshot at resolve time
}
```

**Why labels are snapshotted.** Events are append-only history. If an action's label is later
edited, an office renamed, or the case moved to another workflow, the Excel must still say what the
officer chose on the day. Readers use the snapshot first, and fall back to the catalog only for
events written before this lane (which all use the unchanged general codes).

**The catalog — two tables** (ticketing Alembic stream; no PII; FKs stay inside `ticketing.*`):

```
ticketing.resolution_actions
  code                   String(64)  PK            -- immutable, platform-unique
  label                  Text        NOT NULL
  default_wording        Text        NOT NULL
  owner_organization_id  String(64)  NOT NULL  FK → ticketing.organizations  ON DELETE RESTRICT
                                                    -- a ministry (shared) or below it (local); never global
  counts_as_code         String(64)  NULL  FK → ticketing.resolution_actions (self)
                                                    -- required for a local action, NULL for a shared one;
                                                    -- must be a shared action of the same ministry (§3.1.1)
  is_active              Boolean     NOT NULL default true
                                                    -- no screen sets it in this lane; kept for clean-up (GRM-123)
  created_by_user_id     String(128) NULL          -- NULL for seed
  created_at, updated_at timestamptz

ticketing.workflow_resolution_actions
  workflow_id  String(36)  FK → ticketing.workflow_definitions  ON DELETE CASCADE
  code         String(64)  FK → ticketing.resolution_actions    ON DELETE RESTRICT
  sort_order   Integer     NOT NULL
  PRIMARY KEY (workflow_id, code)
```

⚠ **`ON DELETE RESTRICT` on both org and code, deliberately.** `workflow_definitions.owner_organization_id`
uses `SET NULL`, which silently turns an org-owned item **ownerless** when its org is deleted — for a
resolution action that would detach one ministry's vocabulary from its ministry. An action is never
deleted: historical events cite its code.

**Why `counts_as_code` is checked in the service, not by a constraint:** "same ministry" and "a
shared action" are facts about the organization tree, which a column constraint cannot see. The
service refuses a local action without it, a shared action with it, and a target that is local or
under another ministry.

**Why a join table and not a JSON array of codes on the workflow:** the FK makes a selection of a
non-existent code impossible, and "which workflows use this action?" — what an admin needs before
editing a shared action's wording — is a query, not a scan.

### 3.4 The Excel (Q-01)

| Column | Key | Value |
|---|---|---|
| **Resolution action** | `resolution_category` *(relabelled — Q-05)* | the snapshot label; blank if not resolved |
| **Resolved by** | `resolution_actor` *(new)* | the snapshot label; blank if not resolved; **`Not recorded`** if resolved before this lane; **blank on every SEAH row** |

- Both in `DEFAULT_REPORT_COLUMNS` (so the overview and the quarterly 4-sheet export) and
  `ALL_DATA_EXPORT_COLUMNS`. `resolution_actor` also joins `GROUP_BY_KEYS`, so the pivot can
  count cases **by office** — the comparison managers want.
- **National grouping** *(Q-10)*: a report key `resolution_action_national` — the action's shared
  action (itself when shared, its `counts_as_code` when local), labelled *Resolution action
  (national)*. In `GROUP_BY_KEYS` and `ALL_DATA_EXPORT_COLUMNS`, not in the default columns. It reads
  the **current** mapping, so correcting what a local action counts as corrects past totals too; the
  row's *Resolution action* cell keeps its snapshot. Blank on SEAH rows.
- **`resolution_actor` is not added to `PUBLIC_REPORT_COLUMNS`.** The public share link is out of
  scope; the ask was the internal Excel.
- **Old cases say `Not recorded`, and are not backfilled.** Filling them with the resolving
  officer's office would assert something nobody recorded. A blank would read as missing data.
- **SEAH rows gain nothing.** New SEAH resolutions write no action and no actor (§3.1.3), so both
  columns are blank; historical SEAH rows keep the action label they already show. The rows
  themselves stay behind the existing gate — dropped unless the reader can see SEAH *and* asked for
  them (`build_ticket_query`).
- **`Not recorded` is never shown on a SEAH row** — it would imply a value that should exist.

### 3.5 Where the new fields also appear

| Surface | Change |
|---|---|
| Thread — resolution record note | A `Resolved by: <label>` line under `Date:` ([`08`](../../ticketing_system/08_ticket_resolution_and_case_summary.md) §2.4) |
| Resolved case summary (officer) | `resolution.actor_label` beside `category_label`; passed to the findings LLM as **read-only context** (an office name — no PII) |
| Summary tab pie | Label changes to *Resolution action*; slices use the snapshot label |
| Complainant closure page + PDF | Still shows the action label. *Resolved by* is not added (non-goal). ⚠ For a new SEAH resolution the label is empty — the page and PDF **omit the line** rather than print a blank heading |
| Settings → Workflows | A *Resolution* panel in each workflow and template (`GRM-119`), and a *Belongs to* line with *Change* on each workflow and template (`GRM-122`) — wireframe [`ui/08`](../../ticketing_system/ui/08_resolution_actions_catalog.html). No catalog screen (§3.1.1) |

---

## 4. The resolve form — wireframe and state contract (G-DESIGN)

Same modal, same place ([`ResolutionSheet.tsx`](../../../channels/ticketing-ui/components/ResolutionSheet.tsx),
used by desktop and `/m/tickets/[id]`). One control renamed, one section added.

```
┌──────────────────────────────────────────────────────────┐
│ Resolve case                                             │
│ Choose what was done and who did it. This will appear    │
│ in the case thread.                                      │
│                                                          │
│ What was done                                            │
│ [ Hazard repaired                                  ▾ ]   │  ← list from the case's workflow
│                                                          │
│ Who took the action?                                     │
│ (•) I did — Jhapa Division Road Office                   │  ← derived office, §3.2.1
│ ( ) Another office                                       │
│ ( ) An outside body                                      │
│                                                          │
│ Resolution text (at least 12 characters)                 │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ The reported hazard was inspected and repaired.      │ │
│ └──────────────────────────────────────────────────────┘ │
│                                                          │
│ [ Cancel ]                        [ Confirm resolve ]    │
└──────────────────────────────────────────────────────────┘

"Another office" selected:            "An outside body" selected:
│ (•) Another office               │   │ (•) An outside body              │
│     [ Search offices…        ]   │   │     [ Police                ▾ ]  │
│     Offices on this project:     │
│     ○ Jhapa Division Road Office │
│     ○ ABC–XYZ Joint Venture      │
```

**Copy.** *Resolution category* becomes **What was done** on screen (the Excel header stays
*Resolution action*, the managers' word). Plain verbs; no "actor", "entity" or "kind" on screen
([`ui/05`](../../ticketing_system/ui/05_ui_copy_style.md)).

**Sensitive workflow** — the form is today's form minus the category: title, subtitle *"Describe
what was decided. This will appear in the case thread."*, the resolution text, Cancel / Confirm.
No default wording is filled in.

**States — seven, not two:**

| State | Behaviour |
|---|---|
| Case in a sensitive workflow | Only the resolution text; both sections absent, not disabled |
| Opening | *What was done* and *I did — …* both come from the ticket detail response already loaded; no extra fetch, no spinner |
| Office derived | *I did — <office>* preselected |
| Several own offices, none linked to the project | *I did* shows a small select of the officer's own offices; nothing preselected; **Confirm is disabled until one is chosen** |
| *Another office* chosen, none picked yet | Confirm disabled; hint *"Choose the office that took the action."* |
| Office search returns nothing | *"No office found. If it is not in the directory, choose 'An outside body' or ask an admin to add it."* |
| Server rejects (code not in this workflow's list — the case was re-classified while the form was open) | Form stays open with its text; message *"This case moved to another workflow. Choose what was done again."* and the list reloads |

**Default wording.** Changing *What was done* replaces the text only while the officer has not
edited it. ⚠ **Corrected while building `GRM-116`:** this line first called that "the existing
behaviour, kept" — it was not. The old sheet replaced the text on every change of category, discarding
what the officer had typed. `GRM-116` makes the stated behaviour true.

---

## 5. API contract (G-CONTRACT)

**Ticket detail** (`GET /api/v1/tickets/{id}`) gains, for officers who can resolve:

```jsonc
"resolution_options": [ { "code": "ROAD_REPAIRED", "label": "Hazard repaired", "default_wording": "…" } ],
"resolution_self_offices": [ { "organization_id": "org-jhapa-dro", "name": "Jhapa Division Road Office" } ],
"resolution_office_suggestions": [ { "organization_id": "…", "name": "…" } ],
"resolution_external_actors": [ { "key": "police", "label": "Police" } ]
```

`resolution_self_offices` is the result of §3.2.1: one entry when derived, several when the officer
must choose. **For a case in a sensitive workflow all four are empty arrays** — the UI renders the
text-only form from that, and needs no separate "is sensitive" flag. **Why on the ticket and not from
`GET /workflows/{id}`:** officers cannot read workflow definitions, and a SEAH workflow is readable
only by those who configure sensitive workflows — the case view must not need that permission.

`resolution_options` lists the workflow's **active** selected actions, in `sort_order`. Ownership is
checked when an action is selected for a workflow, not when an officer resolves: an officer never
needs to be inside the action owner's subtree.

**`POST /tickets/{id}/actions` with `action_type: RESOLVE`** gains three optional fields:

| Field | Rule |
|---|---|
| `resolution_actor_kind` | `self` \| `organization` \| `external`. **Omitted → `self`** |
| `resolution_actor_organization_id` | required when `organization` (active org), or when `self` and the officer has several offices; ignored otherwise |
| `resolution_actor_external` | required when `external`, one of the fixed keys |

`resolution_category` is now validated against **the case's current workflow selection**, not a
global list: required and a member when the selection is non-empty; **refused when it is empty**
(sensitive). Actor fields are refused for a sensitive workflow. 422 on any violation, naming the field.

**Compatibility.** Additive for standard cases: a client that sends only `resolution_category` +
`note` keeps working and records `self`. **Narrowing, deliberately, in two places:** a code outside
the case's workflow selection is refused, and a SEAH case that sends any category is refused — a
client that always sends one (as the current UI does) must be updated in the same release.

---

## 6. Sensitive paths (G-SENSITIVE — why this lane carries `+SENSITIVE`)

It touches SEAH (what a SEAH case records, SEAH rows in Excel) and org-scoped authorization (which
ministry sees which actions), so the modifier applies regardless of size
([07 §4.2](../../engineering/07_work_items.md)). What the isolation review checks, separately from
correctness:

1. **No free text reaches the Excel** from either new column — only list labels and directory names.
   Test: a resolve with a name typed into `note` produces no trace of it in `build_report_row`.
2. **SEAH rows stay behind the existing gate** — a user without SEAH visibility gets no SEAH row,
   with or without the new columns. Test exists for the row; extend it to assert the columns.
3. **The case view does not widen workflow read access** — `resolution_options` is served from the
   ticket the officer can already open; no officer gains read on `GET /workflows/{id}`.
4. **The public share is unchanged** — `resolution_actor` is absent from `PUBLIC_REPORT_COLUMNS`.
5. **A SEAH case records nothing structured** — a `RESOLVE` on a sensitive-workflow case with a
   category or any actor field is a 422, and selecting an action for a sensitive workflow is refused.
6. **An action cannot reach another ministry** — the availability test mirrors doc 11 §3d: an action
   owned at Jhapa cannot be offered by an Ilam or a DOR workflow; a DOR action cannot be offered by
   another ministry's workflow; **no action is global**. A local action cannot count as another
   ministry's action. Deleting an org that owns an action is refused, never `SET NULL`.
7. **No organization's admin changes what another ministry's officers can choose**: an `org_admin`
   changes a workflow's list, a workflow's organization or an action only inside its reach; a
   workflow cannot be moved to an organization that cannot use an action on its list (`GRM-119`,
   `GRM-122`). The similarity check is shown only actions the workflow can use (`GRM-121`).

---

## 7. Non-goals

- **The case summary in Excel.** Declined, §1.
- **An `outcome` grouping field** across actions — replaced by *counts as* a shared action (Q-10, §3.1.1).
- **A catalog screen, retiring, restoring, widening, merging duplicates** — cut for admin simplicity (Q-10); merge and clean-up → `GRM-123`.
- **Inheriting a list** from a template or another workflow — lists are copied (§3.1.1).
- **Re-homing position types, roles and project types** before a second ministry is onboarded → `GRM-120`. Workflows and templates are re-homed in this lane.
- **Any structured resolution value for SEAH cases**, and rewriting historical SEAH labels (§3.1.3).
- **Resolved by on the complainant closure page or the public share link.**
- **Backfilling *Resolved by* for cases already resolved.**
- **A free-text "Other" for either field.**
- **Changing the photo requirement on resolve** (hard-blocked today, `GRM-073`).
