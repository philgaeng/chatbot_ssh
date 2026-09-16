# DECISION — an organization's grievances are its projects' grievances

**Status:** decided 2026-08-04 (Philippe). Built the same day.
**Supersedes:** [`DECISION-author-defined-slots`](DECISION-author-defined-slots.md) §2/§3 on the
routing anchor, and the inversion commit `c3d22de5`.
**Related:** [16 §3.1 org tree](../../ticketing_system/16_org_chart_and_positions.md) · [13 §2/§3](../../ticketing_system/13_projects_and_packages.md) · [14 §4](../../ticketing_system/14_platform_settings.md) · [09 reports](../../ticketing_system/09_reports_and_report_builder.md)

---

## 1. The decision

> **A grievance belongs to a project. Every organization named on that project sees it** —
> donor, ministry, department, contractor alike. An organization named on **one lot** sees that
> lot only. And because organizations form a tree, **a parent sees everything its children
> see**, deduplicated.

"Which grievances are the Department of Roads'?" is answered by **membership** —
`project_organizations` / `package_organizations`, widened down the org tree — never by a label
written onto each grievance.

## 2. What this replaces, and why it was wrong

`project_types.routing_org_role` named **one** of a type's organization roles as the anchor.
Whichever organization filled that slot got stamped onto every grievance
(`tickets.organization_id`), and reporting filtered on that stamp.

The stamp can only hold one value, so **one organization owned the grievance and every other
organization on the project owned nothing.** On KL Road, DOR was the anchor: ADB, the donor
funding the road, matched **zero** grievances. There is no value of the anchor that makes both
reports right, because the question "whose grievance is this?" has more than one true answer.

The anchor was also **authored** — someone had to pick it per type — which made an unavoidable
modelling error look like a configuration choice.

Two things confirmed the shape rather than merely simplifying it:

- **The codebase already did this for locations.** `report_rows._location_codes_with_descendants`
  expands a location filter down its tree with a recursive CTE and matches anything inside. The
  org tree has the identical shape and already had `descendant_org_ids` (cycle-guarded, used by
  admin scope). This is the same rule on the tree we had already built.
- **The old filter was already marked as a mistake.** `reports.py` carried
  `organization_id: "Legacy filter; prefer project/location filters"` and did
  `r["organization_id"] == organization_id`.

## 3. The two edges, decided

| Question | Decision |
|---|---|
| An organization named on **one lot** of a 5-lot project | Sees **that lot's** grievances only. Naming a contractor on lot 3 is a statement about lot 3 — a distinction the single stamp could not express at all. Its parent organization still sees everything, through the tree |
| **GRC convening**, the one behaviour the stamp drove | Members now resolve from the **project's GRC staffing** (the GRC roles scoped to the project/location/lot), like every other assignment. A GRC is convened for a project, not for an organization. A project with no GRC staffing falls back to the old organization+location lookup so a convening still notifies somebody |

## 4. As built

**`ticketing/services/org_reach.py`** is the rule, in one place:

- `org_reach_ids` — the organization + its descendants
- `project_and_package_reach` — its projects and its lots, with lots inside a covered project
  subtracted as redundant
- `ticket_filter_for_org` — a WHERE clause; **`false()`** when the organization is named
  nowhere (an organization with no projects has no grievances, which is not "no filter")
- `organization_ids_for_project` — every organization on a project, for the report column

Applied in: `GET /tickets?organization_id=`, `report_rows.build_ticket_query` /
`load_report_rows`, and the XLSX export (the naive post-filter deleted). The export's
**"Organization"** column became **"Organizations"** and lists every organization named on the
project — one id was always one true name and several missing ones.

**Retired:** `routing_org_role` is gone from the project-types API, its validation, the
authoring UI, the project screens and the TS types. The **column survives**, unused, until a
cleanup migration drops it (with `project_actor_roles` and the other legacy fields).

**`tickets.organization_id` survives as a descriptive stamp** — the column is NOT NULL and rides
along in a few payloads. It takes the project's **first required** organization role, not the
first listed: the back-fill migration writes catalog keys alphabetically, so "first listed" on a
migrated type is `donor`, an accident of sorting. Nothing reads it to decide who sees what.

**Project creation** fills the type's first required role with the chosen organization
(`first_required_role_key`), replacing "fills the anchor slot".

## 5. What did *not* change

- The type still names **which organizations a project must have**, and go-live's **B1** still
  blocks when a required one is missing. Only "which one is *the* one" died.
- **Assignment never used the stamp** — `_scope_candidates` ignores it by documented design;
  officers are matched by workflow role and jurisdiction.
- **SEAH suppression** is untouched: a donor still receives nothing on a sensitive case.

## 6. Consequences accepted

- **A grievance now appears in several organizations' reports.** That is the point, and it makes
  per-organization counts non-additive — two organizations' totals may cover the same grievance.
  Any future "grievances per organization" chart must not sum them into a whole.
- **The delete guard still counts the literal stamp** (`Ticket.organization_id`) when refusing to
  delete an organization. That is a referential-integrity check, not a report, and was left
  alone deliberately.
