# Design — Settings redesign (Handover A deliverable)

> **Produces:** the Handover A deliverables — resolved D-forks, new IA map, component tree, and interaction specs — that gate the Handover B Part 2 rebuild.
> **Reads on top of:** [HANDOVER-A-settings-ux-redesign-brief.md](archive/HANDOVER-A-settings-ux-redesign-brief.md) (the mandate) and [`ui/03_admin_setup_flow_evaluation.md`](../../ticketing_system/ui/03_admin_setup_flow_evaluation.md) (OC-06, the evidence). Every decision below traces to an OC-06 finding (F-number / S-seam) or a doc-16 data-model fact.
> **Status:** DRAFT for cowork review. §1–§4 (forks, IA, component tree, interaction specs) are the **milestone that unblocks Part 2** — the brief §9 says "when you finalize the component tree, that's the signal Part 2 can start." §5 (full per-journey wireframe atlas incl. every empty/loading/error/bilingual state) is **produced** — [`settings-wireframes.html`](settings-wireframes.html) (happy path + variants) + [`settings-state-atlas.html`](settings-state-atlas.html) (all states).
> **Design-system contract (non-negotiable, from the brief §3):** 5 hue families (blue/red/amber/green/violet) + gray/slate; banned hues (`orange/yellow/indigo/purple/teal/sky`) stay dead; `text-gray-600` floor; Lucide via `@/lib/icons`; no emoji; tokens from `lib/design-tokens.ts`, never raw color soup; Nepali via `_ne` fields, never fabricated.

---

## 0. The one-paragraph thesis

The current Settings surface scored **48%** as a daily driver because the four setup journeys are stitched together with **cross-tab jumps the user has to make from memory** (OC-06 seams S1/S2/S5) and because the surface **speaks developer, not Nepali civil-servant** (F10/F11, role slugs, color-only severity). The redesign does two things and only two things: **(a) it makes every seam an in-place guided step** so the user never has to carry a value (role key, org id, project link) across a tab boundary, and **(b) it makes the whole surface legible to a low-IT-literacy GoN admin** — plain labels, friendly errors, bilingual inline, text severity, and one always-visible "here's the one thing blocking go-live" line. The org-chart feature (org tree + position types + invite-by-position) folds in as the mechanism that collapses the flagship 7-decision invite into **one comprehensible action** (doc 16 §5.2). We do **not** grow the top-tab count to do it.

---

## 1. The six D-forks — resolved (deliverable 5)

Each decision states the call, the reasoning, and what it commits the component tree to.

### D1 — How many top tabs; does the tree absorb the flat list?

**Decision.** **Keep four task-domain tabs; add a fifth surface that is a _landing_, not a peer tab.** The org tree **replaces** the flat org list (no second org editor). Position types become a **secondary panel inside Organisation**, not a top tab. Officers stay a **section inside Organisation** (a person is someone holding a position at an org unit), not a fifth tab — and remain reachable from Project staffing. **Net new top tabs from the whole org-chart feature: zero.**

```
Settings landing  →  Setup & go-live overview   (the guided spine; not a domain tab)
  ├─ Tab 1  Organisation      (org tree ▸ position types ▸ officers)
  ├─ Tab 2  Workflows & roles (one guided flow)
  ├─ Tab 3  Projects          (project ▸ packages ▸ staffing ▸ go-live detail)
  └─ Tab 4  Platform          (locations ▸ reports ▸ project-types ▸ admin access)   [admin/super only]
```

**Why.** OC-06 §7 is explicit: the two "new tabs" (OrgTree, PositionTypes) must **not** both become top tabs — the tree replaces the flat list, position-types is a set-once ~20–50-row catalog that shouldn't get peer weight (D3). The devil's-advocate "hates the sprawl," but the sprawl OC-06 measured is *within-tab* (read-only panels, sub-tabs, cross-tab jumps), not the four domains. Four domains map cleanly onto the civil-servant mental model — *my structure / how grievances are handled / my project / platform admin*. The real fix for "I finished tab A, now what?" is not fewer tabs; it's the **Setup & go-live overview** landing that threads the four journeys and always names the next step (D6).

