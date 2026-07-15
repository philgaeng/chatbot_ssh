# T3-05 — Extract the remaining settings tab clusters (S/M)

> Workstream E · Branch `dev/tier3-structural` · **Phase 3** · **Independent** — touches only `channels/ticketing-ui/`.
> Evidence: [`00-reassessment.md`](00-reassessment.md) §2. **The source review is half-wrong about this item** — read §2 first.
> Line numbers as of `dev/tier3-structural` @ 2026-07-15 — **these will drift as soon as you start moving code. Re-locate constantly.**

---

## ⚠️ Two review claims are dead — do not chase them

The review says: *"Split the 4,372-line settings page into per-tab components — **L** — Kills the hooks-crash class, cuts the settings bundle, unblocks parallel work."*

1. **"Kills the hooks-crash class" — already banked.** HR-06 (Tier 1) fixed it: see `2026-07_hardening/PROGRESS.md` HR-06 — *"Settings hooks-order fixed (0 `rules-of-hooks` errors)"*. `SettingsPage` (`app/settings/page.tsx:4167`) calls **every** hook unconditionally before its `if (!isAdmin)` early return (`:4255`). **There is no violation left to fix.** Do not "fix" one.
2. **"L effort" — no longer true.** The org-chart sprint (`2026-07_org_chart_positions/`) already did the hard part: `components/settings/` is now **7,748 lines across 27 files**, and the shell is already a clean **206-line** delegator.

**The honest remaining benefit is bundle size, reviewability, and unblocking parallel work — not crash-class elimination.** Scope and claim accordingly; do not oversell this ticket in the sprint summary.

---

## Problem

`app/settings/page.tsx` is still **4,372 lines** because six tab clusters remain defined **inline** rather than extracted. The shell that consumes them is already correct.

| Block | Lines @ 2026-07-15 | ~Size | Target |
|---|---|---|---|
| Workflows — `StepForm`, `ProjectWorkflowSelect`, `ProjectWorkflowsEditor`, `WorkflowEditor`, `WorkflowNotificationsPanel`, `NewWorkflowModal`, `WorkflowsTab` + helpers (`workflowTrackOf`, `bindingsFromProject`, `publishedWorkflowOptions`, `emptyBinding`, `statusBadge`, `typeBadge`, `WorkflowRoleOption`, `WorkflowBindingDraft`, `NOTIFICATION_EVENTS`, `SEAH_EVENTS`, `NOTIF_TIERS`, `NOTIF_CHANNELS`) | 765–2172 | ~1,410 | `components/settings/workflows/` |
| Projects — `ProjectsSection`, `ProjectCreateModal`, `ProjectEditor`, `PackageRow`, `PackageCreateModal` | 2426–3776 | ~1,350 | `components/settings/projects/` (**exists** — `ProjectParticipants.tsx` already there) |
| Roles — `RoleEditModal`, `RoleCreateModal`, `RolesTab` + `RoleEntry`, `mapGrmRoleToEntry`, `owningLevelLabel` | 166–564 | ~440 | `components/settings/roles/` |
| `SystemConfigTab` + `DEFAULT_*_JSON` consts | 3777–4123 | ~350 | `components/settings/platform/` |
| `LocationsSection` | 2173–2425 | ~253 | `components/settings/platform/` |
| `AdminAccessTab` | 565–764 | ~200 | `components/settings/platform/` |

**Leave in `page.tsx`:** the shell (`SettingsPage` `:4167-4372`), the tab types + `MAIN_TABS` (`:290-307`), `SettingsSubTabs` (`:4138`), `ComingSoon` (`:4124`). Target for `page.tsx` afterwards: **~250 lines**.

## The seams are clean — verified

Every shared symbol in the file was mapped. Only **two** cross cluster boundaries:

| Symbol | Defined | Cross-cluster use | Resolution |
|---|---|---|---|
| `RoleCreateModal` | `:308` (roles) | workflows `StepForm` at `:871` | import from `components/settings/roles/` |
| `ProjectWorkflowsEditor` | `:1144` (workflows) | projects `ProjectEditor` at `:3099` | import from `components/settings/workflows/` |

Both are **ordinary imports, not refactors**. Everything else is cluster-internal:
- `statusBadge` (`:767`) → used `:1539`, `:2089` — workflows only
- `typeBadge` (`:777`) → `:1568`, `:1880`, `:1888`, `:2085`, `:2129` — workflows only
- `workflowTrackOf` (`:1109`) → 12 uses, all `1109`–`2122` — workflows only
- `SettingsSubTabs` (`:4138`) → `:4297`, `:4322`, `:4362` — shell only

