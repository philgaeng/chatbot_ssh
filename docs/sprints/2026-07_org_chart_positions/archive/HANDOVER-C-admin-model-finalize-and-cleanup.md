# Handover C — Admin model finalize, spec cleanup & org-scoped catalog

> **⚠ ARCHIVED (design phase) — superseded by [../BUILD-HANDOVER.md](../BUILD-HANDOVER.md)** (the build entry point). Kept for history; the plan is carried forward there.

> **For:** the agent picking this up next. **Prereq reading:** this file, then [`DESIGN-settings-redesign.md`](../DESIGN-settings-redesign.md) §2.4/§2.5, [`DESIGN-REVIEW.md`](../DESIGN-REVIEW.md), and [`docs/ticketing_system/11_roles_and_permissions.md`](../../../ticketing_system/11_roles_and_permissions.md) §1–§2.
> **State on handoff:** the Settings redesign design is **done at ~80% completeness / 73% ease-of-use** (up from a 48% baseline, over four independent devil's-advocate re-scores — history in DESIGN-REVIEW). The admin model is **finalized and locked** (below). What remains is (1) propagating the model through the rest of doc 11, (2) implementing the org-scoped-catalog decision, (3) a couple of residual copy fixes, and (4) five build-time items → RB/Handover-B tickets. **No design decisions are open** — this is execution.
> **Do NOT touch `main`.** Branch off `integration/seah-claude` per the sprint README. Ticketing stream only; migrations get a safety header + real `downgrade()`.

---

## 0. Locked decisions (ground truth — do not re-litigate)

### 0.1 Admin ladder — 4-tier strict-subset (doc 11 §2, as-built)
Each tier does everything the tier below does, plus one more. `country_admin` is **retired → `org_admin`**.

| Tier | Scope | Adds on top of the tier below | Appointed by |
|---|---|---|---|
| **super_admin** | platform | Set up the system; create **institutional roots** (government / local-gov / donor); global catalog; everything | built-in |
| **org_admin** | an org node **+ its whole subtree, any depth** + third-parties it created + shared subtrees | **Authors the catalog** (roles / workflows / position types) — see §0.3; builds org structure; creates contractors; appoints lower admins (attenuated) | super_admin, or a higher org_admin |
| **project_admin** | one project (+ track) | Add participant orgs (contractors) + staffing / go-live data; **no catalog** | org_admin |
| **officer_admin** | an org subtree **or** a project (+ track) | **Invite / modify / revoke officers** — nothing else | org_admin (or project_admin) |

Track (`standard` / `seah`) is on the **scope**, not the role key. Attenuated delegation: appoint only at/below your node, same track, never exceeding your own capabilities.

### 0.2 Actor types — `org_category` (gives "root" a concrete definition)
Every org carries a category, **set at the root and inherited** by children: `government` · `local_government` (province assembly / municipality — its own root) · `donor` (ADB) · `third_party` (contractor, CSC).
- Creating a **new institutional root** (`government` / `local_government` / `donor`) = **super_admin only**.
- **`third_party`** roots are delegable — `org_admin` in scope, `project_admin` for its own project.

### 0.3 Org-scoped catalog (NEW — decided 2026-07-08; implement per §2)
A catalog item (operational **role**, **workflow definition**, **position type**) is **owned by an org node** and available to **that node and its subtree (descendants) only** — "the level it's created at, and below." System/TOR-seed items are **global** (owner = null → available everywhere). This is what makes "org_admin authors the catalog at any depth" safe (no global proliferation, doc 11 §3.3).

---

## 1. Cleanup tasks (self-inflicted; do FIRST — mechanical, low-risk)

The §2 rewrite of doc 11 didn't propagate; other files drifted. Finish it.

### 1.1 doc 11 — propagate the 4-tier ladder through §4–§11
`docs/ticketing_system/11_roles_and_permissions.md`. The round-4 review found these still on the **stale 3-key / `country_code`** model:
- **§ status line (top):** "Locked product spec (June 2026)" → note the 2026-07 admin-ladder revision.
- **§4 access matrix / §5 data-model & scope table:** the scope table still scopes the org tier by **`country_code`** and says "must match appointing **country admin**" — change to the **org-subtree** scope shape (see §2 already-rewritten scope-shape table as the pattern: `organization_id` covers subtree) and "appointing **org_admin**". Add an **`officer_admin`** column/row wherever tiers are enumerated.
- **§6 key list:** says "**3 keys**" → **4 keys** (add `officer_admin`).
- **§8 status:** the ✅s reflect the old `country_admin` build — mark the org_admin/officer_admin/org-scope work as **unbuilt (SH-7)**, not done.
- **§11 acceptance:** item #1 says "super_admin, **org_admin, project_admin only**" → 4 keys incl. `officer_admin`.
- **Space-phrasing sweep:** my earlier sweep replaced `country_admin` (underscore) but not "**country admin**" (space) — fix §7/§8/§9 ("SEAH-track country admin edit", etc.) → "org_admin" / "standard-track admin".
- **Verify:** `grep -n "country_admin\|country admin\|3 keys\|country_code" 11_*.md` returns only intended residue (none in forward text).

### 1.2 doc 16 — give `org_category` a data home
`docs/ticketing_system/16_org_chart_and_positions.md` §3 (the org-schema owner).
- Add **`org_category`** column to the `ticketing.organizations` extension table (§3.1): enum `government | local_government | donor | third_party`, **NOT NULL on roots**, **inherited from root** (children take their root's category; enforce/backfill in the migration).
- **Reconcile with `unit_type`** (§3.1 already lists `company` / `development_partner`): add a mapping note — `development_partner` ⇒ `donor`; `company` ⇒ `third_party`; ministry/department/directorate/provincial_office/division_office ⇒ `government`; add local-gov unit types (e.g. `province_assembly`, `municipality`) ⇒ `local_government`. Decide whether `org_category` is derived-from-`unit_type` or an independent column set at root — **recommend independent column** (a `company` could be a `third_party` contractor OR, rarely, a donor-adjacent body; explicit is safer), with `unit_type` as the fine-grained sub-type.
- Add the **creation-gating rule** (§0.2) to doc 16 §7 (ownership table) — institutional-root create = super only.

### 1.3 Residual slug/symbol fixes (product-facing)
- `settings-state-atlas.html` — CSV import error tile: "…try **division_office**" → "…try **Division office**" (it's inside `errnotice`/`tile__body`, a product surface).
- `settings-state-atlas.html` s6 — the "Share an organisation" tile caption "Granted by any **org_admin** at/above" → "any **admin** at/above".
- `settings-wireframes.html` Frame 07 **pin 26** still prints the literal **`∪`** and "whitelisted" — it's spec-rail (engineer-facing, allowed by policy) but the design's own §7.C says "no math symbol ever renders"; prefer to reword to prose for consistency.

---

## 2. Implement the org-scoped catalog (§0.3)

The design decision is locked; this is its spec. Touch the design docs + the backend ticket (SH-7 sibling); actual code lands in the RB/backend build.

### 2.1 Schema
Add an **owning-org** column to each catalog table:
- `ticketing.roles` → `owner_organization_id` (String(64), **nullable**; NULL = global/system, `super_admin`-owned).
- `ticketing.workflow_definitions` → same.
- `ticketing.position_types` (when built, OC-02) → same.
System/TOR seed items get `owner_organization_id = NULL` (global). Custom items created by an `org_admin` get `owner_organization_id = that admin's scope node`.

### 2.2 Availability rule
A catalog item is usable in a context for target org **T** iff `owner_organization_id IS NULL` **OR** `owner_organization_id` is an **ancestor-or-self of T** (i.e. T ∈ `descendant_org_ids(owner)` ∪ {owner}). Reuses OC-01's `descendant_org_ids` CTE. Apply at: step→role binding (Frame 04), invite role picker (Frame 03 Adjust), position-type list, role catalog list (Frame 08).

### 2.3 Authoring
`super_admin` authors global items; `org_admin` authors items scoped to **its node** (available node + below). `project_admin` / `officer_admin` consume only. On create, the owner is auto-set to the author's scope node (super → global, with an explicit "make global" option).

### 2.4 Doc + UI updates
- **doc 11 §3.3 / §3.6:** state the org-scope rule + `owner_organization_id`; catalog authoring = super (global) + org_admin (own subtree).
- **DESIGN §2.5 + §4.4:** add the org-scoped-catalog paragraph (role/workflow/position-type owned by an org, available level-and-below); update the "catalog = super + org_admin only" line to "authored by super (global) or org_admin (their subtree)."
- **Frame 08 (Roles) + Frame 04 (step binder):** show each catalog item's **owning level** ("System / DoR-wide / Jhapa district") and filter pickers to in-scope items. (Wireframe update — small.)
- **Handover B SH-7:** add the `owner_organization_id` columns + availability filter to the ticket's Fix/Acceptance.

---

## 3. Build-time items → RB / Handover-B tickets (not design)

Carry these into the build; each has a one-line spec + home. (Full context in DESIGN-REVIEW round-2..4.)

| # | Item | One-line spec | Home |
|---|---|---|---|
| 1 | **Admin audit-log UI** | `log_admin_audit()` already fires (users.py); add a GET endpoint + a read surface ("who appointed/revoked/authored what, when") — governance-critical on a PII system | RB (new surface) |
| 2 | **Dual-hat invite collision** | Invite (Frame 03) when the email is already an officer → "add a position to the existing officer" vs Keycloak 409; design the branch | RB-4 + OC-03 |
| 3 | **Workflow level-delete in-flight guard** | "⋯ remove a level" (Frame 04 pin 53) must guard tickets parked at that level (reassign/block), like org-delete/officer-deactivate | RB-3 |
| 4 | **CSV import schema** | Define columns/headers/format for `POST /organizations/import` (parent-by-key, `unit_type`, territory, `org_category`, `_ne`, encoding) | OC-01 |
| 5 | **Project country-validation** | Validate `country_code` against the authoritative source (countries table) + org↔project country consistency | SH-4 / B1 |

---

## 4. Where everything lives

- **Design source of record:** [`DESIGN-settings-redesign.md`](../DESIGN-settings-redesign.md) (IA §2, admin model §2.5, actor types §2.4, interaction specs §4, remediation §7, component tree §3).
- **Wireframes:** [`settings-wireframes.html`](../settings-wireframes.html) — 13 frames, pins 1–56 (open locally; standalone HTML). **State atlas:** [`settings-state-atlas.html`](../settings-state-atlas.html) — 14 surfaces.
- **Review history + scores:** [`DESIGN-REVIEW.md`](../DESIGN-REVIEW.md) (rounds 1–4; the exact findings this handover closes).
- **Specs to update:** doc 11 (§1), doc 16 (§1.2 / §2).
- **Backend plan:** [`HANDOVER-B-...md`](HANDOVER-B-settings-hardening-and-rebuild-plan.md) — **SH-7** owns the admin-scope + org_category + org-scoped-catalog backend; RB-1..4 the frontend rebuild.
- **Session memory (context for a fresh agent):** `~/.claude/projects/-home-philg-projects-nepal-chatbot/memory/` — `admin-model-4-tier-ladder.md`, `user-drives-design-decisions.md`.

---

## 5. Definition of done (this handover)

- [x] doc 11 §4–§11 propagated to the 4-tier ladder + `officer_admin`; no "3 keys" / `country_code`-scoped-org-tier / "country admin" residue (§1.1). *(2026-07-08; grep-verified clean.)*
- [x] `org_category` in doc 16 §3 schema + `unit_type` reconciliation + creation gating in §7 (§1.2).
- [x] Residual product-facing slugs/symbols fixed — atlas CSV "Division office", s6 "any admin", Frame 07 pin 26 prose (§1.3).
- [x] Org-scoped catalog: `owner_organization_id` in doc 11 §5 + rule in §3.3/§3.6 + DESIGN §4.4 + Frame 08 (owning-level chips) + Handover B SH-7 filter (§2).
- [x] Build items filed in Handover B (Part 2 "Open build items" table) (§3).
- [x] [`PROGRESS.md`](../PROGRESS.md) updated.
- [ ] **Re-verify (remaining checkpoint):** re-run the two independent devil's-advocate reviewers on the updated package — the round-4 [MAJOR] doc-11-self-contradiction and `org_category`-no-data-home findings should be gone.

> **Executed 2026-07-08** (§1–§3 done; grep-clean; decks structurally sound). The one open item is the confirmation re-score.
