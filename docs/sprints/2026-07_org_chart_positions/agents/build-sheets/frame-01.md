# Build sheet — Frame 01 · Setup & go-live landing

> RB-0 build sheet. Grounds wireframe Frame 01 + atlas Surface 01 in the real API. Input to RB-2/3/4.
> Sources: DESIGN §2.3, §7.A, D6; wireframes `settings-wireframes.html` Frame 01 (lines 459-597); atlas `settings-state-atlas.html` Surface 01 (lines 292-348).

## 1. Visual ref
- **Wireframe Frame 01** (happy-path + first-run variant) · **Atlas Surface 01** (loading / error / blocked / ready).
- The Settings **landing** (not a domain tab). Full app shell shown once (sidebar + Settings tab bar: `⌂ Setup & go-live · Organisation · Workflows & roles · Projects · Platform`).
- Two modes: **(a) per-project go-live spine** — one plain "next blocker" line ("KL Road is 1 step from going live"), a live checklist (Blocking / Warning / Done rows, each with text severity + color dot + deep-link "Fix →"), a `Go live →` button enabled only when no Blocking item remains, and four "Jump into a journey" domain cards each showing its own Ready/blocker state. **(b) First-run mode** (zero projects) — an ordered 5-step checklist (Add ministry → Workflows & roles → Project → Officers → Go live) with Not started / In progress / Done status + inward CTA.
- **States (atlas):** Loading = streaming skeleton, Go-live button stays disabled; Error = `ErrorNotice` "We couldn't check go-live status just now. Your setup is safe. Try again" — never a false "ready"; Blocked = one blocker + disabled button; Ready = single green verdict (no "activated-but-blocked" limbo).

## 2. Component subtree (DESIGN §3, overview/)
```
overview/
  SetupOverview.tsx        [new]   landing container; picks first-run vs per-project mode by whether any project exists (D1, D6, §7.A)
    SetupChecklist.tsx     [new]   first-run ordered 5-step checklist (§7.A)
    GoLiveSpine.tsx        [new]   per-project live checklist; elevates ProjectGoLivePanel logic (D6, F9, F17)
      shared/SeverityBadge.tsx  [new]  "Blocking"/"Warning"/"Done" text + dot (F11)
      shared/ErrorNotice.tsx    [new]  wraps lib/user-messages.ts formatUserFacingError (F11)
    (domain entry cards)   [new]   Organisation / Workflows & roles / Projects / Platform status cards
```
- **Maps to existing:** `components/settings/ProjectGoLivePanel.tsx` is the logic donor for `GoLiveSpine` (it already renders `getProjectGoLive` checks) — but it uses **raw color dots** (`bg-red-500`/`bg-amber-400`/`bg-green-500`, `ProjectGoLivePanel.tsx:14-18`) with **no text severity**. RB-3 rebuilds it onto `design-tokens.ts` + `SeverityBadge`. `page.tsx` currently has no `SetupOverview` — it is net-new landing.

## 3. Governing interaction rules
- **Setup spine / next-blocker (§2.3, D6, F17):** collapse the two verdicts `can_activate` vs `can_accept_tickets` into ONE plain sentence. Compute the single "next blocker" from `checks` where `severity==="block" && status==="fail"` (blocking IDs `A3`, `A5`, `C5`; `C1` blocks ticket intake). "Warning" = `status==="warn"`. "Done" = `status==="pass"`.
- **Live-refresh (F9):** re-fetch `GET /projects/{id}/go-live` after every structural mutation elsewhere (staffing, workflow link, IA/donor change). Never render a stale checklist. A failed read shows `ErrorNotice`, never a false green (atlas Surface 01 Error tile).
- **Deep-link "Fix →" (D6/F9):** each check's `section` field (`"workflows" | "actors" | "packages" | "staffing" | "locations" | "messaging" | null`, from `project_go_live.py`) routes to the exact surface. Example: C5/C1 (`section="staffing"`) → Projects ▸ Staffing.
- **First-run spine (§7.A):** step done-predicates computed from real state — (1) `≥1 org root` exists, (2) `≥1 published workflow`, (3) `≥1 project`, (4) required actors staffed, (5) a project has no blockers. Steps unlock in order but do not hard-gate.
- **Persona/track gating (§2.5, §7.E):** topbar renders "Signed in as **Organisation admin** · Standard grievances" from `is_org_admin` + `admin_workflow_tracks`. Landing is scoped to the admin's projects.

