# Build sheet — Frame 13 · SEAH — setup & invisibility

> RB-0 build sheet. Grounds wireframe Frame 13 + atlas Surface 13 in the real API. **This frame is a CROSS-CUT, not a new tab** — SEAH is a track filter applied to existing surfaces (workflows, roles, staffing, directory), plus precise invisibility of case existence.
> Sources: DESIGN §7.F4, §3.1 row 13, §2.5 (SEAH-scoped org_admin); doc 16 §6 (shared chart, only SEAH case existence hidden); DECISION §3 (donor SEAH-suppression); wireframes Frame 13 (lines 1500-1545); atlas Surface 13 (lines 787-796). Data owner: **OC-04** (inline SEAH predicates, leak-proofing).

## 1. Visual ref
- **Wireframe Frame 13** + **Atlas Surface 13**. Two sides shown side-by-side.
- **As a SEAH admin:** a red-bordered card (`border-left:3px solid red`, `🔒 SEAH · restricted` badge) with the **SEAH workflow** (own cast — Handles it / Oversees — picker offers **SEAH-track roles only**), own staffing & invite. `Settings ▸ Workflows & roles ▸ SEAH`.
- **As a standard org_admin:** the same directory shows **Standard GRM only**; SEAH officers still **appear as people** (S. Sharma — SDE, Jhapa) but **"(no SEAH workflow, SEAH roles, or SEAH cases appear here)"** — a scope box: "SEAH cases are invisible here… a standard supervisor sees no trace that any subordinate has a SEAH case."
- **States (atlas Surface 13):** Loading (content loads only after SEAH gate passes) · Not a SEAH admin (the tab itself is **absent** — invisibility, not a locked door) · Directory shared (person visible, their SEAH cases not).

## 2. Component subtree (DESIGN §3 — cross-cut, no dedicated tree)
```
workflows/
  StepCast.tsx            [new]      the 4-slot cast; on the SEAH track, picker filters to SEAH-track roles (§4.3, doc 16 §6)
  WorkflowsRolesFlow.tsx  [new]      SEAH track appears as a workflow whose workflow_type/track === "seah"; gated to SEAH admins
officers/
  OfficersDirectory.tsx   [refactor] shared chart — SEAH officers appear as people; Standard/SEAH filter shows ONLY for a SEAH-capable admin
org/
  OrgTree.tsx             [fold+new] shared for directory; no SEAH case signal renders
lib/
  trackFilter.ts          [new]      SINGLE source of track-filter logic (kills the 4-way dup, F13/F24) — drives every SEAH gate
```
- **Maps to existing:** no single SEAH component — it is track filtering woven through `WorkflowsRolesFlow`, `StepCast`, `OfficersDirectory`, `OrgTree`, gated by the admin's `workflow_track`. `lib/trackFilter.ts` is the one place the standard-vs-SEAH predicate lives.

## 3. Governing interaction rules (doc 16 §6 + OC-04)
- **Setup mirrors standard, but gated (§7.F4):** SEAH gets its own workflow, cast, staffing, invite — **the whole surface is restricted to a SEAH `org_admin` / super_admin** (admin with `workflow_track` including `seah`). A standard-only admin **never sees the SEAH tab** (atlas "the tab itself is absent"), not a disabled/locked one.
- **Invisibility scoped precisely (doc 16 §6, pin 50 — round-2 correction):** **only SEAH case existence is hidden.** The chart is **shared for directory purposes** — SEAH officers appear as people in the directory/org tree. But **SEAH tickets, SEAH roles, and any signal of a SEAH case never render** in standard reporting-line, Watching, or notification surfaces. Track-scoped **at the query layer** (server), not merely hidden client-side.
- **SEAH-track role picker (§4.3):** every SEAH step-cast slot offers only roles whose track matches (`workflow_scope ∈ {seah, both}`), single-sourced via `lib/trackFilter.ts`; excluded roles greyed with "wrong track".
- **Donor SEAH-suppression (DECISION §3, OC-04 §5.6):** the donor last-step-informed guardrail (Frame 05 A5) is **standard-track ONLY** — on the SEAH track every donor tier is suppressed at the final step; a donor must receive **nothing** that reveals a SEAH case. Leak-proofing lives server-side in `engine/escalation._apply_step_tier_roles` (per `donor_guardrail.py:14-16`); SEAH-leak tests are the acceptance gate.
- **Admin appointment on SEAH track (§2.5):** appointing a SEAH admin uses `workflow_track="seah"` (or `both`) on `AdminScopeCreate`; a SEAH-only org_admin must not get standard-track rights and vice-versa (attenuation + track, `create_admin_scope`).

