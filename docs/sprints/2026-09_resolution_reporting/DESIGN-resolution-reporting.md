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
[`04_ticketing_schema.md`](../../ticketing_system/04_ticketing_schema.md) (`workflow_definitions`).

> The shared design note for `GRM-116` … `GRM-118`. Three items, one design, one questions register.
> ✅ **Q-01 … Q-04 answered by the owner 2026-09-15.** Q-05 and Q-06 are open — see
> [`QUESTIONS.md`](QUESTIONS.md); each says what it blocks.

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
   for every case. A road-hazard case and a SEAH case need different ones. (`GRM-116`)
2. **The officer records who took the action**, when it was not the grievance officer. (`GRM-117`)
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

### 3.1 Resolution actions live on the workflow (Q-04)

Each **workflow definition** carries its own ordered list of resolution actions. A case offers the
list of **the workflow it is in** (`tickets.current_workflow_id`) at the moment of resolving.

**Why on the workflow, and not keyed on the chatbot menu path:**

- D-007 says SEAH is *the name of a workflow*, not a mode of the system. A list keyed on
  `seah_intake` would reintroduce the mode.
- Re-classification moves a case between workflows. The list should follow the case to its new
  workflow; the menu path the complainant took on day one does not change.
- The consequence, stated plainly: **a project that wants road-works actions must bind a road-hazard
  workflow.** On `KL_ROAD` today, a road-hazard report resolves with the general list. That is the
  honest reading of the configuration, not a defect — and it is visible to the admin, which a
  menu-path lookup would not be.

**Starter lists.** Three lists are defined once in code (`STARTER_RESOLUTION_LISTS`) and copied
onto workflows — by the migration for existing ones, and by the workflow templates for new ones.
**The general list is today's five, with codes unchanged**, so every historical event still resolves.
The road-works and SEAH lists are **drafts for client confirmation** (Q-06, blocks merge of `GRM-116`):

**General** (`general`) — unchanged:

| Code | Label |
|---|---|
| `CLASSIFIED` | Grievance classified |
| `DEMAND_REJECTED` | Complainant demand rejected |
| `ACCEPTED_MONETARY` | Grievance accepted — monetary compensation |
| `ACCEPTED_RELOCATION` | Grievance accepted — relocation |
| `ACCEPTED_OTHER` | Grievance accepted — other remedy |

**Road works** (`road_works`) — draft:

| Code | Label | Default wording |
|---|---|---|
| `ROAD_REPAIRED` | Hazard repaired | The reported hazard was inspected and repaired. |
| `ROAD_MADE_SAFE` | Made safe — signs, barriers or traffic control | The site was made safe with warning signs, barriers or traffic control. A permanent repair is planned. |
| `ROAD_DUST_NOISE_CONTROLLED` | Dust or noise controlled | The contractor was instructed to control dust or noise, for example by spraying water or limiting working hours. |
| `ROAD_NOT_PROJECT_ROAD` | Not on a project road — passed on | The location is not on a project road. The report was passed to the authority responsible for it. |
| `ROAD_NO_HAZARD_FOUND` | No hazard found on inspection | The site was inspected and no hazard was found. |

**SEAH** (`seah`) — draft, **needs a SEAH officer's review** before merge:

| Code | Label | Default wording |
|---|---|---|
| `SEAH_REFERRED_SUPPORT` | Referred to support services | The complainant was referred to support services (medical, psychosocial or legal), with their consent. |
| `SEAH_REFERRED_INVESTIGATION` | Referred for criminal investigation | The case was referred for criminal investigation, with the complainant's consent. |
| `SEAH_DISCIPLINARY_ACTION` | Disciplinary action taken | Disciplinary action was taken under the contractor's or employer's code of conduct. |
| `SEAH_REMOVED_FROM_PROJECT` | Person removed from the project | The person responsible was removed from work on the project. |
| `SEAH_SAFETY_MEASURES` | Safety measures put in place | Safety measures were put in place to protect the complainant and others on site. |

⚠ **Deliberately absent from the SEAH draft: any "not substantiated" outcome.** A survivor-centred
GRM refers and protects; it does not rule on whether the survivor is believed, and a spreadsheet
column reading *"Allegation rejected"* next to a ward and a date is the harm this lane exists to
avoid. If the client wants one, it is their call to make explicitly (Q-06).

**Codes are unique across all starter lists** (hence the prefixes), so a code alone names an action
even where the workflow is not at hand.

**Editing a list in Settings is not in this lane** (Q-04 answer). Until it exists, a list changes
by editing `STARTER_RESOLUTION_LISTS` and a data migration. Logged as `GRM-119`.

### 3.2 Who took the action (Q-02, Q-03)

The resolve form asks **who took the action**, with three answers:

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

### 3.3 What is stored — no new table

Same two events as today. Both gain the same fields in `payload`:

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

**Why labels are snapshotted.** Events are append-only history. If a list is later edited, an
office renamed, or the case moved to another workflow, the Excel must still say what the officer
chose on the day. Readers use the snapshot first, and fall back to looking the code up only for
events written before this lane (which all use the unchanged general codes).

