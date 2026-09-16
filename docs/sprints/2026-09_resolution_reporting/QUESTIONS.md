# Resolution reporting — questions

**Audience:** internal — excluded from the public repository (lifecycle §10.4).

> **How to use this file.** Every question is one the code could not settle. Each carries a
> **recommendation** ([07](../../engineering/07_work_items.md) §3, `G-PRODUCT`).
>
> ✅ **Q-01 … Q-08 answered by the owner 2026-09-15**, and folded into
> [`DESIGN-resolution-reporting.md`](DESIGN-resolution-reporting.md) and the items.
> ✅ **Q-09 answered 2026-09-15.** ✅ **Q-10 decided 2026-09-15** in the owner's wireframe review —
> it simplifies and partly supersedes Q-07 … Q-09's answers. Every question in this lane is answered.
>
> ⭐ **Two answers changed the design after its first commit** — Q-06 (SEAH records nothing) and Q-07
> (one catalog instead of copied lists, with Q-08 settling who owns an entry). The questions below
> keep their original wording, so the reasoning that was overturned stays readable.

---

## Q-01 · What is `resolution_action`?

**Verified:** the Excel already has a *Resolution category* column fed by today's five fixed options.

**Options:** (a) the dropdown itself, made per-workflow, with the Excel column renamed *Resolution
action*; (b) a second dropdown under the existing outcome; (c) the officer's free text.

**Recommendation:** (a). One structured field, no free text, so no PII. (c) is the privacy breach
the lane exists to avoid.

> **Answer (2026-09-15):** (a) — the dropdown itself.

## Q-02 · Who can be named as the office that resolved the case?

**Options:** (a) the organization directory + a fixed list of outside bodies, no free text;
(b) directory + a free-text "Other"; (c) directory only.

**Recommendation:** (a). A typed value is where a person's name gets into the Excel. (c) forces an
admin to add *Police* as an organization before an officer can close a case.

> **Answer (2026-09-15):** (a). The list: Police · Municipality or ward office · Contractor · Court ·
> Other government office. See Q-06 for one proposed addition.

## Q-03 · When the officer acted themselves, what does *Resolved by* show?

**Options:** (a) the officer's office, derived from their position; (b) the fixed label
"Grievance officer"; (c) the officer's name.

**Recommendation:** (a). Every resolved row then names an office, so managers can compare offices
whether or not someone else acted. (c) puts a person's name in a forwarded file.

> **Answer (2026-09-15):** (a) — the officer's office.

## Q-04 · Where do the lists live, and who can change them?

**Verified:** "track" is a retired word; the three tracks named in the request are the three chatbot
menu paths (`intake_route`), each bound to a **workflow** per project. A ticket carries
`current_workflow_id`. ⚠ No project on the dev DB binds a road-hazard workflow.

**Options:** (a) on the workflow definition, seeded from three starter lists, editor later;
(b) fixed in code, keyed on the chatbot menu path; (c) as (a) plus a Settings editor now.

**Recommendation:** (a). Fits D-007 (SEAH is a workflow, not a mode), follows a case through
re-classification, and makes "this project has no road-works list" an honest, visible configuration
fact rather than a hidden lookup. (c) doubles the lane for a list the client edits rarely.

> **Answer (2026-09-15):** (a) — on the workflow, seeded. Editor deferred → `GRM-119`.

---

## Q-05 · Keep `resolution_category` as the internal key, or rename it to `resolution_action`? ⏳ blocks start of `GRM-118`

**Verified — three places the key `resolution_category` is already persisted:**

1. **`ticket_events.payload`** on every resolved case. Events are append-only; the old key is
   there forever, whatever we call it going forward.
2. **Saved quarterly report templates** store column keys as strings
   ([`schemas/reports.py`](../../../ticketing/api/schemas/reports.py) `QuarterlyReportTemplate.columns`).
   A template saved with `resolution_category` would silently lose the column after a rename.
3. **The action API** field (`TicketActionRequest.resolution_category`).

**Options:**

- (a) **Keep the key, change what people see.** Excel header *Resolution action*, form label *What
  was done*. Code and data keep `resolution_category`. New field is `resolution_actor`.
