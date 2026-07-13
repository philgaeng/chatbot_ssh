# Build sheet — Frame 10 · Create a project (+ workflow link)

> RB-0 build sheet. Grounds wireframe Frame 10 + atlas Surface 10 in the real API.
> Sources: DESIGN §7.B (B1 project+package create, B3 workflow→project link, B4 clone-template), §3.1 row 10; DECISION §2 (IA defaulted at create); wireframes Frame 10 (lines 1323-1388); atlas Surface 10 (lines 755-763). Data owner: project create (existing) + country validation **SH-4 / B1**; IA field **doc 13**.

## 1. Visual ref
- **Wireframe Frame 10** + **Atlas Surface 10**. `Settings ▸ Projects ▸ New project`.
- Top-down cards: **Project details** (Name EN, Name Nepali, Country ▾ validated, Project type ▾) → **Packages** (add rows: name + area/location scope) → **How grievances are handled** (Standard workflow picker — **published only**, drafts greyed "publish it first"; optional SEAH workflow ▾) → info strip "Created **switched off** — turns on at go-live once every package is staffed" → `Cancel` / `Create project` → green **"Next: invite your officers"** strip.
- **States (atlas Surface 10):** Loading (country list + workflow options load first) · Error — validation ("Pick a country and give the project a name") · No workflow to link yet ("No published workflow yet. Set one up first — or save as draft").

## 2. Component subtree (DESIGN §3, projects/)
```
projects/
  ProjectEditor.tsx     [extract]  create/edit form (from page.tsx ProjectCreateModal ~2840 / ProjectEditor ~3002)
    (Package add rows)  [new]      name + location scope, created up front (§7.B1)
    (Workflow linker)   [new]      published-only picker + "publish it first" why-excluded (§7.B3, reuses Frame 04 valid-only pattern)
    (IA defaulting)     [new]      implementing_agency_org_id defaulted to owning ministry (DECISION §2)
    ("Next:" strip)     [new]      §7.A end-of-surface next-step pattern (pin 56)
  shared/ErrorNotice.tsx  Bilingual.tsx  [new]
```
- **Maps to existing:** `app/settings/page.tsx:2840 ProjectCreateModal` + `:3002 ProjectEditor`. Package creation + published-only workflow picker + IA defaulting + "Next:" strip are net-new; the create call itself exists.

## 3. Governing interaction rules
- **B1 create switched-off (§7.B1):** a typed project (`project_type_key` set) is created `is_active=false` (`locations.py:1270-1272`); it appears in the first-run spine + go-live (Frame 01) until activated. No activated-but-blocked limbo.
- **Country validation (SH-4 / B1):** country must exist → server 422 if not (`locations.py:1259-1261`); `short_code` normalized/validated (`ProjectCreate._normalize_short_code`, `locations.py:140-146`) and unique (409 if taken, `:1263-1268`). Surface both as friendly errors (atlas "Pick a country…").
- **B3 workflow link — published only:** the Standard picker lists only `status==="published"` workflows; drafts render greyed with "publish it first" (same valid-only / why-excluded pattern as the Frame 04 step binder). Optional SEAH workflow slot. Linking uses the `standard_workflow_id`/`seah_workflow_id` fields on `PATCH` (which internally map to workflow bindings, `locations.py:1478-1533`; `_validate_project_workflow` enforces published + correct type). For a brand-new project, create first, then PATCH the workflow link (create body has no workflow field).
- **B4 clone-a-template (primary path):** "Start from a template" is the least-decisions path (Frame 04 concern) — mostly relevant to the workflow authoring frame, but the project create's "How grievances are handled" step assumes a published workflow already exists; if none, the atlas "No workflow to link yet" state offers "Set one up first / save as draft".
- **IA defaulting (DECISION §2):** `implementing_agency_org_id` defaults to the owning ministry; must be `government`/`local_government` (422 via `validate_implementing_agency`, `locations.py:1285-1290`). Optional on the create form (defaulted server-side / by convention).
- **"Next:" pattern (§7.A, pin 56):** every task surface ends naming the next step — here a green "Next: invite your officers" strip after create.

