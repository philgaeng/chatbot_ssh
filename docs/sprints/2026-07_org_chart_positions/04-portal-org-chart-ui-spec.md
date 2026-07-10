# OC-05 — Portal: org-chart & positions UI

> **Standing rule — keep [`PROGRESS.md`](PROGRESS.md) current.** Update it at **every commit** for this ticket: status, checklist ticks, deviations, and (for schema work) the migration-head table. A commit that changes sprint state without a matching PROGRESS update is incomplete. (Same rule in the sprint [README](README.md), [agents/README](agents/README.md), and [agents/BUILD-HANDOVER](agents/BUILD-HANDOVER.md).)

> Workstream: portal · Branch `orgchart/oc-05-portal` · **After** OC-01..04 land **and after** hardening HR-06 (shared file).
> Feature source: [`docs/ticketing_system/16_org_chart_and_positions.md`](../../ticketing_system/16_org_chart_and_positions.md) §5.1, §5.2, §4. Grounded by the OC-06 UX evaluation ([05-admin-setup-ux-evaluation.md](05-admin-setup-ux-evaluation.md)) — read it first.
> **Hard rule from the review:** do not grow the 4,717-line god-file. All new UI is new `components/settings/*` components; the only edit to `app/settings/page.tsx` is tab wiring.

---

## Where it goes (verified)

`channels/ticketing-ui/app/settings/page.tsx` (4,717 lines) already delegates to a `components/settings/` folder with 12 per-tab components (`OrganizationsTab.tsx`, `OfficersTab.tsx`, `OfficerModals.tsx`, `OfficerScopeTable.tsx`, `OfficerJurisdictionForm.tsx`, `ProjectStaffingSection.tsx`, `ProjectTypesTab.tsx`, …). Main tabs at `page.tsx:264-273`: `org_officers`, `workflows_roles`, `projects`, `platform`; render block at `page.tsx:4640-4712`. Org-chart UI slots under `org_officers` as a new sub-tab (or extends the existing `organizations` sub-tab), rendered from **new** components.

## Change

Build these as new files in `components/settings/`, wired in via a **~5-line** addition to the `page.tsx` sub-tab switch (the only allowed edit to that file):

1. **`OrgTreeTab.tsx`** — org-unit tree editor: nested tree view (parent → children), create/edit unit modal (`unit_type`, `parent`, `territory_location_code`, `territory_includes_children`, `display_name` + `display_name_ne`), and the **CSV import** panel (upload → server validates → show row errors → confirm). Reuse `OrganizationsTab.tsx`/`OrgCreateModal.tsx` patterns and the design system ([`ui/02_design_system.md`](../../ticketing_system/ui/02_design_system.md) — icon rules, palette, no emoji). Consumes the OC-01 endpoints via typed `apiFetch` wrappers added to `lib/api.ts` (follow its section-header conventions; keep `apiFetch`'s signature stable).
2. **`PositionTypesTab.tsx`** — position-type catalog editor: table of types with `display_name`, `allowed_unit_types`, `reports_to_position_key`/`locus`, **`default_role_key` (the matrix)**, `visibility_mode`, `workflow_track`. Create/edit modal validates against roles + unit types (server is source of truth; surface server 400s inline). Editing `default_role_key` shows the **"review holders"** prompt (doc 16 §4) — a non-blocking notice listing current holders, since the change does not re-sync them.
3. **Invite pre-fill flow** (doc 16 §5.2) — the comprehensible one-action path for low-IT-literacy admins: in the officer invite/Manage modal (`OfficerModals.tsx` / `OfficerJurisdictionForm.tsx`), add an org-unit **tree picker** → position-type select (filtered by the unit's `allowed_unit_types`) → role/org/scope fields **pre-fill** and remain editable. On save, the existing invite call carries the `position` selection (OC-03). Show the **override badge** when the chosen role differs from the matrix default.
4. **Display surfaces** (§5.1): show `position title, org unit` on the officer roster (`OfficersTab`), ticket assignee chips, timeline event actors, and the reports export column — replacing the bare role key where a position exists. Fall back to the role label when an officer has no position.
5. **`lib/api.ts`** typed wrappers for every OC-0x endpoint (organizations tree/import, position-types CRUD, users positions, supervisor). One wrapper per endpoint, matching the existing 153-endpoint style.

## Sequencing & isolation (the HR-06 seam)

- Land **after HR-06** merges its `page.tsx` hooks fix, then rebase. If OC-05 must start earlier, keep the `page.tsx` diff to the tab-wiring lines only and rebase — never edit near the ~4590 hooks region HR-06 owns.
- No page split (that's Tier-3); no new state-management library; no `apiFetch` signature change (153 callers depend on it).

## UX guardrails (from OC-06)

- The invite pre-fill must be **one comprehensible action** (tree → position → done), not a form the admin re-fills. Every pre-filled field shows where it came from ("from position: SDE").
- Nepali labels (`display_name_ne`) are **translator-gated** — render them when present, never fabricate; where absent, fall back to English and mark for the translation sheet. No hardcoded Nepali strings in components.
- Match the design system; the new tabs must look native to the existing settings shell (no new visual language).

## Tests (acceptance)

Vitest (`components/settings/__tests__/` or co-located, matching the HR-06 vitest seed):
- [ ] Pure logic extracted and unit-tested: `allowed_unit_types` filtering of the position select; override-badge predicate (chosen role ≠ matrix default); tree flatten/nest helper.
- [ ] Invite pre-fill: picking a position sets role/org/scope from the matrix; editing a field overrides it; the payload sent carries the position + final (possibly overridden) values.
- [ ] Error handling: server 400 on position-type save renders inline (not a silent failure — the HR-06 pattern); CSV import row errors render as a list with nothing committed.
- [ ] `tsc --noEmit` clean, `eslint .` no new errors (0 `rules-of-hooks`), `npm run build` completes.

## Manual verification (against local stack, bypass-auth mode; `docs/deployment/DOCKER.md`)
- [ ] Build the DoR subtree in the tree editor; CSV-import a small subtree; both render nested.
- [ ] Create position types; edit a `default_role_key` → "review holders" prompt appears and does **not** change existing officers.
- [ ] Invite an officer via tree → "SDE, Jhapa Division Office" in one flow; roster/chip/timeline show the position title; override badge shows when role is changed.
- [ ] Confirm no visual/behavior regression on the existing settings tabs (org, officers, workflows, projects, platform).

## Done means
OC-05 checklist ticked in [`PROGRESS.md`](PROGRESS.md); new components in `components/settings/*` (god-file untouched beyond wiring); tsc/eslint/vitest/build green in CI; manual flows recorded; OC-06 findings that scoped into OC-05 all addressed or explicitly deferred with a note.