## 4. Concrete endpoints (real routers / lib/api.ts) — all EXISTING, filtered by track
| Purpose | Method + path | Track filter | Wrapper |
|---|---|---|---|
| Am I a SEAH admin? (gate the tab) | `GET /api/v1/users/me/admin-context` | `"seah" ∈ admin_workflow_tracks` decides tab visibility | `getAdminContext()` `api.ts:820` |
| SEAH workflow + cast | `GET /api/v1/workflows?...` then step reads | filter `workflow_type`/track === `"seah"` | `listWorkflows` `api.ts:593`, `getWorkflow` `api.ts:622` |
| SEAH-track role picker | `GET /api/v1/roles?...` | filter `workflow_scope ∈ {seah, both}` (client `trackFilter.ts`; server SH-7 org-scoped) | `listRoles(params?)` `api.ts:754` |
| Officers directory (shared) | `GET /api/v1/officers` / roster | people visible to all; **no SEAH case field returned** to standard admins | `listOfficers()` `api.ts:733`, `listOfficerRoster()` `api.ts:898` |
| SEAH staffing / go-live (C4) | `GET /api/v1/projects/{id}/go-live` | C4 "SEAH L1 officer" check (`project_go_live.py:485-511`) when `seah_workflow_id` set | `getProjectGoLive` `api.ts:1840` |
| Link SEAH workflow to project | `PATCH /api/v1/projects/{id}` | `{seah_workflow_id}` — 403 unless `can_assign_project_workflow(user,"seah")` (`locations.py:1503-1531`) | `updateProject` `api.ts:1858` |
| Appoint SEAH admin | `POST /api/v1/admin-scopes` | `{role_key, workflow_track:"seah"}` (`schemas/user.py:75`) | `createAdminScope` `api.ts:828` |

### `[GAP]` / notes:
- **No dedicated "SEAH" endpoint** — correct by design; SEAH is a track predicate over the existing workflow/role/staffing/admin-scope endpoints. The build's job is to apply `trackFilter` **consistently** and rely on server-side track scoping (OC-04) as the authoritative gate.
- **Invisibility must be server-enforced** — the directory/roster and notification endpoints must **not return SEAH case existence** to a standard admin. RB cannot achieve invisibility by client hiding alone; verify OC-04 predicates strip SEAH tickets/roles/case-signals at the query layer for standard-track callers. (Client hiding of an already-leaked payload is a fail.)
- **Standard/SEAH directory filter** appears **only** for a SEAH-capable admin (pin 45 / round-2 fix) — gate the filter control on `admin-context`, else its mere presence leaks that SEAH exists.

## 5. Tokens / labels contract
- **SEAH red badge + border (design-system):** `🔒 SEAH` badge and subtle red left border use the `danger` token family (`design-tokens.ts:69-79` — "RED Danger, SEAH"), text `text-red-700/800`, border `border-red-100/200`, bg `bg-red-50`. The lock is a Lucide icon via `@/lib/icons`, **not** an emoji.
- **Track as plain words:** "SEAH grievances" / "SEAH · restricted", never `seah` slug; standard side shows "Standard grievances" (§7.C).
- **Roles as labels** via `RoleLabel`; **Bilingual** officer/office names via `<Bilingual>` (people are shared, so names still render bilingually).
- **Friendly errors** — a non-SEAH admin never reaches an error (the tab is absent); any track-mismatch 403 (e.g. linking SEAH workflow) → `ErrorNotice` + `formatUserFacingError`.
- No banned hues elsewhere; red is reserved for SEAH/danger only.

## 6. Data owner (backend tickets)
- **OC-04** — inline SEAH predicates + leak-proofing (the query-layer invisibility, donor SEAH-suppression tests). Admin track-scoping: **SH-7**. Shared-chart / case-existence-hidden model: **doc 16 §6**.

## 7. Open gaps / risks for RB-2/3/4
1. **Invisibility is a server contract, not a UI toggle** — the single biggest risk. Every list/notification endpoint a standard admin can hit must be verified (OC-04) to exclude SEAH case existence; a client that merely `display:none`s leaked data fails the SEAH-leak acceptance test.
2. **`trackFilter.ts` must be the single source** — DESIGN flags 4 diverging implementations today (`page.tsx:414-418,1978-1982`, `users.py`, `admin_access.py`); the SEAH gate breaks if a surface uses a stale copy.
3. **Directory-filter presence leaks existence** — the Standard/SEAH filter, and any SEAH count/badge, must be gated on `admin-context` track membership, not just filtered results.
4. **Donor SEAH-suppression** (Frame 05 ↔ 13 interaction) — the standard-track A5 guardrail must never fire on SEAH; confirm `_apply_step_tier_roles` suppression is covered by a payload-content assertion (DECISION §9).
5. **Dual-track admins (`both`)** see both sides — ensure the shared directory doesn't double-render or cross-contaminate track-scoped role pickers.
