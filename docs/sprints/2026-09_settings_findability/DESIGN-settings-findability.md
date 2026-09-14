# Design — Settings findability & inline creation (September 2026)

**Audience:** internal — excluded from the public repository (lifecycle §10.4).
**Governed by:** [`engineering/07_work_items.md`](../../engineering/07_work_items.md) ·
[`engineering/05_frontend.md`](../../engineering/05_frontend.md) §9a (the design gate) ·
[`ticketing_system/ui/05_ui_copy_style.md`](../../ticketing_system/ui/05_ui_copy_style.md) (all on-screen wording).
**Origin:** user request (client feedback, 2026-09-07). **Lane:** `settings-ui`.

> This is the shared design note for `GRM-085` … `GRM-090`. Six items, one design, one questions
> register — which is what makes them a lane rather than six loose rows ([07](../../engineering/07_work_items.md) §1.2).

---

## 1. Brief — what the screens are for, and what is wrong

**Who reads them.** A Nepali government official — career civil servant in a district or ministry
office, reading English as a second language, not technical
([`ui/05`](../../ticketing_system/ui/05_ui_copy_style.md), confirmed by the owner 2026-09-07).
⚠ **Not the rural / low-literacy complainant audience** — that governs the chatbot and webchat
surfaces ([doc 16 §5.2](../../ticketing_system/16_org_chart_and_positions.md)), not this one. What
carries over from the complainant standard and what does not:

| Carries over | Does not |
|---|---|
| Plain, short English; the simpler of two words | Icon-led or picture-led navigation |
| Severity in **words**, never colour alone ([`ui/05`](../../ticketing_system/ui/05_ui_copy_style.md) rule 6) | Reading-level constraints below ordinary official English |
| BS dates only | Avoiding tables or multi-column layouts |

**What they are trying to finish.** Two jobs, and Settings currently obstructs both:

1. **Find one record** among many. Measured on the live stack: **57 officers across 57 positions**,
   and an organization forest with no search or filter control **at all**
   ([`OrgTree.tsx`](../../../channels/ticketing-ui/components/settings/org/OrgTree.tsx) — the file has
   no `q`, no filter state, nothing). The officer directory has a search box, but it matches only
   three fields, so the two columns an admin actually scans by — Office and Project / area — are
   not searchable.