**Schema.** One column: `ticketing.workflow_definitions.resolution_options` — JSON, NOT NULL,
an ordered list of `{code, label, default_wording}`. No PII, no FK. Ticketing Alembic stream.

### 3.4 The Excel (Q-01)

| Column | Key | Value |
|---|---|---|
| **Resolution action** | `resolution_category` *(relabelled — Q-05)* | the snapshot label; blank if not resolved |
| **Resolved by** | `resolution_actor` *(new)* | the snapshot label; blank if not resolved; **`Not recorded`** if resolved before this lane |

- Both in `DEFAULT_REPORT_COLUMNS` (so the overview and the quarterly 4-sheet export) and
  `ALL_DATA_EXPORT_COLUMNS`. `resolution_actor` also joins `GROUP_BY_KEYS`, so the pivot can
  count cases **by office** — the comparison managers want.
- **`resolution_actor` is not added to `PUBLIC_REPORT_COLUMNS`.** The public share link is out of
  scope; the ask was the internal Excel.
- **Old cases say `Not recorded`, and are not backfilled.** Filling them with the resolving
  officer's office would assert something nobody recorded. A blank would read as missing data.
- **SEAH rows gain no new visibility.** The report query already drops SEAH rows unless the
  reader can see SEAH *and* asked for them (`build_ticket_query`). The new columns ride that gate.

### 3.5 Where the new fields also appear

| Surface | Change |
|---|---|
| Thread — resolution record note | A `Resolved by: <label>` line under `Date:` ([`08`](../../ticketing_system/08_ticket_resolution_and_case_summary.md) §2.4) |
| Resolved case summary (officer) | `resolution.actor_label` beside `category_label`; passed to the findings LLM as **read-only context** (an office name — no PII) |
| Summary tab pie | Label changes to *Resolution action*; slices use the snapshot label |
| Complainant closure page + PDF | **Unchanged** — still shows the action label. *Resolved by* is not added (non-goal) |

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

**States — six, not two:**

| State | Behaviour |
|---|---|
| Opening | *What was done* and *I did — …* both come from the ticket detail response already loaded; no extra fetch, no spinner |
| Office derived | *I did — <office>* preselected |
| Several own offices, none linked to the project | *I did* shows a small select of the officer's own offices; nothing preselected; **Confirm is disabled until one is chosen** |
| *Another office* chosen, none picked yet | Confirm disabled; hint *"Choose the office that took the action."* |
| Office search returns nothing | *"No office found. If it is not in the directory, choose 'An outside body' or ask an admin to add it."* |
| Server rejects (code not in this workflow's list — the case was re-classified while the form was open) | Form stays open with its text; message *"This case moved to another workflow. Choose what was done again."* and the list reloads |

**Default wording.** Changing *What was done* replaces the text only while the officer has not
edited it — the existing behaviour, kept.

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
must choose. **Why on the ticket and not from `GET /workflows/{id}`:** officers cannot read workflow
definitions, and a SEAH workflow is readable only by those who configure sensitive workflows — the
case view must not need that permission.

**`POST /tickets/{id}/actions` with `action_type: RESOLVE`** gains three optional fields:

| Field | Rule |
|---|---|
| `resolution_actor_kind` | `self` \| `organization` \| `external`. **Omitted → `self`** |
| `resolution_actor_organization_id` | required when `organization` (active org), or when `self` and the officer has several offices; ignored otherwise |
| `resolution_actor_external` | required when `external`, one of the fixed keys |

`resolution_category` is now validated against **the case's current workflow list**, not the global
list. 422 on any violation, naming the field.

**Compatibility.** Additive. A client that sends only `resolution_category` + `note` keeps working
and records `self`. The only narrowing is validation: a general-list code sent for a case in the
SEAH workflow is now refused — which is the point.

---

## 6. Sensitive paths (G-SENSITIVE — why this lane carries `+SENSITIVE`)

It touches SEAH (a SEAH list, SEAH rows in Excel), so the modifier applies regardless of size
([07 §4.2](../../engineering/07_work_items.md)). What the isolation review checks, separately from
correctness:

1. **No free text reaches the Excel** from either new column — only list labels and directory names.
   Test: a resolve with a name typed into `note` produces no trace of it in `build_report_row`.
2. **SEAH rows stay behind the existing gate** — a user without SEAH visibility gets no SEAH row,
   with or without the new columns. Test exists for the row; extend it to assert the columns.
3. **The case view does not widen workflow read access** — `resolution_options` is served from the
   ticket the officer can already open; no officer gains read on `GET /workflows/{id}`.
4. **The public share is unchanged** — `resolution_actor` is absent from `PUBLIC_REPORT_COLUMNS`.
5. **The SEAH list wording is reviewed by a SEAH officer** before merge (Q-06).

---

## 7. Non-goals

- **The case summary in Excel.** Declined, §1.
- **Editing resolution lists in Settings** → `GRM-119`.
- **Grouping actions across workflows** (e.g. "substantiated" vs "not" across general and road
  works) → Q-07, open, blocks nothing.
- **Resolved by on the complainant closure page or the public share link.**
- **Backfilling *Resolved by* for cases already resolved.**
- **A free-text "Other" for either field.**
- **Changing the photo requirement on resolve** (hard-blocked today, `GRM-073`).