**Commits the tree to:** one `OrgTree` surface (kills `OrganizationsTab`'s flat list), a `PositionTypesPanel` under Organisation, an `OfficersDirectory` section under Organisation, and a new `SetupOverview` landing.

### D2 — Invite: how much stays visible after pre-fill? (the make-or-break)

**Decision.** Picking **tree node → position** renders a **human-readable outcome card**, not a form. Role, organisation, and location scope are **pre-filled and hidden behind an "Adjust" disclosure**. The **override badge appears only** when the admin opens Adjust and changes a matrix default. Every pre-filled value shows its **provenance** ("from position: SDE"). No role is pre-selected as a silent default (F21) — the *position* is the choice; if none is picked the outcome card doesn't render.

```
┌─ Invite officer ─────────────────────────────────────────────┐
│  1  Who, and where in the ministry?                          │
│     Office:  [ Jhapa Division Office            ▾ ]  (tree)   │
│     Position:[ Senior Divisional Engineer (SDE) ▾ ]          │
│     Email:   [ ______________________ ]                      │
│                                                              │
│  ┌─ This will create ───────────────────────────────────┐   │
│  │  SDE, Jhapa Division Office                           │   │
│  │  → acts as  Site Safeguards Focal Person             │   │
│  │             (from position: SDE)                     │   │
│  │  → covers   Jhapa district                           │   │
│  │             (from office territory)                  │   │
│  │  → on       KL Road project                          │   │
│  │                                                      │   │
│  │  [ ▸ Adjust role, area, or project ]   ← collapsed   │   │
│  └──────────────────────────────────────────────────────┘   │
│                        [ Cancel ]   [ Send invite → ]        │
└──────────────────────────────────────────────────────────────┘
```

**Why.** OC-06 §7 makes this the single deliverable that decides whether the org-chart feature "delivers or just adds a tab": *"If picking a position drops four pre-filled-but-visible editable fields in front of a low-IT user, we've re-introduced the complexity we're removing."* The outcome card is the whole point — it turns 7 decisions (F5) into 3 inputs and a confirmation. Full interaction spec in §4.1.

**Commits the tree to:** `InviteOfficer` (orchestrator) → `InviteOutcomeCard` + `InviteAdjustDisclosure` + `ProvenanceHint` + `OverrideBadge`.

### D3 — "Review holders" prompt: informational or actionable?

**Decision.** **Actionable.** Editing a position type's `default_role_key` opens an **opt-in "Review & re-sync N holders"** action (not a bare "12 holders won't change" notice), reconciled with the transfer-refresh flow so there is **one** re-sync surface, not two. Doc 16 §4 is explicit that the edit does **not** silently re-sync — so the drift must be **visible and fixable**, not silent and not merely announced.

```
Position type "SDE" saved.  Its default role changed: Site Safeguards Focal → Field Engineer.
┌──────────────────────────────────────────────────────────────┐
│  12 officers currently hold SDE. Their role was NOT changed.  │
│  [ Review 12 holders → ]        [ Leave them as they are ]    │
└──────────────────────────────────────────────────────────────┘
   Review opens a list: per holder, current role vs new default,
   checkbox to re-sync; "Re-sync selected" runs the same path as
   the transfer role/scope refresh (doc 16 §4). All-or-nothing per batch.
```

**Why.** A bare notice leaves the admin at "…so what?" (brief D3). The re-sync must route through the same `user_roles`/`officer_scopes` refresh the transfer flow uses (doc 16 §3.3/§4) so we don't build two divergent re-sync paths.

**Commits the tree to:** `ReviewHoldersModal`, shared with the transfer-refresh flow inside `OfficerManageModal`.

### D4 — Nepali: bilingual-inline now, or store-only?

**Decision.** **Bilingual inline now**, where `_ne` is present: render `English / देवनागरी` (e.g. "SDE / वरिष्ठ डिभिजनल इन्जिनियर"), **English fallback** when `_ne` is absent, and **never fabricate** — an absent `_ne` is marked for the translator sheet, not filled. A single `<Bilingual>` render helper is the seam; full i18n infra (chrome strings, locale switch) is the separate RB-1 ticket.

**Why.** The data model is Nepali-first (`default_language="ne"`) and `_ne` columns ship in OC-01/02, but the surface has **zero i18n scaffolding** (F14) — `display_name_ne` would be the first bilingual data in a portal that can't render bilingually. Inline bilingual is high-value for this exact audience and cheap (one helper), and it stops us adding new hardcoded English a later i18n pass must unpick (OC-06 §6 recommendation).

**Commits the tree to:** `shared/Bilingual.tsx` (used by every `_name`/`display_name` render across Organisation, Officers, Position types).

### D5 — Workflows & roles: merge into one guided flow?

**Decision.** **Merge.** One flow: **workflow → steps → bind role**, where the step's role picker shows **only roles valid for that workflow's track** and, for excluded roles, **explains why** ("Not shown: wrong track — this is a Standard role and the workflow is SEAH"). The role catalog stays editable (it's the behavior catalog) but is reframed as *the thing the flow binds to*, cross-linked from the step binder, not a sibling sub-tab with no link.

**Why.** The step→role binding is the central seam S1 — today three sibling surfaces (workflow steps, role catalog, officer holders) with no cross-link, and the binding has zero track validation (F2). Handover B SH-2 makes the server reject wrong-track/non-existent bindings; the UI's job (brief §3, last bullet) is to **surface that rejection well** and, better, to **prevent the user from ever selecting an invalid role** by filtering the picker and explaining the exclusion. Slugs become human labels throughout (F11); the step is shown as a **cast** of role slots (§4.3), and the mystery "Archetype" dropdown is renamed "acts as" with one shared role/step vocabulary (F20).

**Commits the tree to:** `WorkflowsRolesFlow` → `WorkflowEditor` + `StepEditor` + `StepRoleBinder` (valid-only picker + "why excluded") + `RoleCatalog`/`RoleEditor`, all extracted out of `page.tsx`.

### D6 — Go-live: where does the checklist live and how does it read?

**Decision.** Promote it out of the buried, stale, color-only Projects panel into the **Setup & go-live overview** (the landing spine) **and** keep a per-project detail. It **live-refreshes after every structural mutation** (F9), reads as **one plain-language "next blocker" line** (F17 — replaces the two terse verdicts), and every item carries a **text severity label** ("Blocking" / "Warning") beside the color dot (F11). Each blocker's "Fix" deep-links to the exact surface + field.

```
┌─ Setup & go-live ────────────────────────────────────────────┐
│  KL Road is 1 step from going live.                          │
│                                                              │
│  ● Blocking   No L2 officer for package "Section A"          │
│               → Fix: Projects ▸ Staffing ▸ Section A         │
│  ○ Warning    No Nepali name on 3 org units                  │
│               → Review (won't block go-live)                 │
│  ✓ Done       Workflow published · Actors assigned · …       │
│                                                              │
│  [ Go live → ]   (enabled only when no Blocking items remain)│
└──────────────────────────────────────────────────────────────┘
```

**Why.** OC-06 F9/F17 + brief D6: the checklist "silently lies until you click Refresh," conveys blocking-vs-warning by color only, and splits `can_activate` from `can_accept_tickets` into two confusing verdicts. One spine, live, plain-language, one next blocker.

**Commits the tree to:** `SetupOverview` + `GoLiveSpine` (elevates and live-refreshes today's `ProjectGoLivePanel` logic; `project_go_live.py` already emits plain-language messages — F-strengths — we surface them properly).

---

## 2. New IA map (deliverable 1)

### 2.1 Surface structure

```
Settings
│
├─ ⌂ Setup & go-live  ......................  LANDING (all admins; scoped to their projects)
│     • single "next blocker" line + live checklist  (D6, F9, F17)
│     • entry cards → the four domains, each showing its own done/blocked state
│     • replaces: the stale go-live panel buried in Projects
│
├─ ▸ Organisation  ..........................  TAB 1  (org_admin standard / super_admin)
│     ├─ Org tree            tree replaces flat list; inline add-child/edit/territory  (F8, D1)
│     │                      bilingual node labels  (D4)
│     ├─ Position types      secondary panel; matrix editor; review-holders action  (D1, D3)
│     └─ Officers            directory + Invite-as-result  (F5, D2); position-title display  (§5.1)
│
├─ ▸ Workflows & roles  .....................  TAB 2  (org_admin standard / super_admin author; project_admin + officer_admin read-only, F12)
│     └─ one guided flow: workflow → steps → bind role
│           valid-only role picker + "why excluded"  (S1, F2-surface, D5)
│           role catalog cross-linked, human labels not slugs  (F11)
│
├─ ▸ Projects  ..............................  TAB 3  (project_admin own scope / country / super)
│     ├─ Project + packages
│     ├─ Actors        add org + role AS AN ACTION (kills read-only S2/F8)
│     ├─ Staffing      guided inline invite (keep S3/S4 strengths); empty-state CTA (F23)
│     └─ Go-live detail feeds the overview spine  (D6)
│
└─ ⚙ Platform  ..............................  TAB 4  (super_admin; org_admin reports only)
      ├─ Locations
      ├─ Quarterly reports   (keep QuarterlyReportSettings)
      ├─ Project types       (F10: real seed action or "contact admin", never "run migrations")
      └─ Admin access
```

Persona gating follows the 4-tier ladder (§2.5 / doc 11 §2): `org_admin` is **track-scoped** (a SEAH admin must not get standard-track org-tree rights, F4) — enforced server-side by Handover B SH-7; the UI gates as **defense-in-depth** (reads `canManageStructure`, which today is threaded but never read, F3).

### 2.2 Every OC-06 seam, and how the new IA removes it

| Seam (OC-06 §1) | Today | New IA |
|---|---|---|
| **S1** Workflows ↔ Officers: step binds a bare `role_key`, three unlinked surfaces | `page.tsx:1579,4674` | **Merged flow (D5):** step binder picks from valid-only roles, cross-links to the catalog; role labels not slugs. |
| **S2** Org → Projects: org editor's project panel is **read-only** | `page.tsx:2320-2337` | **Action, not read-out (F8):** actor authoring ("give this org a project role") is an inline action; org tree + project actor share one add-role affordance. |
| **S3** Projects needs Orgs (already guided) | `ProjectActorAddRow.tsx:84-100` | **Kept** — inline "+ New organization" retained as a strength. |
| **S4** Projects needs Officers (already guided) | `ProjectOfficerModal.tsx:91-116` | **Kept + unified** — "Invite new" reuses the one `InviteOfficer` component. |
| **S5** Officers needs Projects: invite org list empty unless pre-linked | `OfficerJurisdictionForm.tsx:570-574` | **Prerequisite carried into the flow (brief §5.4):** the invite knows which project(s) the org is linked to; if unlinked, it offers to link inline instead of dead-ending. |
| **S6** Go-live checklist goes stale, "Fix" only scrolls | `page.tsx:3072,3441` | **Overview spine (D6):** live-refresh on every mutation; "Fix" deep-links to surface+field. |

### 2.3 Language / legibility pass (applies to every surface)

These are cross-cutting and belong to the IA, not one screen:

- **Human labels, never slugs** (F11): `site_safeguards_focal_person` → "Site Safeguards Focal Person" everywhere a role is shown. A `RoleLabel` helper resolves slug→label with the catalog `display_name`.
- **Friendly errors** (F11): every admin mutation routes its failure through `lib/user-messages.ts` `formatUserFacingError` (which **exists and is unused**) via one `ErrorNotice` component. No raw `API 409 {…json…}`.
- **Text severity beside color** (F11): "Blocking"/"Warning" labels, never color-only — fails low-literacy and color-blind users.
- **No developer copy in empty states** (F10): "Run Alembic migrations" / "mock_tickets --reset" become either an admin-triggerable action or "contact your administrator."
- **Bilingual inline** (D4/F14): `<Bilingual>` on every name field where `_ne` is present.

### 2.4 Org identity vs hierarchy vs project participation (the contractor question)

Three distinct concepts the schema **already separates** — and the UI must not conflate them (the first wireframe draft wrongly nested a contractor *under* the ministry):

| Concept | Table | Owner | Editing surface |
|---|---|---|---|
| **Identity** — an org exists | `organizations` (id, name, `display_name_ne`, country) | whoever needs it (see authz below) | Organisation ▸ Org tree · or inline at Projects ▸ Actors |
| **Reporting hierarchy** — the GoN chain | `organizations.parent_organization_id` (doc 16) | `org_admin` (standard) | Organisation ▸ Org tree (reporting-line group) |
| **Project participation** — org acts in a project as a party | `project_organizations` + `project_actor_roles` (`main_contractor`, `implementing_agency`, `donor`, …) | `project_admin` (standard), own scope | Projects ▸ Actors |

**The tree is a forest, not one tree.** `parent_organization_id` is nullable. The government reporting line is one *rooted* subtree (Ministry → Department → Division Offices); **contractors and development partners are their own roots** (`parent = null`), never nested under a ministry — and **each root can itself be a multi-level subtree**. This:
- keeps the "belongs to DoR" subtree check (doc 16 §3.1) honest — a contractor isn't swept into the ministry;
- makes the deployment **replicable per ministry** and **multi-ministry-ready** — the surface treats "a ministry" as *a* root, not *the* root, so a second ministry (or a per-ministry clone) drops in cleanly;
- puts **ADB (a `development_partner`) as its own root** — an international donor, independent of any ministry;
- **lets a company/donor own its own hierarchy** — a main contractor holds subcontractors, a donor its country/regional offices. `parent_organization_id` is generic, so `company` may parent `company`; subtree checks, territory, and admin scope (§2.5) all apply uniformly, and whoever has scope over the root manages its children (the org_admin who owns it, or the project_admin who created it). **OC-01 unit_type validation** must therefore allow `company`/`development_partner` as roots and permit `company`→`company` nesting; add a `sub_contractor` / `branch` unit_type only if the government wants the distinction (lean: permissive — don't over-model private structure).

**Who creates contractors.** Contractors are **`third_party`** orgs (§2.5 actor types), which are the *delegable* category: an **`org_admin`** creates them anywhere in its scope, and a **`project_admin`** creates them for its own project (honoring doc 11 §2.3 — "subcontractors join mid-project; `project_admin` links orgs to party roles without waiting for a higher admin"). Editing the **reporting tree** (re-parent / unit_type / territory / CSV import) and creating a **new institutional root** (government / local-gov / donor) stay with `org_admin` / `super_admin` respectively. This corrects OC-06 F3's blanket `is_any_admin` gate *toward* scoped, category-gated creation.

> **As-built alignment:** global `/organizations` CRUD is currently gated by `MANAGE_ORG_STRUCTURE` (standard-track); **SH-7** generalizes that gate to the org-subtree scope + `org_category` rules above. Until SH-7 lands, treat the current gate as the org-tier stand-in.

**Contractor dedup — a guardrail, not a gate (decided).** Because project owners can create orgs, the duplicate-swamp risk (OC-06 **O2**, `ADB_2`) is real. On create, the server fuzzy-matches the registry and the UI shows a **soft flag** — "Possible duplicate: {org} · Use existing / Create anyway" — **never a hard block**. Match signals:
- **Name** — token match on the *distinctive* words, **skipping a generic-word stoplist** (corporation, company, organization, contractor, construction, pvt, ltd, jv, …), so "…Construction JV" and "…Contractor JV" still collide on the distinctive tokens;
- **Email domain** — a match on a *corporate* domain is a strong signal; **free providers (gmail, yahoo, hotmail, outlook, …) are ignored**;
- **Address** — fuzzy string match.

Officers enter complete org names carefully, so token matching lands well; the flag is the guardrail Salesforce lacked. A higher **org_admin** (or `super_admin`) retains merge/re-parent to reconcile after the fact. This **extends SH-4** (which today only "warns on exact duplicate name") to a fuzzy candidate finder.

### 2.5 Admin model — the 4-tier ladder + actor types (as-built; doc 11 §2 updated to match)

**Decided (2026-07).** At ministry scale (Department of Roads ≈ 5,000 staff) and under Nepal's federal structure, admin authority attaches to an **org node** and cascades over its **subtree, at any depth**. Four tiers form a **strict subset ladder** — each does everything the tier below does, plus one more capability — which is what makes *named* tiers legible for low-IT admins (vs. a hidden `can_author_catalog` flag). **doc 11 §2 has been updated to this ladder** (the round-2/3 "conflicts with doc 11" finding is resolved by updating the stale spec, not bending the design).

| Tier | Scope | Adds (on top of the tier below) | Appointed by |
|---|---|---|---|
| **super_admin** | platform | Set up the system; create **institutional roots** (government / local-gov / donor); global catalog; everything | built-in |
| **org_admin** | an org node **+ its whole subtree** + third-parties it created + shared subtrees (**any depth**) | **Author the catalog** (workflows / roles / position types) for its track; build org structure; create contractors; appoint lower admins (attenuated) | super_admin, or a higher org_admin |
| **project_admin** | one **project** (+ track) | Add participant orgs (**contractors**) + staffing / go-live data | org_admin |
| **officer_admin** | an org subtree **or** a project (+ track) | **Invite / modify / revoke officers** — nothing else | org_admin (or project_admin) |

**Catalog authorship = super_admin + org_admin only** (project_admin / officer_admin *consume* it). This keeps one consistent catalog per track (doc 11 §3.3) and **resolves the contradiction** the old "root vs sub org_admin" split created. An `org_admin` scoped at a government/ministry root is the top of that structure's admin tree.

**Actor types (`org_category`) gate root creation.** Every org carries a category, set at its root and inherited: **government** (ministry → dept → offices) · **local_government** (province assembly / municipality — its own root, no national parent) · **donor** (ADB) · **third_party** (contractors, CSCs). Creating a **new institutional root** (government / local_government / donor) is **super_admin only**; **third_party** roots are delegable (org_admin in scope; project_admin for its own project). This is the concrete definition of "root" the round-3 review found missing — a root's **category** is what distinguishes it in the §2.4 forest.

**Scope reach (precise).** An admin's authority covers a target org iff it is (a) in `descendant_org_ids(scope_node)`; **or** (b) an org it **created**; **or** (c) a subtree **shared** with it by a higher admin — **and** it matches the admin's `workflow_track`. Contractors/donors are independent roots (§2.4), reached only by (b)/(c), never (a).

**Attenuated delegation.** An org_admin appoints admins only **at or below** its node, **within its track**, **never exceeding its own capabilities** — so recursive delegation scales without a super_admin bottleneck; the tree provides the levels.

**Three overlays on one tree — do not conflate:** reporting line (supervisor/visibility, doc 16) · admin scope (this section) · project participation (§2.4). SEAH invisibility (doc 16 §6) binds all three.

**Backend impact — SH-7 (hierarchical admin scope)** on OC-01's `descendant_org_ids` CTE: the four role keys, the scope reach (a/b/c) + track, `org_category` + root-creation gating, and attenuation. Supersedes SH-1's flat gate + absorbs SH-1b. Attenuation + SEAH-leak tests are acceptance.

**UI impact.** Every surface row-scoped to the admin's subtree; **Admin access** appoints org / project / officer admins (attenuated), creates institutional roots (super), and shares subtrees. `GET /users/me/admin-context` returns the reach + tier.

---

## 3. Component tree (deliverable 3 — the Part-2 gating artifact)

This is the target shape `page.tsx` (4,723 lines) is demolished **toward** (Handover B RB-2). Legend: **[keep]** reuse as-is (design-token pass only) · **[refactor]** substantial change to an existing file · **[extract]** pull inline code out of `page.tsx` · **[new]** net-new component · **[fold]** absorbs a former OC-05 component.

```
app/settings/
  page.tsx                          [refactor→thin]  nav shell + persona gating + routing only (~150 lines target)

components/settings/
  overview/
    SetupOverview.tsx               [new]      landing: next-blocker line + domain entry cards (D1, D6)
    GoLiveSpine.tsx                 [new]      live checklist; elevates ProjectGoLivePanel logic (D6, F9, F17)

  org/
    OrganisationTab.tsx             [extract]  sub-nav: Org tree · Position types · Officers
    OrgTree.tsx                     [fold+new] tree editor; REPLACES OrganizationsTab flat list; renders TWO groups —
                                               reporting-line subtree(s) + independent org roots (§2.4) (F8, D1; ex-OC-05 OrgTreeTab)
    OrgTreeNode.tsx                 [new]      row: <Bilingual> label, unit_type, territory, inline add-child/edit/set-territory
    OrgEditor.tsx                   [refactor] create/edit unit; adds parent/unit_type/territory/display_name_ne;
                                               hosts the dedup soft-flag (§2.4); fixes F1 (Devanagari), F18 (country/dup), F19 (id)
    OrgCsvImport.tsx                [new]      whole-file-validate → single-txn import (OC-01 endpoint)
    PositionTypesPanel.tsx          [fold+new] secondary panel; matrix editor (D1, D3; ex-OC-05 PositionTypesTab)
    PositionTypeEditor.tsx          [new]      display_name(_ne), allowed_unit_types, default_role_key,
                                               reports_to, visibility_mode, workflow_track
    ReviewHoldersModal.tsx          [new]      opt-in re-sync of N holders (D3); shared w/ transfer-refresh

  officers/
    OfficersDirectory.tsx           [refactor] from OfficersTab; position-title display w/ role-label fallback (§5.1, F5)
    InviteOfficer.tsx               [refactor] orchestrator; rebuild of OfficerModals invite path (D2, F5, F21)
    InviteOutcomeCard.tsx           [new]      the human-readable "This will create …" card (D2 — make-or-break)
    InviteAdjustDisclosure.tsx      [refactor] role/org/scope override behind "Adjust"; from OfficerJurisdictionForm (D2)
    OverrideBadge.tsx               [new]      shows only when Adjust changes a matrix default (D2)
    OfficerManageModal.tsx          [refactor] manage existing positions/scopes; hosts ReviewHoldersModal (D3)
    OfficerScopeTable.tsx           [keep]     staged draft rows are an OC-06 strength; token pass only

  workflows/
    WorkflowsRolesFlow.tsx          [new]      the merged guided flow container (D5, S1)
    WorkflowList.tsx                [extract]  from page.tsx WorkflowsTab
    WorkflowEditor.tsx              [extract]  from page.tsx (~281 lines inline)
    StepEditor.tsx                  [extract]  from page.tsx StepForm (~245 lines inline)
    StepRoleBinder.tsx              [new]      valid-only role picker + "why excluded" (S1, F2-surface, D5)
    RoleCatalog.tsx                 [extract]  from page.tsx RolesTab; human labels (F11)
    RoleEditor.tsx                  [extract]  "acts as" preset (renamed from archetype) + grouped permissions incl. Add/reassign officers (F20)
    StepCast.tsx                    [new]      the 4-slot step cast (Handles it / Oversees / Kept informed / Can view) — §4.3
    NotificationRules.tsx           [new]      per-track event × slot × channel grid (settings.notification_rules) — §4.5

  projects/
    ProjectsTab.tsx                 [extract]  project + packages + actors + staffing + go-live detail
    ProjectEditor.tsx               [extract]  from page.tsx
    ProjectActorSection.tsx         [refactor] actor add/role as an ACTION (kills read-only S2/F8); PRIMARY contractor-create
                                               home — inline create routes through the dedup soft-flag (§2.4)
    ProjectActorAddRow.tsx          [keep]     guided "+ New organization" strength (S3)
    ProjectStaffingSection.tsx      [refactor] coverage warnings kept (strength); empty-state CTA (F23)
    ProjectOfficerModal.tsx         [refactor] delegates to shared InviteOfficer (S4 unified)
    ProjectGoLiveDetail.tsx         [refactor] from ProjectGoLivePanel; feeds GoLiveSpine (D6, F9, F11, F17)
    ProjectTypesTab.tsx             [keep]     Platform; fix F10 empty-state copy

  platform/
    PlatformTab.tsx                 [extract]  sub-nav container (from page.tsx platform block)
    LocationsPanel.tsx              [extract]
    AdminAccessPanel.tsx            [extract]  from page.tsx AdminAccessTab; gains "appoint org_admin at this node" (attenuated)
                                               + "whitelist a subtree"; renders subtree-scoped (§2.5)
    QuarterlyReportSettings.tsx     [keep]

  shared/
    Bilingual.tsx                   [new]      "EN / देवनागरी" with EN fallback; never fabricates (D4, F14)
    RoleLabel.tsx                   [new]      slug → catalog display_name (F11)
    SeverityBadge.tsx               [new]      "Blocking"/"Warning" text + dot (F11)
    ErrorNotice.tsx                 [new]      wraps lib/user-messages.ts formatUserFacingError (F11)
    ProvenanceHint.tsx              [new]      "from position: SDE" / "from office territory" (D2)
    SettingsSubTabs.tsx             [keep]     existing sub-tab chrome

lib/
  design-tokens.ts                  [keep]     the contract; imported by all of the above (kills F24)
  user-messages.ts                  [keep]     finally wired via ErrorNotice (F11)
  api.ts                            [refactor] typed wrappers for OC-01..04 endpoints; apiFetch signature stable (RB-4)
  orgTree.ts                        [new]      client tree build/flatten/descendant helpers (forest-aware, §2.4)
  orgDedup.ts                       [new]      fuzzy candidate finder — name tokens + stoplist, corp-email, address → soft flag (§2.4)
  adminScope.ts                     [new]      client scope-reach test (subtree ∪ owned ∪ whitelisted, + track) for row-gating (§2.5)
  trackFilter.ts                    [new]      SINGLE source for track-filter logic (kills the 4-way dup, F13/F24)
```

**Two structural rules this tree enforces (OC-06 F13/F24):**
1. **Track-filter logic is single-sourced** in `lib/trackFilter.ts`. Today it's re-implemented in four diverging places (`page.tsx:414-418,1978-1982`, `users.py:142-147`, `admin_access.py:341-349`). The UI copies converge here.
2. **No component imports raw color** or copies `ORG_ROLE_COLORS` (which carries banned `purple/indigo/orange/teal`). All color via `design-tokens.ts`; an org-role token map is centralized there (backlog item from F24).

**This is the signal Part 2 can start.** When this tree is approved, RB-2 (demolition) has a target and RB-3/RB-4 have components to build.

---

## 4. Interaction specs for the three hard patterns (deliverable 4)

### 4.1 Invite-as-result (pre-fill + Adjust + override badge)

The flagship. State machine, not a form.

**Inputs (always visible):** Office (tree picker) · Position (filtered by the office's `unit_type` via `allowed_unit_types`, doc 16 §3.2) · Email.

**On (office + position) chosen → resolve the outcome:**
- role ← position type's `default_role_key` (the matrix, doc 16 §4)
- organisation ← the chosen tree node
- scope ← office `territory_location_code` (+ `territory_includes_children`)
- project ← the project(s) the office is linked to (S5 prerequisite, resolved here)

**Render the outcome card** (not fields): `"{Position}, {Office} → acts as {RoleLabel} (from position: {position}) → covers {territory} (from office territory) → on {project}"`. All provenance via `ProvenanceHint`.

**The S5 branch (the seam we're killing):** if the office is **not** linked to the selected project, do **not** dead-end (today's banner, `OfficerJurisdictionForm.tsx:570-574`). Show inline: *"Jhapa Division Office isn't on KL Road yet. [Link it and continue]"* — one click links the org to the project (the guided S3 path already exists on the project side) and the card completes.

**Adjust (collapsed by default):** opens role / organisation / scope as editable fields (`InviteAdjustDisclosure`). Changing any value **away from the matrix default** stamps an `OverrideBadge` on that line ("Overridden — matrix default was Site Safeguards Focal"). Provenance flips from "from position" to "overridden by you." This is the **only** time the override badge shows (doc 16 §4: overrides are visible on the Manage modal as informational badges).

**No silent default (F21):** if no position is picked, the outcome card is absent and "Send invite" is disabled — the admin must make the position choice; nothing is pre-selected.

**Send (irreversible Keycloak email — F21):** a confirm step summarising the outcome card in one sentence before the email fires.

**Multi-scope safety (SH-3 / F6 / O10):** if the invite spans multiple locations, the outcome card lists all scopes and the send is **all-or-nothing** (server transaction, Handover B SH-3). The UI shows one combined result, never N partial rows.

**States:** _loading_ (resolving matrix) → skeleton card · _error_ (position has no `default_role_key`, or org validation fails per SH-3) → `ErrorNotice`, card shows "Role needs to be chosen manually — [Adjust]" · _bilingual_ position/office names via `<Bilingual>`.

### 4.2 Tree editor (create child / territory / CSV import)

**Surface:** `OrgTree` replaces the flat list. Rows are `OrgTreeNode`, indented by depth, each with inline affordances revealed on hover/focus (keyboard-reachable):

```
Ministry of Physical Infrastructure & Transport / भौतिक पूर्वाधार…      [+ child] [edit] [⋯]
  └ Department of Roads / सडक विभाग                                     [+ child] [edit] [⋯]
      └ Jhapa Division Office / झापा डिभिजन कार्यालय   ▸ covers Jhapa   [+ child] [edit] [⋯]
```

- **`[+ child]`** opens `OrgEditor` with `parent_organization_id` pre-set; `unit_type` choices constrained to what can sit under the parent.
- **`[edit]`** edits name (EN + `_ne`), `unit_type`, territory. **Fixes F1:** Devanagari names are creatable — the id is derived server-side (ASCII policy, Handover B SH-6) and the name carried in `display_name_ne`; the client no longer locks the Create button on Devanagari input. **Fixes F19:** the id shown is the id sent.
- **Set territory** attaches `territory_location_code` + `territory_includes_children` — this is what makes the office routable for invite pre-fill (doc 16 §3.1/§5.2).
- **CSV import** (`OrgCsvImport`, OC-01 endpoint): whole-file validate → preview diff → single-transaction insert; errors listed by row through `ErrorNotice`, never a raw dump.

**Position types** live in the sibling panel (`PositionTypesPanel`), not the tree — a set-once catalog (D3). Editing a type's `default_role_key` triggers the D3 review-holders action.

**States:** _empty_ → "No organisation units yet. [Add the top ministry] or [Import from CSV]" (real CTAs, F10 — no migration copy) · _loading_ → tree skeleton · _error_ → `ErrorNotice` · _bilingual_ → every node label.

### 4.3 Step→role binding — the step "cast" (valid-only picker + "why excluded")

A workflow step is **not one role** — it's a small **cast**, one relationship per slot. This is the as-built schema (`ticketing/models/workflow.py:72-83`): `assigned_role_key` (one), `supervisor_role` (one), `informed_roles[]` (many), `observer_roles[]` (many). Presented in plain language so the multi-role reality is obvious (the current UI buried it as a footnote, so admins think one step = one role):

```
Step 1 · Acknowledge (L1)                          from template · Standard GRM
  Handles it     [ Site Safeguards Focal      ▾ ]  owns & works the case   (assigned_role_key · one)
  Oversees       [ Office Manager (Supervisor) ▾ ]  escalate / reassign     (supervisor_role   · one)
  Kept informed  [ Field Officer × ] [ + add ]      view + notes            (informed_roles    · many)
  Can view       [ + add viewer role ]              read-only               (observer_roles    · many)

  picking a role → ✓ Site Safeguards Focal · ✓ PD/PIU Focal
                   ─ Not shown (2) ─  SEAH National Officer · wrong track  |  GRC Chair · bound at L3 only
```

**This answers "how do I put different roles on one level?"** — the safeguards officer *handles it*, their office-manager *oversees* (escalate/reassign), a field officer is *kept informed* (view + notes). The same roles can sit in different slots at other steps.

- **Only `Handles it` is required.** Seed **workflow templates pre-fill the whole cast** (doc 11 §3.5), so the admin clones a template and tweaks rather than binding every slot — the least-decisions path (the answer to "how are roles/workflows best bound"). Inline "+ Create role" is the escape hatch.
- Each slot's picker lists **only roles whose track matches** (single-sourced `lib/trackFilter.ts`); excluded roles are shown **greyed with the reason** ("wrong track"), not hidden — killing the silent F2 failure. Labels, never slugs (F11).
- The four slots mirror the server's full role-usage accounting, so tier-only roles can't be silently orphaned (F15). Server-side SH-2 rejects wrong-track/non-existent bindings on write and publish; a race surfaces via `ErrorNotice`, re-opening the offending slot.

**Two questions, two places (the clarity rule that removes the confusion):** *what can a role do?* → the role's permissions (§4.4); *where does it act, and as what?* → this step cast. Kept separate, the model stays simple. UI labels map to schema: Handles it→`assigned_role_key`, Oversees→`supervisor_role`, Kept informed→`informed_roles`, Can view→`observer_roles`.

**Publish state made visible (S1/F-workflow-silent-on-project):** the workflow header shows Draft / Published; a project won't show a workflow until it's published, so the editor surfaces "Not published — this workflow won't appear on any project yet. [Publish]" instead of letting the admin wonder why it's missing downstream.

**States:** _empty_ (no roles for this track) → "No Standard-track roles yet. [Create a role]" (not "run migrations") · _error_ → `ErrorNotice` · _bilingual_ → role labels where `_ne` present.

---

### 4.4 Role definition — archetype + grouped permissions + usage (added on request)

The role is the pivot of the GRM — a safeguards officer *is* their role — so the catalog surface makes the concept **legible**, not just editable. Grounded in doc 11 §3 and the `ticketing.roles` schema; wireframe = Frame 08.

**What a role carries** (`ticketing.roles`, `role_kind=operational`): `display_name` + `role_key` (slug), `workflow_scope` (**track**: standard/seah/both — controls where it can be bound), `permissions` (JSON capabilities — *what the holder can do*), `jurisdiction_mode` (invite-time area default), `role_origin` (system/TOR seed vs custom).

**The hinge, made visible.** The surface leads with a concept diagram — Position type →(matrix)→ **Role** →(bound to)→ Workflow step, and Officer →holds→ Role →grants→ Permissions — so the admin sees *why* the role matters before editing it. This is the answer to "how do roles work?": the role is the one object all four of position, step, officer, and permission connect through.

**Permissions via a preset, not raw strings — and "archetype" is renamed** (F20, doc 11 §3.4): the jargon "archetype" is replaced by **"this role acts as"**, using the **same vocabulary as the step cast** — Handler / Supervisor / Informed / Viewer / GRC committee / SEAH handler. Picking one pre-fills `permissions`; then a **grouped plain-language picker** fine-tunes — Cases (View / Acknowledge / Add notes / Escalate / **Add · reassign officers** / Resolve) · GRC (Convene / Decide) · SEAH (Access) · Reports (View / export). "Add / reassign officers" (the `reassign` capability) was added on request. **Dangerous admin caps** (`users:invite`, `settings:write`, `projects:manage`) never appear on operational roles.

**Usage guard rails** (doc 11 §3.4 step 4): every catalog row shows "Used on N steps · M officers"; a role held but bound to no step warns (auto-assign would fail); delete is blocked while any step/officer references it (mirrors SH-5).

**Two knobs not conflated** (doc 11 §3.2): the role's `jurisdiction_mode` is only the invite-time default; the *actual* area an officer covers is per-person `officer_scopes`, set in the invite/manage flow — surfaced as an info note on the role, never edited there.

**Who manages** (doc 11 §3.3, reconciled with §2.5): **`super_admin`** authors **global** items; **`org_admin`** (own track) authors items **scoped to its org node**; **`project_admin` / `officer_admin` only *use* the catalog**; system-role permissions are super_admin-only.

**Org-scoped catalog (decided 2026-07-08).** Every catalog item — role, workflow definition, position type — carries an **`owner_organization_id`** and is available **at its owning org level and below** (`owner IS NULL` = global; system/TOR seed = global). A role authored at the DoR node is usable across DoR; one authored at a Jhapa-district node exists only there. This is what makes "org_admin authors at any depth" safe — no global proliferation of N incompatible role keys. **UI:** the role catalog (Frame 08) and every picker (step binder Frame 04, invite Adjust Frame 03) show each item's **owning level** ("System · DoR-wide · Jhapa district") and list only in-scope items (filter: `owner IS NULL OR target ∈ descendant_org_ids(owner) ∪ {owner}`, reusing OC-01's CTE). Backend = Handover B SH-7. Workflows-first (§3.5): the Roles surface is catalog hygiene; steps (§4.3) are where roles are consumed, with inline "+ Create role" as the escape hatch.

**Commits the tree to:** `RoleCatalog` (list + usage) + `RoleEditor` ("acts as" preset + grouped picker) + `StepCast` (§4.3) — in the §3 component tree; this spec fixes their content.

---

### 4.5 Notifications — derived from the cast, tuned per track (added on request)

Notifications are **not a per-step configuration** — the cast already decides them. The slot a role sits in *is* its notification tier: Handles it→`actor`, Oversees→`supervisor`, Kept informed→`informed`, Can view→`observer`. As-built `settings.notification_rules` (seeded by migration `j8l0n2p4r6`) is a matrix `track → event → tier → [channels]`, gated by `should_notify(workflow, event, tier, channel)` — safe-by-default (missing key → no send).

**Surface, mostly don't configure:**
- **In the cast (§4.3):** each slot shows what it means for alerts ("Oversees → alerted on escalation & SLA"), so the admin sees the consequence of a binding without opening any config.
- **One grid per track** (Standard, SEAH), *not per step* — the rare tuning surface. Rows = the 7 events (New case / Escalated / SLA breached / Resolved / GRC convened / Assigned / Quarterly report); columns = the 4 cast slots; cells = channel chips (In-app / Email / SMS). Pre-seeded with the sensible defaults (`_DEFAULT_NOTIFICATION_RULES`); **observers are a silent column** by design; SEAH omits GRC-convened & quarterly-report.

**Channels, phased** (CLAUDE.md notifications): in-app is the proto default for officers; email/SMS layer on; SSE push is v2. **Complainant notifications are a separate track** (chatbot-first + SMS fallback, `_DEFAULT_COMPLAINANT_NOTIFICATIONS`); officer-assignment SMS is per-project Messaging (doc 06 §5), shown read-only for context.

**Open design point:** notifications are **track-level, not per-step** (as-built). Simpler, and I recommend keeping it — a per-step override is possible but adds a knob most admins won't want. Flag if the ministry needs per-step differences.

**Commits the tree to:** `NotificationRules` (per-track grid) — new, in the `workflows/` group.

---

## 5. Wireframes per journey (deliverable 2 — produced)

Deliverable 2 ships as **two rendered HTML decks** in this folder (standalone, open locally):

- **[`settings-wireframes.html`](settings-wireframes.html)** — the **happy-path + key-variant** walkthrough: **thirteen** desktop frames (Setup & go-live [+ first-run], Org tree, Invite-as-result, Workflows & roles [step cast + SLA + clone-template], Projects, Position types, Admin access [+ revoke/bootstrap], Roles & permissions, Notifications, **Create a project**, **Officer directory & lifecycle at scale**, **Org lifecycle & scale**, **SEAH setup & invisibility**) with pins 1–56 keyed to every OC-06 finding / D-fork / §7 remediation.
- **[`settings-state-atlas.html`](settings-state-atlas.html)** — the **systematic state coverage**: for each surface, the **loading / empty / error / bilingual / scoped** states (not just the happy path), a shared state-vocabulary section (skeletons, `ErrorNotice`, severity, `<Bilingual>`, permission-gating), and the new **Admin access** surface (§2.5) — scope row-gating, attenuated appointment, whitelist, and the project_admin read-only case.

Both honour the design-system contract (friendly errors, text severity, no banned hues, no fabricated Nepali) and render theme-aware chrome with product-palette mock UI. Between them they cover:

1. **Setup & go-live overview** — landing, next-blocker line, loading/ready/blocked/error.
2. **Organisation** — org tree (forest), position types, officers directory; loading/empty/error(CSV)/bilingual.
3. **Workflows & roles** — merged flow + valid-only binder; empty/error(publish)/draft/bilingual.
4. **Projects** — actors-as-action, staffing CTA, coverage warning, dedup flag; loading/empty/error.
5. **Admin access (§2.5)** — subtree scope, appoint (attenuated), whitelist, project_admin read-only.

> These were gated on the IA + component tree being locked (brief §9 / Handover B §1) — that lock held through the §2.4/§2.5 additions, so the decks reflect the current model.

---

## 6. Decision log (for the sprint record)

| Fork | Decision | Traces to |
|---|---|---|
| D1 tabs / tree | 4 domain tabs + a Setup landing; tree replaces flat list; position-types & officers fold under Organisation; **zero net new top tabs** | OC-06 §7, F8, F13; brief D1/D3 |
| D2 invite | Outcome card; role/org/scope behind "Adjust"; override badge only on override; provenance on every value; no default role | OC-06 §7, F5, F21; doc 16 §4/§5.2; brief D2 |
| D3 review holders | Opt-in "Review & re-sync N holders", shared with transfer-refresh | OC-06 §5; doc 16 §4; brief D3 |
| D4 Nepali | Bilingual inline where `_ne` present, EN fallback, never fabricate; `<Bilingual>` seam; full i18n = RB-1 | OC-06 §6, F14; brief D4 |
| D5 workflows+roles | Merge into one flow; valid-only picker + "why excluded"; labels not slugs | OC-06 S1, F2, F11, F20; brief D5 |
| D6 go-live | Promote to Setup overview spine; live-refresh; one next-blocker line; text severity | OC-06 F9, F11, F17; brief D6 |
| Org model (§2.4) | Forest of roots; reporting line = `org_admin`, project participation = `project_admin` own scope; contractors & ADB are independent roots; multi-ministry-ready | doc 16 §3.1, doc 11 §2.3; OC-06 F3 |
| Contractor create + dedup (§2.4) | `project_admin` may create; fuzzy-match **soft flag** (distinctive name tokens + corporate email + address), never a hard block | decision; corrects F3, extends SH-4 (was exact-name warn) |
| Admin model (§2.5) | **4-tier ladder: super_admin / org_admin (subtree, any depth — authors catalog) / project_admin (contractors + staffing) / officer_admin (invite only)**; **catalog = super + org_admin only**; attenuated delegation | scale (DoR ≈5000) + federalism; **doc 11 §2 updated to match** (resolves the round-2/3 blocker); new **SH-7** |
| Actor types (§2.5) | Org `org_category` — **government / local_government / donor / third_party**, set at root, inherited; **new institutional root = super_admin only**; third_party (contractors) delegable to org_admin / project_admin | user decision; gives "root" a concrete definition; doc 11 §2 · doc 16 §3 |
| Roles ↔ workflow (§4.3/§4.4) | Step = a **cast** (Handles it / Oversees / Kept informed / Can view = `assigned`/`supervisor`/`informed_roles`/`observer_roles`); templates pre-fill it; "archetype" renamed **"acts as"** (shared role/step vocabulary); + "Add / reassign officers" capability | user request (simplify); as-built `workflow.py:72-83`; doc 11 §3.5 |
| Notifications (§4.5) | **Derived from the cast** (slot = notification tier); one **per-track** grid (event × slot × channel), pre-seeded; observers silent; complainant channel separate | user request; as-built `settings.notification_rules`; doc 12 §9 · notifications.py |
| First-run spine (§7.A) | Setup landing has a **first-run mode** — a zero-data ordered checklist (Add ministry → Workflows & roles → Project → Officers → Go live); per-project go-live is the second mode | review A; OC-06 "next step" thesis |
| Creation flows (§7.B) | Spec'd: project + package create; **workflow authoring incl. per-step SLA**; workflow→project link (published only); clone-a-template as primary path | review B (blockers) |
| Plain language (§7.C) | Hard rule: no code identifiers / math symbols on screen; `unit_type`/project-role/visibility rendered as labels; track/matrix defined; "/ —" → "Nepali name needed" | review C; own F11 |
| Consistency (§7.E) | Atlas covers all surfaces; cast vocab = role "acts as" exactly (Handler / Supervisor / Informed / Viewer); notif grid shows in-app-proto + email/SMS phase-in; `org_admin` naming throughout | review E |
| Lifecycle & scale (§7.F) | Spec'd: officer transfer/edit/deactivate; org delete/re-parent/merge; directory + tree search/pagination; SEAH setup + invisibility; admin revoke/bootstrap/orphan-rehome | review F |

---

## 7. Post-review remediation specs (devil's-advocate A/B/C/E/F)

An independent adversarial review (two agents, cold read) scored the package **Completeness 57% · Ease-of-use 60%** — beating the old 48% on the fixed frictions but with real holes. Full record: [`DESIGN-REVIEW.md`](DESIGN-REVIEW.md). This section specs the fixes. **D (bilingual chrome) is deferred by decision** (stays an RB-1 ticket). Legend: **[wireframed]** already in the decks · **[spec-only]** specified here, render pending.

### 7.A — First-run setup spine (the day-one landing) — *review A*

**Gap:** the go-live spine is *per-project* ("KL Road is 1 step from going live"), so on an empty system — the exact moment a first-timer needs guidance — nothing anchors it. The "every screen names the next step" thesis was only ever shown on an almost-finished project.

**Spec.** The Setup landing (`SetupOverview`) has **two modes**, chosen by whether any project exists:
1. **First-run mode (project-agnostic):** an ordered, zero-data checklist computed from real state, each row = status (Not started / In progress / Done) + one-line what-&-why + a primary CTA linking inward:
   1. **Add your ministry & organisations** → Organisation (done when ≥1 org root exists)
   2. **Set how grievances are handled** — workflows & roles → Workflows & roles (done when ≥1 workflow is *published*)
   3. **Create your project & packages** → Projects (done when ≥1 project exists)
   4. **Invite your officers** → Projects ▸ Staffing / Officers (done when required actors staffed)
   5. **Go live** → per-project go-live (enabled when a project has no blockers)
   Steps unlock in order but don't hard-gate (jumping ahead is allowed; the CTA just guides).
2. **Per-project go-live mode** (existing §1/D6): once ≥1 project exists, the landing shows the single "next blocker" spine per project; the first-run checklist collapses to a "Setup complete" strip or the remaining first-run items.

**Every task surface ends with "Next: <step>"** back to the spine — fixes the "I finished this, now what?" gap surviving on org tree / workflow / project screens (ease #12).

**Components:** `SetupOverview` (+ first-run mode), `SetupChecklist` [new]. **[wireframed]** — Frame 01 first-run variant + atlas Setup first-run state.

### 7.B — Creation & authoring flows — *review B (blockers)*

**Gap:** the invite, cast, and go-live are specified, but the paths to *create* the things they check were `[extract]` pass-throughs: no project/package creation, no workflow authoring, no per-step **SLA**, no workflow→project link.

**B1 · Project & package creation** ([wireframed] — Frame 10). "New project" → name (+ `_ne`), country (validated), project type, **packages** (add rows: name + location scope), then **link workflows** (B3). Created `is_active=false`; appears in the first-run checklist and go-live until activated. Component `ProjectEditor` [extract→spec'd].

**B2 · Workflow authoring incl. per-step SLA** ([wireframed] — SLA added to Frame 04). Each step carries, beside its cast (§4.3): an **SLA** (duration before auto-escalation) and its **escalation target** shown read-only — *"escalates to the next step's Handler pool"* (the locked truth: the reporting line never redirects escalation, doc 16). New workflow's **primary path is "Start from a template"** (B4); "blank" is the advanced escape. `StepEditor` = cast + SLA + escalation-target display.

**B3 · Workflow→project linking** ([wireframed] — Frame 10). Pick `standard_workflow_id` / `seah_workflow_id` from **published** workflows only; drafts are shown greyed with "Publish it first" (reuses the F04 valid-only/why-excluded pattern). Closes the seam the go-live spine's "Workflow published" check implied but never surfaced.

**B4 · Clone-a-template** ([wireframed] — Frame 04 variant). "New workflow → Start from a template" (Standard GRM 4-level / SEAH) clones steps + cast + SLAs, opens for tweak — the least-decisions path doc 11 §3.5 mandates. Removes the Frame-04-empty-state trap (was: "create a role before a step can bind").

### 7.C — Plain-language / no-jargon pass (hard rule) — *review C (own F11 violated)*

**Gap:** slugs I claimed to kill reappeared as `unit_type` chips (`division_office`, `development_partner`, `company`), `descendant_org_ids` and a literal **"∪"** printed on screen, and "track" / "the matrix" / "attenuated" undefined.

**Spec (a build rule, not a screen):**
- **No code identifier or math symbol ever renders.** A single display map `lib/labels.ts` resolves `unit_type` → label ("Division Office"), project-role → label ("Main contractor"), `visibility_mode` → plain ("sees direct reports"), each with `_ne`. Applies to Frames 02 / 05 / 06 / 07 and the org authznote.
- **The scope line becomes prose**, not set-notation: *"You manage the Department of Roads and every office beneath it, plus organisations you added or that were shared with you."* Delete `∪` and `descendant_org_ids`; "attenuated" is a spec word, never UI.
- **Define the three floating terms:** *track* → surfaced as "Standard grievances / SEAH" with a one-time tooltip; *the matrix* → "default role for this position"; *acts as* → kept, glossed inline.
- **"/ —"** (missing Nepali) → a labelled chip **"Nepali name needed"** (not "mark for translator" — jargon to the civil servant).

**[wireframed]** — applied across Frames 02/05/06/07.

### 7.E — Consistency fixes (self-inflicted) — *review E*

- **Atlas coverage** ([wireframed]): add Position types, Roles catalog, Notifications state sets (loading / empty / error) — atlas Surfaces 07 / 08 / 09, so "every surface, all states" is finally true.
- **One vocabulary, exact** ([wireframed]): unify on the **cast's plain verb-phrases** — the role's "job in a step" field uses the *same words as the cast*: **Handles it / Oversees / Kept informed / Can view** (removing the Handler≠"Handles it" mismatch; verb-phrases are friendlier for low-IT than the nouns). "GRC panel" / "SEAH handler" are **"Handles it" specialisations** for those contexts (stated), not extra slots.
- **Notification defaults vs proto** ([wireframed]): Frame 09 shows **In-app as the enabled proto channel; Email / SMS marked "phase-in"** (muted), with a banner — reconciling the seeded matrix with CLAUDE.md's locked "in-app only (proto)". The target matrix stays visible; the phasing is honest.
- **Admin naming** ([wireframed]): the admin tier renders as **"Organisation admin"** (`org_admin`) everywhere, incl. Frame 01 topbar; a note flags the JWT/role-key transition is SH-7.

### 7.F — Lifecycle & scale — *review F*

**F1 · Officer lifecycle** ([wireframed] — Frame 11; `OfficerManageModal`). **Edit** (role/scope, staged rows — the existing OfficerScopeTable strength), **transfer** (new office/position → offer role/scope re-sync via the shared review-holders flow, doc 16 §3.3; old rows end, no silent re-scope), **deactivate** (ends `user_roles` + scopes, keeps history/audit). **In-flight cases (round-2 fix):** deactivate — and transfer, for cases that don't move — **require reassigning the officer's open cases first**; no ticket is left owner-less.

**F2 · Org lifecycle** ([wireframed] — Frame 12; the node "⋯" menu). Menu = **edit · add child · set territory · move (re-parent)** (pick new parent, cycle-guarded) **· merge · deactivate/delete** with the **SH-4 guard surfaced**: "Can't delete — on 2 projects, holds 3 officers, 4 open cases. Reassign the cases and move the officers first." (409 → friendly, never a raw error). **Merge semantics (round-2 fix):** folding org B into A re-homes B's officers, `project_organizations` links, and child subtree to A, **moves B's open cases with it**, and **flags conflicting territory/country** for the admin to resolve — not a silent overwrite.

**F3 · Scale (≈5,000 staff)** ([wireframed] — Frames 11 & 12). Officer **directory**: server-side search + filters (org, role, project, track) + pagination. Org **tree**: search-to-node, collapse/expand, **lazy-load subtrees** (don't render thousands of nodes); the tree endpoint already supports `root_id`/`tree=true` (OC-01). Both were implied by the "5,000 staff" premise and must be real.

**F4 · SEAH surfaces** ([wireframed] — Frame 13) — the compliance half that was near-absent. **SEAH workflow** setup (SEAH track, its own cast), **SEAH-track invite** (gated to an **`org_admin` (seah)** / super), **SEAH staffing**; and **invisibility scoped precisely** — only SEAH *case existence* is hidden. The chart is **shared for directory purposes** (doc 16 §6), so SEAH officers appear as people; but SEAH **tickets, SEAH roles, and any signal of a SEAH case** never render in standard reporting-line, Watching, or notification surfaces. Track-scoped at the query layer; SEAH-leak tests are the acceptance gate (OC-04). *(Round-2 correction: the earlier "no SEAH officers appear at all" over-stated doc 16 §6.)*

**F5 · Admin lifecycle** ([wireframed] — Frame 07 variant). **Bootstrap:** `super_admin` appoints the first `org_admin` at a ministry root (the empty-admin base case). **Revoke:** appointments and whitelists are removable (with a confirm). **Orphan-on-removal:** when an `org_admin` is removed, orgs it created **re-home to the nearest enclosing admin scope** — never orphaned ownership.

---

*Milestone + first remediation pass. §1–§4 unblock Handover B Part 2; §5 wireframes produced; §7 closes review findings A/B/C/E/F (D deferred). Full review: [`DESIGN-REVIEW.md`](DESIGN-REVIEW.md).*
