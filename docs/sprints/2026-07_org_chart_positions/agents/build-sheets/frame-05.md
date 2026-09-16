# Build sheet — Frame 05 · Projects — staffing & go-live

> RB-0 build sheet. **This frame is REBUILT per [DECISION-project-participants-and-supervision.md](../../DECISION-project-participants-and-supervision.md) (2026-07-10).** The old per-project **actor-role catalog / "+ Add role" column is REMOVED.**
> Sources: DESIGN §2.4, §4.1 (invite delegate), §3.1 row 05; DECISION §2/§3/§5/§7; wireframes Frame 05 (lines 900-986, incl. the revised-2026-07-10 banner); atlas Surface 05 (lines 537-584, incl. revised banner). Data owner: **doc 13**, OC-03 (staffing invite), SH-4 (contractor dedup).

## 1. Visual ref
- **Wireframe Frame 05** + **Atlas Surface 05** (both carry the amber "⚠ Revised 2026-07-10 — RB-0 rebuilds" banner).
- Content area under `Settings ▸ Projects ▸ KL Road`. Top-down: **Project actors** table (org + project role) → **Staffing per package** (officer / level / scope) with per-package coverage warnings and an empty-state CTA → an **Add contractor** panel with a **fuzzy-dedup soft flag** → a red **"1 item stops KL Road going live"** strip linking to the Setup spine.
- **REMOVE from the old frame:** the `Project role / + Add role` column, `ProjectActorRolesEditor`, the actor-role catalog. **KEEP:** the Implementing-agency row (now a single defaulted field, not a role), coverage warnings, staffing CTA, dedup flag.
- **ADD (DECISION):** a defaulted **Implementing agency** field; an optional **Donor** include (0..n) that auto-fills the last standard step's "Kept informed" cast; a per-level **Supervisor** (reassignment authority, default = next level's Handler pool, shown-not-blank); **new blocking states** — donor-present-but-not-informed, and unstaffed-level.
- **States (atlas Surface 05):** Loading (staffing streams per row) · Empty staffing (real CTA "Invite officer for L2 →") · Coverage warning ("No officer scoped for {org} on this package") · Error — save failed (SH-3 jurisdiction: "That organisation isn't on this project…").

## 2. Component subtree (DESIGN §3, projects/)
```
projects/
  ProjectsTab.tsx              [extract]  project + packages + staffing + go-live detail (from page.tsx ProjectsSection ~2667 / ProjectEditor ~3002)
    (Implementing agency field) [new]     single defaulted org pointer (government/local_government only)
    (Donor include control)     [new]     0..n donor add/remove; guardrail state
    ProjectStaffingSection.tsx  [refactor] coverage warnings kept; empty-state CTA (F23); + per-level Supervisor row
    ProjectOfficerModal.tsx     [refactor] delegates to shared InviteOfficer (Frame 03) — S4 unified
    ProjectActorSection.tsx     [refactor] PRIMARY contractor-create home; inline create → dedup soft-flag (§2.4). NOTE: actor-ROLE column removed
    ProjectActorAddRow.tsx      [keep]     guided "+ New organisation" (S3)
    ProjectGoLiveDetail.tsx     [refactor] from ProjectGoLivePanel; feeds GoLiveSpine (Frame 01)
  ── REMOVED ── ProjectActorRolesEditor (page.tsx ~3682) — deleted per DECISION §1
  shared/ErrorNotice.tsx  SeverityBadge.tsx  RoleLabel.tsx  Bilingual.tsx  [new]
```
- **Maps to existing:** `components/settings/ProjectStaffingSection.tsx`, `ProjectOfficerModal.tsx`, `ProjectActorAddRow.tsx`, `ProjectGoLivePanel.tsx` all exist. `page.tsx:3682 ProjectActorRolesEditor` is **deleted**. Supervisor + donor UI are net-new.