**Shared utils:**
- `friendlyError` (`:124`) — **34 uses across every block**. Extract to `components/settings/lib/friendlyError.ts` (or reuse an existing util if one exists — grep first). This one moves first; everything else depends on it.
- `RoleEntry` / `mapGrmRoleToEntry` (`:130`, `:144`) — used by roles (`:167`, `:415`…), workflows (`:1932`), **and the shell** (`:4200`, `:4212`). Put the type + mapper in `components/settings/roles/` and import from all three.

---

## Change

**This is mechanical file movement. It is not a redesign.** The prime directive: **zero behavior change**.

1. **Move `friendlyError` first** (its own commit) — 34 call sites, unblocks everything else.
2. **Extract one cluster per commit**, in ascending risk order: `AdminAccessTab` → `LocationsSection` → `SystemConfigTab` → Roles → Workflows → Projects. Each commit: move the code, add imports, `tsc` + `eslint` + `vitest` + `build` green, commit.
3. **Move code verbatim.** Do **not** rename, re-style, "improve", re-type, or reorganize props while moving. A move commit that also changes behavior is unreviewable — and this file has no test coverage to catch you (see below).
4. **Follow the existing conventions** in `components/settings/` — the org sprint set them (`org/`, `officers-v2/`, `overview/`). Match the export style, file naming, and `@/components/settings/...` import path shape used by the 10 existing imports at `page.tsx:6,102-116`.
5. **Props over context.** The extracted tabs currently close over shell state (`roleCatalog`, `rolesLoading`, `loadRoleCatalog`, `grmRoleChoices`, the `can*` flags). The shell already passes these explicitly to `WorkflowsTab`/`RolesTab`/`ProjectsSection` (`:4310-4345`) — **keep that shape**. Do not introduce a context or a store in this ticket.
6. **Watch for hooks-order regressions while moving.** The class is fixed, but *you* can reintroduce it. `eslint` has `react-hooks/rules-of-hooks` as an **error** (HR-05 deliberately reserved the error channel for exactly this) — a violation fails CI. Do not downgrade it. If you hit one, fix the code, not the rule.

---

## Tests (acceptance)

**Honest constraint: `app/settings/page.tsx` has no direct test coverage.** Portal vitest is 61 tests / 8 files (H2-01 auth, H2-06 thread hook, HR-06 seed) — **none cover settings**. The safety net for this ticket is `tsc` + `eslint` + `build` + manual click-through.

- [ ] `npx tsc --noEmit` clean at **every** commit.
- [ ] `npx eslint .` — **0 errors** at every commit; warning count **does not increase** (baseline: 141 warnings, tracked in [`../2026-07_hardening/followups/portal-lint-cleanup.md`](../2026-07_hardening/followups/portal-lint-cleanup.md)). If your move surfaces new warnings, that is a signal you changed something.
- [ ] `npm run build` green at every commit.
- [ ] `npm test` — existing 61 vitest still green.
- [ ] **Add at least a smoke test per extracted tab** (render + assert the tab's heading/primary control). This ticket is the natural moment to start settings coverage from zero — the components become individually mountable *because* of the extraction. Small, but it makes the next settings change safe.
  > If skipped for scope, **log it as a followup + TODO.md row** — do not leave it silently untested.
- [ ] **Bundle check**: record the settings route's build size before and after (`next build` output). The stated benefit is bundle size — **measure it, don't assume it**. If it doesn't move, say so in the summary rather than claiming it did.

## Manual verification

Every tab, at the roles that can see it (the shell's gating at `:4178-4196` is role-dependent — `isSuperAdmin` / `isCountryAdmin` / `isProjectAdmin` / `isAdmin` see different tab sets):

- [ ] **Setup** overview renders; "open project" jump still navigates to Projects (`navigateToProject`, `:4238`).
- [ ] **Org & officers** → both sub-tabs (already extracted — regression check only).
- [ ] **Workflows & roles** → Workflows: list, create, edit steps, notifications panel, project bindings. Roles: list, create, edit, delete.
- [ ] **Projects** → list, create, edit, packages, participants, staffing, go-live.
- [ ] **Platform** (super_admin) → Locations, Quarterly reports, Project types, Advanced (JSON), Admin access.
- [ ] Role-gating unchanged: a `project_admin` sees exactly the tabs they saw before; a non-admin still gets the lock screen (`:4255`).
- [ ] *(May be marked pending-human if no browser/Keycloak is available — record as such. Note H2-02/H2-06's UI click-through parity sweeps are **also** still pending-human; see [`../2026-08_tier2_quality.md`](../2026-08_tier2_quality.md) §Leftovers. Consider one combined session.)*

---

## Out of scope — log, don't fix

- **Redesigning any tab.** If a tab is badly structured, that is a separate ticket. Move it as-is.
- **The 141 ESLint warnings** — already tracked in `portal-lint-cleanup.md`. Do not fix them here; do not let the count grow either.
- Anything else found while moving → PROGRESS.md → Deviations + followup + TODO.md row.