- (b) **Rename to `resolution_action` everywhere going forward**, with an alias that maps the old
  key on read — in event payloads, saved templates and the API — kept indefinitely.

**Recommendation:** (a). Managers never see a key; they see the header, and the header says
*Resolution action* either way. (b) buys a matching name at the price of a permanent alias in three
readers, and an alias forgotten in any one of them is a silently empty column in someone's quarterly
report. The mismatch between `resolution_category` and `resolution_actor` is cosmetic and is
explained in one line of `08` §2.3.

> **Answer (2026-09-15):** (a) — keep `resolution_category`; relabel only. Folded into `GRM-118`.

## Q-06 · Are the road-works and SEAH lists right? ⏳ blocks merge of `GRM-116`

**Drafts:** [`DESIGN`](DESIGN-resolution-reporting.md) §3.1. Written from the intake routes, the
chatbot's road-hazard and dust aliases, and the SEAH focal-point mitigation options
([`docs/seah/01_seah_intake_flow.md`](../../seah/01_seah_intake_flow.md) — *referral to support
services, police/legal information*).

**Three specific points to confirm with the client:**

1. **SEAH has no "not substantiated" outcome, deliberately.** A survivor-centred GRM refers and
   protects; it does not rule on belief. **Recommendation:** keep it absent unless the client asks
   for it in writing, and if they do, have a SEAH specialist word it.
2. **The SEAH list must be reviewed by a SEAH officer** before merge — wording on these cases is
   not a developer's call.
3. **Proposed addition to the outside-body list: *Users' committee*** (उपभोक्ता समिति). Road works
   in Nepal commonly act through one. **Recommendation:** ask the client; add it if they say it is
   used on this project.

**Why it blocks merge and not start:** until the editor exists (`GRM-119`), changing a list after
merge takes a data migration on every workflow that copied it. Before merge it is a constant edit.