## 4. Concrete endpoints (real routers / lib/api.ts)
| Purpose | Method + path | Payload → Response | Wrapper |
|---|---|---|---|
| List projects (choose which spine / first-run) | `GET /api/v1/projects?country=&active_only=false` | → `list[ProjectResponse]` | `listProjects(country?, activeOnly=true)` `api.ts:1799` |
| Per-project go-live checklist | `GET /api/v1/projects/{project_id}/go-live` | → `GoLiveReportResponse{checks[]{id,label,group,severity,status,message,section}, can_activate, can_accept_tickets, summary}` | `getProjectGoLive(projectId)` `api.ts:1840` (`GoLiveReport` iface `api.ts:1697-1712`) |
| Activate ("Go live →") | `PATCH /api/v1/projects/{project_id}` | `{is_active:true}` → `ProjectResponse` (422 with `activation_block_message` if `!can_activate`) | `updateProject(id,{is_active})` `api.ts:1858` |
| Admin persona/track for topbar + scoping | `GET /api/v1/users/me/admin-context` | → `AdminContextResponse{is_super_admin,is_org_admin,is_project_admin,admin_workflow_tracks[],admin_project_ids[],can_create_project,...}` | `getAdminContext()` `api.ts:820` |
| First-run step-1 done? (org roots) | `GET /api/v1/organizations?active_only=true` | → `list[OrganizationResponse]` | `listOrganizations(country?)` `api.ts:1736` |
| First-run step-2 done? (published workflow) | `GET /api/v1/workflows?...` | → workflow list; check `status==="published"` | `listWorkflows(...)` `api.ts:593` |

- Backend go-live source: `ticketing/services/project_go_live.py:213-638` (`evaluate_go_live`) — `_ACTIVATION_BLOCK_IDS={"A3","A5","C5"}` at line 632; `activation_block_message` 641-650; `ticket_intake_block_message` (C1) 653-663. Router: `ticketing/api/routers/locations.py:1319-1341`.
- `[GAP]` **No single "landing status" endpoint.** RB-3 composes first-run + per-project state from `listProjects` + N× `getProjectGoLive` + `getAdminContext` + `listOrganizations`/`listWorkflows` (as §3.1 index states: "RB-3 composes existing status, no new endpoint"). Consider a batched aggregate if N projects makes N+1 go-live calls costly.

## 5. Tokens / labels contract
- **No raw color** — replace `ProjectGoLivePanel.tsx:14-18` dots with `design-tokens.ts` `danger`/`warning`/`success` (`lib/design-tokens.ts:70-102`). `SeverityBadge` renders **text label beside the dot** ("Blocking"/"Warning"/"Done") — never color-only (F11).
- **Friendly errors** — the "couldn't compute" tile routes through `formatUserFacingError` (`lib/user-messages.ts:145`) via `ErrorNotice`.
- **Labels not slugs** — the next-blocker line uses `check.message` (already plain-language from `project_go_live.py`); never print check IDs (A5/C5) on screen.
- **Bilingual** — project/org names in domain cards via `<Bilingual>` where `display_name_ne` present (D4). No banned hues, no emoji (the wireframe's `⌂`/`⚠`/`✓` are Lucide icons in the real build, via `@/lib/icons`).

## 6. Data owner (backend tickets)
- Go-live checks incl. **A5 donor guardrail + C5 all-levels-staffed**: **doc 13** / DECISION §7 (as-built `project_go_live.py`). Admin context/persona: **SH-7**. Composition only — no new endpoint (§3.1 index row 01).

## 7. Open gaps / risks for RB-2/3/4
1. **N+1 go-live reads** on the landing when many projects exist — no aggregate endpoint (`[GAP]`). Cache / batch.
2. **First-run "required actors staffed" predicate** has no direct endpoint — must be inferred from each project's C1/C5 go-live checks; define precisely so step 4 doesn't flicker.
3. `GoLiveSpine` must **re-fetch on cross-surface mutations** (staffing, workflow link, IA/donor) — wire a shared invalidation signal or the "live-refresh" (F9) promise breaks.
4. Existing `ProjectGoLivePanel` shows every check flat; the spine must **rank to one next blocker** and collapse Done rows — new presentation logic, not a port.
5. Topbar persona label depends on `admin-context`; ensure `SetupOverview` blocks on it (atlas Surface 06 loading note) so the wrong scope never briefly renders.