## 3. Governing interaction rules
- **Implementing agency (DECISION §2):** single `implementing_agency_org_id`, **defaulted to the owning ministry**, must be `government`/`local_government` (server rejects contractor/donor with 422 via `validate_implementing_agency`). Because defaulted, go-live A3 is effectively always satisfied → folds into staffing gate.
- **Donor include + guardrail (DECISION §3, go-live A5):** donors optional & 0..n. Including a donor auto-populates the **last standard-track step's "Kept informed"** cast with the donor's roles (`donor_national`/`donor_hq`/`donor_consultant`); admin may trim to ≥1. **Go-live BLOCKS** if a donor is present but no donor role is in that cast (`A5`, severity `block`). **SEAH-suppressed** — the guardrail is standard-track only; a donor must receive nothing on a SEAH case.
- **Supervisor (DECISION §5):** per-`(project, step)` reassignment authority; resolver order = explicit → next-step Handler pool (default, shown-not-blank with provenance "Supervisor: L2 handler pool — change") → top-step requires explicit → null. Prefer a **pool** over a lone person. Distinct from escalation (which goes to the next step's Handler).
- **Unstaffed-level block (DECISION §7, go-live C5):** go-live blocks unless **every standard workflow level has ≥1 officer scoped to the project** (stricter than C1/C2 which cover L1/L2 only). Ticket-intake block = **L1 staffed** (C1).
- **Staffing empty-state CTA (F23):** pre-targets the exact actor + level ("Invite officer for L2 →"), reusing the one `InviteOfficer` component (Frame 03 delegate) — not a disabled button that hits `projectActors[0]`.
- **Contractor create + dedup (§2.4, SH-4):** create routes through a fuzzy candidate finder → **soft flag** ("Possible duplicate — Use existing / Create anyway"), never a hard block. Match signals: distinctive name tokens (skip generic stoplist), corporate email domain (free providers ignored), address.
- **Coverage warnings (retained strength):** "No officer scoped for {org} on this package" stays, per uncovered level, beside the staffing it refers to.

## 4. Concrete endpoints (real routers / lib/api.ts)
| Purpose | Method + path | Payload → Response | Wrapper |
|---|---|---|---|
| Load project (IA + donors read-only) | `GET /api/v1/projects/{project_id}` | → `ProjectResponse` incl. `implementing_agency_org_id`, `donor_org_ids[]` (`locations.py:202-221`, mapped `1196-1197`) | (add getProject wrapper; not present) |
| **Set implementing agency** | `PATCH /api/v1/projects/{project_id}` | `{implementing_agency_org_id}` → `ProjectResponse` (422 if not gov/local-gov — `locations.py:1459-1468`) | `updateProject` `api.ts:1858` — **`[GAP]` payload type lacks `implementing_agency_org_id`** (1858-1867) |
| Go-live detail (A5 donor, C5 all-levels) | `GET /api/v1/projects/{project_id}/go-live` | → `GoLiveReportResponse` (A5 `locations`… `project_go_live.py:309-338`, C5 `513-533`) | `getProjectGoLive` `api.ts:1840` |
| Packages (staffing rows) | `GET /api/v1/projects/{project_id}/packages` | → `list[PackageResponse]` | `listPackages(projectId)` `api.ts:2064` |
| Officer roster / scoping | staffing via `OfficerScope` + `ProjectOfficerModal`; invite delegate = Frame 03 | see Frame 03 (OC-03) | `ProjectOfficerModal.tsx` |
| Link/create contractor org | `POST /api/v1/organizations` then `POST /api/v1/projects/{project_id}/organizations/{organization_id}` | `OrganizationCreate` → `OrganizationResponse`; then link → `ProjectOrgItem` | `createOrganization` `api.ts:1741`; `addProjectOrg` `api.ts:1900` |
| IA / donor org picker (client-filter by category) | `GET /api/v1/organizations?country=` | → `list[OrganizationResponse]{org_category, unit_type, display_name_ne}` — **filter `org_category` client-side** (no category query param, `locations.py:335-364`) | `listOrganizations(country?)` `api.ts:1736` |
| Remove org from project | `DELETE /api/v1/projects/{project_id}/organizations/{organization_id}` | → 204 | `removeProjectOrg` `api.ts:1992` |

### `[GAP]` — critical, block RB-3:
- **No add/remove-donor endpoint anywhere.** `project_donors` table + `ProjectDonor` model exist (`models/project.py:101-116`), `ProjectResponse.donor_org_ids` is **read-only** (`locations.py:213`, `1197`), the A5 go-live check reads `project_donor_org_ids` — **but there is no `POST`/`PUT`/`DELETE` for donors, and `ProjectCreate`/`ProjectUpdate` do NOT accept `donor_org_ids`.** The donor-include UI (auto-fill guardrail, blocking state) is unwireable until backend adds e.g. `POST/DELETE /api/v1/projects/{id}/donors/{org_id}` (+ call `apply_donor_informed_defaults` on add). **Flag to doc-13 owner.**
- **`updateProject` TS wrapper omits `implementing_agency_org_id`** (`api.ts:1858-1867`) though the backend PATCH accepts it — add to the payload type before the IA field can be saved.
- **No supervisor endpoint surfaced** in `locations.py` project routes — the per-`(project,step)` supervisor (DECISION §5, resolver in OC-03/02-spec) needs its own read/write API for the Supervisor row; confirm with OC-03 owner (`[GAP]`).
- **Contractor fuzzy-dedup finder** (SH-4 extension to a candidate finder) — confirm the endpoint/response exists; today SH-4 only "warns on exact duplicate name."

## 5. Tokens / labels contract
- **Blocking donor/unstaffed states** use `danger` (`design-tokens.ts:70`) + `SeverityBadge` "Blocking"; coverage warnings use `warning` (`:83`) + "Warning" — never color-only.
- **Officers display by position title** ("SDE, Jhapa Division Office") with `RoleLabel` fallback (doc 16 §5.1) — never the raw role slug.
- **Friendly errors** — SH-3 jurisdiction 409 → `ErrorNotice` "That organisation isn't on this project…" via `formatUserFacingError` (`user-messages.ts:145`).
- **Bilingual** org names via `<Bilingual>` (`display_name_ne`); no banned hues/emoji.

## 6. Data owner (backend tickets)
- IA field + donor guardrail (A5) + all-levels-staffed (C5): **doc 13** / DECISION. Staffing invite + supervisor resolver: **OC-03** (+ 02-spec §54-58 reframe). Contractor dedup: **SH-4**. SEAH donor suppression: **OC-04 §5.6**.

## 7. Open gaps / risks for RB-2/3/4
1. **Donor CRUD endpoint missing** (above) — highest-priority blocker for this frame's new model.
2. **Supervisor read/write API unconfirmed** — the Supervisor row can't be built without it.
3. **`updateProject` wrapper** must gain `implementing_agency_org_id`.
4. **Category filtering is client-side only** — IA picker must exclude non-gov/local-gov, donor picker must show only `donor`; a bad selection is caught server-side (422) but the picker should pre-filter to avoid it.
5. **Deletion of `ProjectActorRolesEditor`** ripples: `getProjectActorRoles`/`setProjectActorRoles` (`api.ts:1981-1990`) + `project_actor_roles` routes (`locations.py:1666-1706`) become dead for this surface — confirm nothing else depends before removing from the tab.
