# Agent runbook — OC-05: Portal org-chart & positions UI

**Branch:** `orgchart/oc-05-portal` off `integration/seah-claude` · **Model:** Opus (high effort — pre-fill/matrix correctness against the permission model; the pure tree/table rendering alone is Sonnet-eligible if split out) · **Spec:** [`../04-portal-org-chart-ui-spec.md`](../04-portal-org-chart-ui-spec.md) · Read [`README.md`](README.md) common rules first, then the **OC-06 evaluation** ([`../05-admin-setup-ux-evaluation.md`](../05-admin-setup-ux-evaluation.md) output). All work in `channels/ticketing-ui/`.

⚠️ **Start after OC-01..04 land AND after hardening HR-06.** HR-06 owns a hooks fix at ~`app/settings/page.tsx:4590` and is told to touch nothing else — do not fight it in the god-file.

## Mission

Build the org-tree editor, the position-type/matrix editor, and the invite pre-fill flow (tree → position → pre-filled editable fields) as **new `components/settings/*` components**, and surface position titles across the officer/ticket UI — without growing the 4,717-line settings page beyond ~5 lines of tab wiring.

## Steps

1. **Baseline & ground:** `npm ci`, `npx tsc --noEmit` (clean), `npx eslint .` (0 `rules-of-hooks` after HR-06). Read the OC-06 evaluation and fold its OC-05-owned findings into your task list. Read the existing `components/settings/*` (12 components) — `OrganizationsTab.tsx`, `OrgCreateModal.tsx`, `OfficersTab.tsx`, `OfficerModals.tsx`, `OfficerJurisdictionForm.tsx` — and the sub-tab render block `app/settings/page.tsx:4640-4712`.
2. **`OrgTreeTab.tsx`** (new): nested tree view + create/edit unit modal (`unit_type`, parent, territory, `display_name` + `display_name_ne`) + CSV import panel (upload → server-validate → show row errors → confirm). Reuse `OrganizationsTab`/`OrgCreateModal` idioms and the design system (`docs/ticketing_system/ui/02_design_system.md` — icons, palette, no emoji).
3. **`PositionTypesTab.tsx`** (new): matrix editor table; create/edit modal validating against roles + unit types (server is source of truth — surface 400s inline per the HR-06 error pattern); editing `default_role_key` shows the non-blocking **"review holders"** notice (doc 16 §4 — it does not re-sync holders).
4. **Invite pre-fill** (doc 16 §5.2): in `OfficerModals.tsx`/`OfficerJurisdictionForm.tsx`, add org-unit tree picker → position select (filtered by the unit's `allowed_unit_types`) → role/org/scope **pre-fill, still editable**, with a "from position: …" provenance hint and the **override badge** when the chosen role ≠ matrix default. Saving carries the `position` selection to the OC-03 invite call.
5. **Display surfaces** (§5.1): position title + org unit on the officer roster, assignee chips, timeline actors, reports column — fall back to the role label when no position exists.
6. **`lib/api.ts`:** one typed `apiFetch` wrapper per OC-0x endpoint (org tree/import, position-types, users positions, supervisor), matching the file's section-header conventions. **Keep `apiFetch`'s signature stable** (153 callers).
7. **Tab wiring:** the *only* edit to `app/settings/page.tsx` — add the new sub-tab(s) under `org_officers` (~5 lines). Rebase on HR-06 first; never edit near the ~4590 hooks region.
8. **Verify:** extract pure logic (`allowed_unit_types` filter, override-badge predicate, tree flatten/nest) and unit-test with vitest (the HR-06 seed); `tsc`/`eslint`(0 hooks)/`npm test`/`npm run build` green. Run the spec's manual flows on the local stack (`docs/deployment/DOCKER.md`, bypass-auth) and record in [`../PROGRESS.md`](../PROGRESS.md).

## Constraints

- **No inline additions to `app/settings/page.tsx`** beyond tab wiring — all UI in new `components/settings/*` files. No page split (Tier-3), no state-management library, no `apiFetch` signature change.
- Nepali (`display_name_ne`) rendered when present, never fabricated; absent → English fallback + mark for the translation sheet. No hardcoded Nepali in components.
- Match the design system; new tabs look native to the settings shell. Don't fix unrelated eslint findings — log them in PROGRESS deviations.

## Done means

OC-05 checklist ticked in [`../PROGRESS.md`](../PROGRESS.md); new components added, god-file untouched beyond wiring, landed after HR-06; tsc/eslint(0 hooks)/vitest/build green in CI; manual flows recorded; OC-06 findings scoped to OC-05 addressed or explicitly deferred with a note.
