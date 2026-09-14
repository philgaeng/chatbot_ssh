# Resolution reporting — questions

**Audience:** internal — excluded from the public repository (lifecycle §10.4).

> **How to use this file.** Every question is one the code could not settle. Each carries a
> **recommendation** ([07](../../engineering/07_work_items.md) §3, `G-PRODUCT`).
>
> ✅ **Q-01 … Q-04 answered by the owner 2026-09-15**, all four as recommended, and folded into
> [`DESIGN-resolution-reporting.md`](DESIGN-resolution-reporting.md) and the items.
> ⏳ **Q-05 open — blocks the start of `GRM-118`** (it decides a column key).
> ⏳ **Q-06 open — blocks the merge of `GRM-116`** (not its start: build on the drafts).
> ⏳ **Q-07 open — blocks nothing.**

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

> **Answer:** —

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

> **Answer:** —

## Q-07 · Should actions group across workflows? ⏳ blocks nothing

**The issue:** once lists differ per workflow, the Summary tab pie shows general, road-works and SEAH
actions as separate slices. A manager asking *"what share of all grievances were upheld?"* cannot
read that across lists.

**Option:** give each action an `outcome` from a small fixed set (e.g. *remedied* · *referred* ·
*no action needed* · *not upheld*) and let the pie and pivot group on it.

**Recommendation:** **not now.** Nobody has asked for it, and it can be added later without
rewriting history — codes are unique across lists (DESIGN §3.1), so a code → outcome mapping
applies to past events as well. Raise it if the managers ask for cross-workflow totals.

> **Answer:** —