> **Answer (2026-09-15):** *"1. follow your reco — no resolution for SEAH, therefore no need for 2.
> 3. accept your addition."*
>
> **Clarified the same day** — "no resolution for SEAH" had three readings (no list · SEAH out of the
> lane entirely · the draft list minus "not substantiated"). **The owner chose SEAH out of the lane
> entirely:** a case in a sensitive workflow records **neither** an action **nor** who took it; its
> resolve form is the text alone; the Excel's two columns are blank on its row. Reason: *Resolved by:
> Police* re-identifies as surely as an action label, and today a SEAH case is *forced* to pick
> *"Complainant demand rejected"*-style outcomes. The SEAH draft list is dropped, so point 2 (a SEAH
> officer's review) falls away. *Users' committee* is added to the outside bodies.
> → DESIGN §3.1.3 · `GRM-116` · `GRM-117` · `GRM-118`.

## Q-07 · Should actions group across workflows? ⏳ blocks nothing

**The issue:** once lists differ per workflow, the Summary tab pie shows general, road-works and SEAH
actions as separate slices. A manager asking *"what share of all grievances were upheld?"* cannot
read that across lists.

**Option:** give each action an `outcome` from a small fixed set (e.g. *remedied* · *referred* ·
*no action needed* · *not upheld*) and let the pie and pivot group on it.

**Recommendation:** **not now.** Nobody has asked for it, and it can be added later without
rewriting history — codes are unique across lists (DESIGN §3.1), so a code → outcome mapping
applies to past events as well. Raise it if the managers ask for cross-workflow totals.

> **Answer (2026-09-15):** *"This is a real concern — we need to find a balance between letting users
> naturally grow the list and crazy creation of duplicates. In the best case an agent can manage that
> and check new entries against what is already in the list and judge whether it justifies an addition
> or recommend an existing one."*
>
> **What it changed.** The recommendation (an `outcome` field, later) answered the wrong problem.
> Cross-workflow totals are hard *because* the same action gets created twice under two codes — so
> the fix is to stop the duplicate, not to group duplicates after the fact. That is impossible with a
> list **copied onto each workflow** (the first design): there is no single list to check against,
> and labels drift between copies. **Proposed and accepted the same day:** actions live in **one
> catalog**; a workflow selects from it; reuse gives shared codes, and shared codes give cross-workflow
> totals with no grouping field. The catalog is built in `GRM-116`; authoring and the agent in
> `GRM-119`. → DESIGN §3.1, §3.3.

## Q-08 · Many ministries on one platform — who owns a catalog entry?

**Asked by the owner, 2026-09-15:** *"We may have a lot of different workflows and modes, so we should
be able to manage this in the catalogue: what happens if tomorrow we have the Ministry of Interior or
Customs plugged into the same grievance redressal software?"*

**Verified:** the platform already answers this for every other catalog — roles, workflow definitions,
position types, project types carry `owner_organization_id`; `NULL` is global; an owned item is
visible only at its organization and below
([`11`](../../ticketing_system/11_roles_and_permissions.md) §3.3, built as SH-7). ⚠ But on the dev DB
**all workflow definitions are global**, so a second ministry would already see DOR's workflows.

**Recommendation:** apply the same rule to resolution actions — no new mechanism. Seed actions are
global; an `org_admin` authors actions owned by its node; a workflow may select an action only if the
workflow sits at or below the action's owner. The agent (`GRM-121`) checks a new entry only against
what the author can see, so it cannot leak one ministry's catalog to another; a `super_admin` view
finds duplicates across ministries and **promotes** one to global. The seed being global is a
platform-wide gap, not this lane's: log it separately and fix all catalog kinds together before a
second ministry is onboarded.

> **Answer (2026-09-15):** *"agree with reco of 8."* Folded into DESIGN §3.1.1 and §6 check 6 ·
> `GRM-116` · `GRM-117` (office search limited to the case's country) · `GRM-119` · **`GRM-120`
> opened** for the global seed. `GRM-116` unblocked.

## Q-09 · Where in Settings is the catalog managed? ⏳ blocks `GRM-119` only

**Asked by the owner, 2026-09-15**, before implementation.

**Verified — how Settings places catalogs today** (`app/settings/page.tsx`): four main tabs —
*Projects & packages · Organizations & officers · Workflows · Settings*. **A catalog sits as a
sub-tab beside the thing that uses it:** *Position types* beside the organization tree
(`OrganisationTab.tsx`), *Project types* beside *Workflows* (authors only — `super_admin`, `org_admin`).
The *Settings* main tab is `super_admin`-only, so it cannot hold anything an `org_admin` authors.
The workflow editor (`WorkflowEditor.tsx`) is steps, then a *Notifications* panel.

**Recommendation — two places, because there are two different jobs:**

1. **Workflows → *(open a workflow)* → a *Resolution* panel**, under *Notifications*. The job:
   *"which actions does this workflow offer, in what order?"* Pick from the catalog, reorder, remove.
   ⭐ **"+ New action" lives in the picker**, and runs the agent's duplicate check before saving — so
   the moment an admin is about to create a duplicate is the moment the agent suggests the existing
   one (the same pattern as `GRM-089`: create from the picker, don't send the admin elsewhere).
   On a sensitive workflow the panel is a single line: *"Sensitive workflows do not record a
   resolution action."*
2. **Workflows → a third sub-tab, *Resolution actions***, beside *Project types*, same visibility.
   The job: *"what is in the catalog, and is it healthy?"* The list the author's scope sees, with
   **Owner** (*Global* / *Department of Roads* …) and **Used by N workflows**; rename; retire (asks
   what replaces it where it is used). For `super_admin`, a *Possible duplicates across
   organizations* section with *Promote to global*.

**Why not one place.** Only the panel: retiring and renaming change **every** workflow using the
action, and doing that from inside one workflow's editor hides the blast radius. Only the sub-tab: an
admin building a workflow has to leave it, create an action elsewhere, and come back — which is where
duplicates get made, because the check happens away from the need.

**Why not *Settings → Settings*.** `super_admin` only; the `org_admin` of a second ministry must be
able to author its own actions (Q-08).

**Recommended in addition, for `GRM-116`:** ship the *Resolution* panel **read-only** in the workflow
editor. It is a list, and it removes the cost `GRM-119` names — *"a workflow created from scratch
silently gets the general list, and its author has no way to know"* — from day one rather than
whenever the editor lands. It adds a small `G-DESIGN` step to `GRM-116`.

> **Answer (2026-09-15):** *"I think we will pass all of them in a row, so no point to build something
> in G116 if we fix it in G119."* — **the two places as recommended; the read-only panel in `GRM-116`
> declined.** Consequences, folded the same day: `GRM-119` is scheduled rather than deferred
> (reclassified `debt` → `feature`, its follow-up replaced by an item file); it owes a committed
> wireframe (rule 9a.4 — no shipped screen to baseline), now [`ui/08`](../../ticketing_system/ui/08_resolution_actions_catalog.html);
> and the agent is split out as **`GRM-121`** to keep both items ≤ L. `replaced_by_code` moves into
> `GRM-116`'s migration so the table is created once.
>
> **Wireframe review with the owner, same day** — *"lets fix the specs as you recommend, especially the
> ownership issue."* ⚠ The drawn *Create a new action* could not work on any seeded workflow: they are
> all global, a global workflow selects only global actions, and an `org_admin`'s new action is owned
> by its organization. Behind it, a wider gap: workflow writes check the track, not the owner, so a
> district admin could change a workflow every ministry binds. **Folded:** `GRM-119` R1–R4 — **a
> global workflow is read-only to every organization's admin**; a new action is always created *for*
> a workflow and owned where that workflow can use it; edit/retire/restore only within reach.
> Consequence accepted with the fix: until `GRM-120`, only a `super_admin` changes a seeded workflow's
> actions. Also folded: *Restore*, *No replacement* on retire, *Edit* instead of *Rename*, an explicit
> *Save*, the panel on templates, owner wording matching *Project types*; in `GRM-121`, a server-side
> verdict, the lowest widen target, and a cross-root merge that always makes the kept action global
> (the draft's could not complete), with a confirmation frame. → DESIGN §3.1.1, §6 check 7 · `ui/08`.


## Q-10 · The authoring wireframe is too complex for future admins — what is the simplest model that keeps national statistics whole?

**Raised by the owner, 2026-09-15**, reviewing `ui/08`: *"I think the level of complexity is too high for
the future admins — we need to simplify. As well we should have a hard rule with max 8 different
resolution actions for the stated workflow."* Decided over one conversation; each step below is the
owner's answer to a proposal.

1. **Simplify to one panel per workflow.** Accepted. Cut: the catalog sub-tab, the ownership choice,
   retire/restore with replacement mapping, widening, the audited reason prompt, cross-ministry merge.
   *Owner: "I'm happy."*
2. **At most 8 actions per workflow** — a constant, enforced in the service. *Owner's own rule.*
3. **Lists are copied, never inherited.** Asked by the owner (*"if we already have 5 actions for all
   orgs and add a 6th and 7th while there are already 8 for a few places, then what happens"*).
   Answer: nothing — a workflow's list is its own. Inheritance would force blocking the ministry,
   breaking the limit, or silently dropping local actions. *Owner: "understood."*
4. **National statistics.** *Owner: "the trade-off is that when DOR wants national stats — it
   breaks."* Copying does not break them (copies share codes); **locally created actions do**. Proposed:
   **every local action counts as one shared action** (`counts_as_code`), pre-filled by the similarity
   check; reports gain a national grouping. *Owner: "YES — shared is only under 1 org."* → **no global
   actions**: shared = owned by a ministry.
5. **Every workflow and template belongs to an organization** — forced by 4, since a workflow with no
   organization cannot say whose actions it may offer. Existing ones get their projects' ministry in
   `GRM-116`'s migration. *Owner: "that is ok — but we need a section in settings/workflow where we
   assign the right owner — for instance these workflows belong to PD-ADB and not the whole of DOR"* →
   **`GRM-122`**. *"Templates should be owned by organization as well"* → templates owned, and a
   template is offered only to workflows of its organization or below.

**Consequences folded 2026-09-15:** DESIGN §3.1.1 (rewritten), §3.1.2, §3.3, §3.4, §6, §7 · `GRM-116`
(owned seeds and workflows, `counts_as_code`, limit, publish gate, rework checklist for the
uncommitted build) · `GRM-118` (national grouping) · `GRM-119` (L → M) · `GRM-121` (M → S) · **`GRM-122`
opened** · **`GRM-123` opened** (debt: merge and clean-up) · `GRM-120` narrowed · `ui/08` rewritten
(five frames).
