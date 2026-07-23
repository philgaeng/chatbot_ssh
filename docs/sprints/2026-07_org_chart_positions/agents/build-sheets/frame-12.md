# Build sheet — Frame 12 · Organisation — org lifecycle (⋯) & tree at scale

> RB-0 build sheet. Grounds wireframe Frame 12 in the NOW-REAL org API. Input to RB-2/3/4.
> **Data owner:** OC-01 (tree, `root_id`/`tree=true` lazy-load) + SH-4 (delete/merge guards).
> **Real router:** `ticketing/api/routers/locations.py`, prefix `/api/v1` (`ticketing/api/main.py:117`). Shares `OrgTree`/`OrgEditor` with Frame 02.

---

## 1. Visual ref

- **Wireframe:** `settings-wireframes.html` Frame 12 (line 1446, `#f12`).
- **Atlas:** `settings-state-atlas.html` Surface 12 "Organisation — lifecycle & scale" (line 777) — Loading-a-subtree / Delete-blocked(SH-4) / Move-blocked(cycle). Atlas 00 applies.
- **Layout (3–5 lines):** The same org tree as Frame 02, but **at ministry scale**: a "Find an office by name…" search, a "1,240 offices · showing top level only" count, and nodes that show a child-count chip and **"48 offices · click to load"** (lazy-load subtrees). The focused node's **`⋯` menu** is defined here: Edit name & type · Add child office · Set territory · Move to a new parent (cycle-guarded) · Merge a duplicate in · Deactivate / Delete. Delete surfaces the SH-4 guard as a plain-language stop ("Can't delete Jhapa Division Office. It's on 2 projects, holds 3 officers, and has 4 open cases. Reassign the cases and move the officers first."). Merge folds a duplicate in (re-homes officers / project-links / children, moves open cases, flags territory/country conflicts).

---

## 2. Component subtree (DESIGN §3, `components/settings/org/`)

```
OrganisationTab.tsx            [extract]  (shared)
  └ OrgTree.tsx                [fold+new] gains: search-to-node, collapse/expand, LAZY-LOAD subtrees (root_id/tree)
      ├ OrgTreeNode.tsx        [new]      row + the "⋯" menu (edit · add child · set territory · move · merge · deactivate/delete)
      │                                   + child-count chip + "click to load"
      └ OrgEditor.tsx          [refactor] reused for edit / move (reparent picker, cycle-guarded)
lib/orgTree.ts                 [new]      forest-aware build/flatten/descendant helpers; drives lazy expand
shared/ErrorNotice.tsx         [new]      the friendly 409 (delete guard) + 422 (cycle) surface
```

**Demolition source:** same as Frame 02 — the flat `OrganizationsTab` (`components/settings/OrganizationsTab.tsx:35`) and inline `OrgEditor` (`app/settings/page.tsx:2190`). Frame 12 adds the `⋯` menu, lazy-load, and search that the 4-node happy path (Frame 02) doesn't exercise.

---

## 3. Governing interaction rules (DESIGN §4.2, §7.F2/F3)

- **Reparent cycle-guard (Move).** "Move to a new parent" → `PATCH /organizations/{id}` with `parent_organization_id`. Server rejects a cycle: 422 "Reparenting would create a cycle (a node cannot report to its own descendant)" (`locations.py:648-652`; `would_create_cycle` in `org_tree.py:106`). Atlas Surface 12 renders it as "Can't move an office under one of its own sub-offices. Pick a parent outside this branch." The reparent picker must **exclude the node's own subtree** client-side (via `lib/orgTree.ts` descendants) so the user rarely hits the 422; still surface the server 422 via `ErrorNotice` on a race.
- **Destination-parent scope.** A non-super org_admin can only move within its own subtree; server 403 "Your org_admin scope does not cover the destination parent" (`locations.py:653-660`). Gate the picker options by admin-context; server is truth.
- **Subtree category cascade on move.** Moving a node adopts the new parent's `org_category` and cascades it to the moved node's whole subtree (`locations.py:685-693`). The client must refetch the moved subtree.
- **Child-delete 409 guard (SH-4).** `DELETE /organizations/{id}` is blocked (409) — each guard returns a plain string in `detail`:
  - `child_count` — "N child organization(s) report to this org. Reassign or delete them first." (`locations.py:726-736`) — **the parent-delete orphan guard** (self-FK is SET NULL, which would silently orphan the subtree).
  - `ticket_count` (`:738`), `role_count` (UserRole, `:747`), `scope_count` (OfficerScope, `:756`), `assign_count` (WorkflowAssignment, `:767`), `pkg_count` (PackageOrganization, `:778`), `proj_count` (ProjectOrganization, `:791`).
  The wireframe's combined "on 2 projects, holds 3 officers, 4 open cases" is a **friendlier aggregate** than the server's one-guard-at-a-time messages — see §7 risk.
- **Deactivate ≠ Delete.** "Deactivate" maps to `PATCH /organizations/{id}` `{is_active:false}` (no dedicated endpoint). The delete guards do **not** run on deactivate — confirm whether deactivate should also require reassigning open cases (§7 risk).
- **Lazy-load at scale (F3).** Render top level first; expand a node by calling `GET /organizations?root_id={id}&tree=true` (subtree via `descendant_org_ids` CTE, `locations.py:354-358`). Never render thousands of nodes at once. `tree=true` returns depth-first order (`_order_for_tree`, `locations.py:307`).

---

## 4. Concrete endpoints (all `/api/v1`, real)