2. **Add a record while already in the flow that needs it.** Setting up a project, the admin reaches
   Organizations and Staffing and finds pickers that can only select something that already exists.
   The escape route is another tab and a lost place — and the copy admits it:
   *"Link organizations to this project first (Projects & packages → Partner organizations), then
   invite officers"*
   ([`OfficerJurisdictionForm.tsx:573`](../../../channels/ticketing-ui/components/settings/OfficerJurisdictionForm.tsx#L573)).

**One sentence:** *find things, and add things, without leaving the screen you are on.*

## 2. IA — the objects and their containment

Nothing in this lane changes what an object **is**. Three decisions about how they are arranged:

### 2.1 Top-tab order is outcome-first, and that inverts the dependency order

New order (`GRM-085`): **Projects & packages · Organizations & officers · Workflows · Settings.**

⚠ **This is the opposite of the build order.** A project's staffing needs officers, who need
organizations; its levels need workflows. Dependency order would read Workflows → Organizations →
Projects. The new order is defensible anyway, and the reason is worth recording because it is the
only thing that makes it not-arbitrary:

> **The project console already sequences the dependencies.** Its left rail walks Identity →
> Grievance workflows → Packages → Organizations → Staffing, and the go-live panel names what is
> missing and blocks on it. So the guided path lives *inside* the project, and the top tabs are free
> to be ordered by **what the admin came to do** rather than by what must exist first. Ordering top
> nav by dependency would only be right if nothing downstream sequenced them — and something does.

**Non-goal:** no tab is renamed. *"Workshop" in the client's note was a typo for **Workflows**,
confirmed by the owner 2026-09-07.*

### 2.2 The organization list is a forest, and filtering must not flatten it

[`OrgTree`](../../../channels/ticketing-ui/components/settings/org/OrgTree.tsx) renders two groups —
the government reporting line, and independent roots (contractors / development partners). **The tree
*is* the parent relationship.** Two consequences:

- **A "parent organization" filter is dropped** from the client's request. It duplicates clicking a
  parent node, and it is the control most likely to be reached for *instead* of reading the tree,
  which is the one thing the tree is for. Owner decision 2026-09-07 (Q-02).
- **Search filters in place, keeping ancestors visible.** A match deep in the forest is meaningless
  without the line above it: *"Division Office"* is not an answer, *"DOR → Provincial Office 1 →
  Division Office"* is. Ancestors render as context — present, de-emphasised, not counted as matches.

Filters kept: **Type** (`org_category` / `unit_type`) and **Area** (`territory_location_code`).

### 2.3 Staffing levels get progressive disclosure, packages-style

Staffing (`GRM-090`) currently renders every level, every slot and every assign-control expanded, so
the two blockers on the KL Road project sit below a screen of controls that are already satisfied.
Levels become collapsible with the same disclosure pattern packages already use
([`PackageRow.tsx`](../../../channels/ticketing-ui/components/settings/projects/PackageRow.tsx)).

⭐ **Default state is the whole design decision here.** Collapse-everything hides exactly what the
screen exists to surface. **Collapsed by default, except a level with an unmet required slot**, and
the collapsed header carries the count **in words** — *"Needs an officer"* — never a bare red dot
([`ui/05`](../../ticketing_system/ui/05_ui_copy_style.md) rule 6;
[`05_frontend`](../../engineering/05_frontend.md) rule 8.2).

## 3. Wireframe — the baseline is the shipped screen

**Owner decision 2026-09-07 (Q-04): the live screens replace the mockup.**
[`ui/04_projects_packages_redesign.html`](../../ticketing_system/ui/04_projects_packages_redesign.html)
is stale (`GRM-064` — it still shows Locations and Packages as separate sections and organizations
inside the package card) and is **not** being hand-refreshed. It is marked superseded where it is
cited, per [`05_frontend`](../../engineering/05_frontend.md) rule 9a.3.

So for `GRM-085`, `GRM-087`, `GRM-089` and `GRM-090` the shipped route **is** the wireframe baseline,
and each item states its delta against it. ⚠ **One exception:** `GRM-086` adds a control surface that
does not exist on any shipped screen — a filter bar over a tree. That one produces a committed
`.html` wireframe next to its spec before build, per rule 9a.1. It is named in the item as a required
artifact, not assumed.

*Why the exception rather than the rule: a mockup earns its cost when it decides a shape nobody has
seen. Redrawing a screen that renders in a browser today is transcription, and a transcribed mockup
is the exact artifact that goes stale — which is how `GRM-064` happened.*

## 4. Direction

No new visual language. Tokens, palette and icons from
[`ui/02_design_system.md`](../../ticketing_system/ui/02_design_system.md); the existing filter-chip
group in the officer directory (All / Standard / SEAH) is the reference for the new filter controls,
so the two screens converge rather than diverge.

**Copy is governed, not invented** — every string routes through
[`ui/05`](../../ticketing_system/ui/05_ui_copy_style.md), including its glossary. Notably:
`org_category` surfaces as **"Type"**, never "category" or "entity"; the area control is
**"Search area"**, never "reach"; level labels come from `location_level_defs`
(`level_name_en` — "Province", "District"), never hardcoded, so the control stays correct outside Nepal.

## 5. State + responsive contract — binding on every item in this lane

**Three rendered states, not two** ([`05_frontend`](../../engineering/05_frontend.md) rule 3.4):

| State | Requirement |
|---|---|
| **Loading** | Skeleton, `aria-busy`. The officer directory's existing skeleton is the pattern |
| **Error** | Through `formatUserFacingError` + one `<ErrorNotice>`. Never a raw status code (F10/F11) |
| **Empty — nothing exists** | Says so, and offers the create action |
| **Empty — nothing matches** | ⭐ **A different state.** Names the terms, and offers **Clear filters**. An admin who cannot tell "no results" from "no data" concludes the system is broken |
| **Dense** | 57 officers today, and the roster is fetched whole. Filtering stays client-side (§6) |

**Responsive.** 360 px is the floor. The filter bar wraps to a second row; it never scrolls
horizontally and never collapses into an icon-only control. Tree indentation caps so a
fourth-level org does not push its own name off-screen.

**Colour is never the only signal**, on any of it.

## 6. Implementation contract — what is frozen now, and what each item freezes

**Frozen for the lane:**

- ⭐ **All filtering and searching in this lane is CLIENT-side, and no API changes.** Verified
  2026-09-07 by reading the endpoint
  ([`locations.py:362`](../../../ticketing/api/routers/locations.py#L362)): `GET /api/v1/organizations`
  accepts `country`, `active_only`, `root_id`, `tree` and `q` — and **no** filter for
  `org_category`, `unit_type` or `territory_location_code`. It would have been the obvious place to
  add them. **It is the wrong place**, for a reason that only shows up when you read what `q` does:
  it returns a **flat filtered set**, so an organization whose *parent* does not match the term
  comes back without its parent, and the forest cannot be rebuilt. Server-side `q` is therefore
  structurally incapable of §2.2's ancestor rule.
  **`OrgTree` already fetches the entire forest in one call** (`listOrganizations(undefined, {tree:true})`),
  with `org_category`, `unit_type` and `territory_location_code` present on every node — so matching
  in the client is both less work and the only correct option.
  ⚠ **This retires `G-CONTRACT` from `GRM-086`'s profile.** It was assumed to fire at intake and it
  does not.
- **The existing server-side `q` is left alone.** It is unused by this screen after `GRM-086`, but
  other callers may depend on it and removing it is not this lane's change.
- **Officer filtering stays client-side too**, over the full `listOfficerRoster()` payload — the
  standing `TODO` for server-side search and pagination in
  [`OfficersDirectory.tsx`](../../../channels/ticketing-ui/components/settings/officers-v2/OfficersDirectory.tsx)
  is **explicitly not this lane's work** (§7).
- **Modals are reused, never rebuilt.** `GRM-089` opens the existing
  [`OrgCreateModal`](../../../channels/ticketing-ui/components/settings/OrgCreateModal.tsx);
  `GRM-090` opens the existing
  [`ProjectOfficerModal`](../../../channels/ticketing-ui/components/settings/ProjectOfficerModal.tsx).
  Both must return to the picker with the new record **selected**, not merely created — a modal that
  creates a record and drops you back at an empty picker has moved the problem, not solved it.

**Frozen per item, before that item's build starts** (§9a step 6): the props, the exact copy strings,
and the filter state shape.

## 7. Non-goals

- **No server-side search or pagination** for either list, and the `TODO` that asks for it stays.
- **No change to the org tree's two-group split**, and no change to what an org *is*.
- **No tab renamed**, and no tab added or removed.
- **No change to SEAH visibility.** The directory's Standard / SEAH filter keeps its current
  behaviour exactly; new filters compose with it and do not replace it.
- **No refresh of the `ui/04` mockup** (Q-04) — it is marked superseded, not redrawn.
- **No change to `GRM-064`'s underlying screen.** Closing that row is a documentation act here.

## 8. What this lane does not verify

Every item is `planned` at intake. G-VERIFY is satisfied per item by an e2e spec in the harness QA-04
built — the settings routes are already driven, so these extend existing specs rather than adding a
suite. ⚠ Two known environment traps that will bite anyone writing those specs:

- **`GRM-081`** — a fresh seed derives officer display names from the email (`l1-officer@grm.local` →
  `L1-Officer`), and a dev box shows `Site Officer L1`. **Key specs on the email**, never the name.
  Fresh roster is **17** officers; this dev box has **67**. A spec asserting "57 officers" is a spec
  that fails in CI.
- **`GRM-080`** — a cold stack renders as `super_admin` for ~10 s before the roster resolves. A
  settings spec that asserts on the admin gate races it.