## 4. Concrete endpoints (real routers / lib/api.ts)
| Purpose | Method + path | Payload → Response | Wrapper |
|---|---|---|---|
| **Create project** | `POST /api/v1/projects` | `ProjectCreate{country_code, short_code, name, description?, is_active?, project_type_key?, implementing_agency_org_id?}` → `ProjectResponse` (422 bad country / 409 dup short_code / 422 IA-not-gov) (`locations.py:1246-1316`, schema `:127-146`) | `createProject(payload)` `api.ts:1806` — **`[GAP]` `ProjectCreate` iface `api.ts:1667-1674` lacks `implementing_agency_org_id`** |
| Countries (validated dropdown) | `GET /api/v1/countries` | → `list[CountryResponse]` (`locations.py:906`) | (add wrapper if absent) |
| Project types (dropdown) | `GET /api/v1/project-types?active_only=true` | → `list[ProjectTypeItem]` | `listProjectTypes()` `api.ts:1844` |
| Add package | `POST /api/v1/projects/{project_id}/packages` | `PackageCreate` → `PackageResponse` (`locations.py:1918`) | `createPackage(projectId, payload)` `api.ts:2068` |
| Package location scope | `POST /api/v1/projects/{project_id}/packages/{package_id}/locations/{location_code}` | → 201 (`locations.py:1988`) | (package location wrapper) |
| Workflows for the "published only" picker | `GET /api/v1/workflows?...` | → workflow list; filter `status==="published"` | `listWorkflows(...)` `api.ts:593` |
| Link standard/SEAH workflow (post-create) | `PATCH /api/v1/projects/{project_id}` | `{standard_workflow_id?, seah_workflow_id?}` → `ProjectResponse` (403 if not track-authorized; `_validate_project_workflow` → 422 if draft/wrong type) (`locations.py:1478-1533`) | `updateProject` `api.ts:1858` |
| Set IA (if surfaced on form) | `PATCH /api/v1/projects/{project_id}` | `{implementing_agency_org_id}` → `ProjectResponse` | `updateProject` — **`[GAP]` payload type lacks the field** (`api.ts:1858-1867`) |

### `[GAP]`:
- **`ProjectCreate` TS interface omits `implementing_agency_org_id`** (`api.ts:1667-1674`) though the backend `POST /projects` accepts it — add before the IA field can be set at create time.
- **`updateProject` TS payload omits `implementing_agency_org_id`** (`api.ts:1858-1867`) — same fix as Frame 05.
- **No donor field at create** — consistent with the donor-CRUD gap (Frame 05 `[GAP]`); donors are added post-create only, and even that endpoint is missing.
- Confirm a **`getCountries`/`listCountries`** wrapper exists in `api.ts` for the validated country dropdown; if not, add one against `GET /api/v1/countries`.

## 5. Tokens / labels contract
- **Bilingual names** — Name EN + Name Nepali fields feed `name` (+ `display_name_ne` on org, but project has no `_ne` name field yet — see risk 4); render existing names via `<Bilingual>` (D4).
- **Published-only / why-excluded** greyed drafts use gray tokens + a plain "publish it first" note — not color-only.
- **Friendly errors** — 422 country / 409 short_code → `ErrorNotice` + `formatUserFacingError` (`user-messages.ts:145`); "Pick a country and give the project a name" (atlas).
- **"Next:" strip** uses `success` tokens (`design-tokens.ts:95`), green — an allowed hue. Info strip ("switched off") uses `primary`/blue. No banned hues, no emoji (Lucide via `@/lib/icons`).
- **Project type shown as label** ("Road construction"), never the `project_type_key` slug (§7.C).

## 6. Data owner (backend tickets)
- Project + package create: existing (`locations.py`). Country/short_code validation: **SH-4 / B1**. IA field: **doc 13** / DECISION §2. Workflow link (published-only): existing binding logic + B3.

## 7. Open gaps / risks for RB-2/3/4
1. **IA at create is unwireable in TS** until `ProjectCreate` (and `updateProject`) gain `implementing_agency_org_id`.
2. **Workflow link is a second call** — a new project is created without workflows, then PATCHed; the create form's "How grievances are handled" step must sequence create→PATCH (and handle partial failure). Consider whether B1 wants create+link atomic.
3. **Project Nepali name has no column** — `ProjectCreate` accepts only `name` (no `name_ne`); the wireframe's "Name (Nepali)" field has nowhere to persist. Confirm with doc-13 owner whether to add `name_ne`, else drop the field (don't fabricate).
4. **Package "area it covers"** maps to `PackageLocation` — the add-package UX must chain package create → location attach; surface as one step.
5. **Empty-workflow dead-end** (atlas "No workflow to link yet") — must offer "Set one up first / save as draft", not block; a draft project (`is_active=false`) is the escape.