| Method + path | Payload | Response / notes |
|---|---|---|
| `GET /organizations?root_id={id}&tree=true` | query: `root_id`, `tree`, `country?`, `active_only=true` | `OrganizationResponse[]`, subtree depth-first. **Powers lazy-load.** Auth. `locations.py:335`. |
| `PATCH /organizations/{id}` | `OrganizationUpdate` — `parent_organization_id` (move), `is_active:false` (deactivate), name/unit_type/territory (edit) | `OrganizationResponse`. Cycle 422; scope 403; category cascade. `locations.py:582`. |
| `DELETE /organizations/{id}` | — | 204, or **409** with a plain-text guard message (child / ticket / role / scope / assignment / package / project). Gated + scope. `locations.py:701`. |
| `POST /organizations` | `OrganizationCreate` (`parent_organization_id` preset) | 201 — "Add child office". `locations.py:366`. |
| `POST /organizations/duplicate-candidates` | `{name, …, exclude_organization_id}` | soft-flag list — feeds "Merge a duplicate in" discovery. `locations.py:501`. |

### `[GAP]` — endpoints this frame needs that do NOT exist
- **`[GAP]` Merge.** "Merge a duplicate in" (re-home the folded org's officers, `project_organizations`/`package_organizations` links, child subtree; **move its open cases**; flag conflicting territory/country) has **no endpoint**. This is a multi-table transactional operation with conflict reporting — not composable from the current PATCH/DELETE. Owner: SH-4. **Hard gap** — RB cannot build the merge action against real API.
- **`[GAP]` Server-side tree search (`q`).** "Find an office by name…" over 1,240 offices needs a search-to-node endpoint. `GET /organizations` has **no `q` param** (`locations.py:335-363`; only `country`/`active_only`/`root_id`/`tree`). Client-side filtering defeats lazy-load at scale. Owner: OC-01. Gap.
- **`[GAP]` Per-node child/descendant count.** Nodes show "523 offices" / "48 offices · click to load" without loading the subtree. No count endpoint exists; `GET ?root_id=` returns the rows (which requires loading them). Needs a lightweight per-node count. Owner: OC-01. Gap.
- **`[GAP]` Aggregated delete-guard preview.** The wireframe's single friendly line ("on 2 projects, holds 3 officers, 4 open cases") needs **all** guard counts at once; the real `DELETE` returns the **first** blocking guard only (raises on the first non-zero). Either add a `GET /organizations/{id}/delete-impact` preview, or the client attempts delete and shows one guard at a time (degraded UX). Owner: SH-4. Gap.
- **`[GAP]` Reassign-open-cases-before-delete flow.** The guard blocks; there is no endpoint here to *reassign* the org's open cases (that lives in the tickets domain). The "Reassign the cases … first" CTA must deep-link out to ticket reassignment — confirm the target.
- **`[GAP]` `lib/api.ts` wrappers** — `listOrganizations` (api.ts:1736) passes neither `root_id` nor `tree`; add lazy-load-aware wrappers (shared with Frame 02).

---

## 5. Tokens / labels contract (DESIGN §7.C, §7.E)

- **Labels, never slugs.** `⋯` menu items and chips are plain English ("Division office", "covers Jhapa"); resolve `unit_type`/`org_category` via `lib/labels.ts`. No code identifiers or math symbols (no `descendant_org_ids`, no `∪`).
- **Friendly 409 / 422** via `formatUserFacingError` (`lib/user-messages.ts:145`) + one `ErrorNotice`. The delete guard and the cycle guard are the canonical "raw server error → human sentence" cases in the whole redesign — never surface `API 409 {…json…}`. Note the client should map the plural distinct server guard strings into the aggregate wording where possible (see §7).
- **`<Bilingual>`** on node labels (shared with Frame 02); absent `_ne` → "Nepali name needed".
- **Colors via `design-tokens.ts`**; destructive "Deactivate · Delete" uses the red family token (wireframe `--p-red700`); no banned hues, no emoji; Lucide via `@/lib/icons`; `text-gray-600` floor.

---

## 6. Data owner

| Path | Ticket |
|---|---|
| Tree read, `root_id`/`tree=true` lazy-load, reparent, cycle guard | **OC-01** |
| Delete guards (child/ticket/role/scope/assignment/package/project), merge, dedup, delete-impact preview | **SH-4** |
| Admin subtree scope on move/delete (403s) | **SH-7** |

---

## 7. Open gaps / risks for RB-2/3/4

1. **Merge is entirely unbuilt server-side** (`[GAP]`). It is the most complex lifecycle op (re-home links + children + move open cases + conflict flags) and has no endpoint. RB cannot deliver the `⋯ → Merge` action until SH-4 ships it. Flag to the ticket owner; may need to ship Frame 12 with Merge disabled/"coming soon".
2. **Delete guard is one-at-a-time vs the wireframe's aggregate.** The real `DELETE` raises on the first non-zero guard, so a naive client shows "N child organization(s)…" then, after the user fixes that, "M tickets…", etc. To match the wireframe's single combined sentence, add a **delete-impact preview** endpoint (SH-4). Decide before RB-3 whether to build the preview or accept iterative guards.
3. **Search + per-node counts are scale-critical and missing.** The "1,240 offices, top level only, click to load, find by name" experience needs `q` search and child counts server-side; without them the frame degrades to load-everything (contradicting the F3 premise). Owner OC-01.
4. **Deactivate open-case policy undecided.** `PATCH is_active:false` bypasses the delete guards; §7.F says deactivate should also require reassigning open cases. Confirm whether the backend enforces this on deactivate or the UI must warn.
5. **Reassign-cases deep-link target unknown.** The delete-guard CTA "Reassign the cases … first" must route to the ticket-reassignment surface; confirm the route (outside the settings/org domain).
6. **Next.js 16 caveat** (`channels/ticketing-ui/AGENTS.md`) — read `node_modules/next/dist/docs/` before writing components; lazy-load/tree state interacts with the framework's data conventions.
</content>
