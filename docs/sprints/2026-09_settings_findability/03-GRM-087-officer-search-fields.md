# `GRM-087` — officer search ignores the two columns admins scan by

**Origin:** user request (client, 2026-09-07) · **Lane:** `settings-ui` · **Reported:** 2026-09-07
**Design:** [`DESIGN-settings-findability.md`](DESIGN-settings-findability.md) §1, §5

## Kind

**`feature`** — question 1: no live spec claims searchable office or project/area.

## Profile

| ✓ | Question | Fires |
|---|---|---|
| ✔ | Changes user-visible behaviour | `G-PRODUCT` · `G-SPEC` · `G-VERIFY` |
| ✗ | A UI surface changes shape | — **no new control; the search box already exists** |
| ✗ | Schema changes | — |
| ✗ | PII · auth · SEAH · complainant channel · new egress | — |
| ✗ | API or event shape changes | — |
| ✔ | Deployed | `G-RELEASE` |
| ■ | always | `G-TEST` |

> **profile:** `UI feature` −`G-DESIGN` · **gates:** PRODUCT · SPEC · TEST · VERIFY · RELEASE
> **model:** Opus · **size:** XS

## The change

The search haystack is `[display_name, email, ...positions]`
([`OfficersDirectory.tsx:156`](../../../channels/ticketing-ui/components/settings/officers-v2/OfficersDirectory.tsx#L156)).
Add: **organization name** (and its Nepali name), **project name and code**, and **location scope
names** — the fields already rendered in the Office and Project / area columns.

⭐ **Verified 2026-09-07: the data is already in hand.** The same component computes all of it
client-side for `projectAreaCell` — `orgById`, `o.project_codes` → `projectByCode`, and
`o.scopes[].location_code` → `prettyLocation`. This is a haystack edit, not a data-fetching change.

## Files it may touch

- [`components/settings/officers-v2/OfficersDirectory.tsx`](../../../channels/ticketing-ui/components/settings/officers-v2/OfficersDirectory.tsx) — the `filteredOfficers` memo, and the placeholder string
- [`07_officer_management_and_assignment.md`](../../ticketing_system/07_officer_management_and_assignment.md) — G-SPEC

## Gates — evidence

- **G-TEST** — a spec that searches by organization name and by project code and gets the right
  officer. ⚠ **Key on the email, never the display name** (`GRM-081`): a fresh seed derives
  `l1-officer@grm.local` → `L1-Officer` where this dev box shows `Site Officer L1`.
- **G-VERIFY** — [`settings-officers.spec.ts`](../../../channels/ticketing-ui/e2e/flows/settings-officers.spec.ts) already drives search; extend it.
- **G-DESIGN** — does not fire. The control, its placement and its states are unchanged; only what it
  matches changes. Placeholder copy still goes through [`ui/05`](../../ticketing_system/ui/05_ui_copy_style.md).

## Non-goals

No new filter controls — those are `GRM-088`. No server-side search; the standing `TODO` in the
file header stays.

## Register line

```
| `GRM-087` — officer search ignores the two columns admins scan by | feature | UI feature −DESIGN | `ready` | XS | settings-ui | … |
```

## Notes

The Standard / SEAH filter composes with search today and must keep doing so — widening the haystack
must not change which officers the track filter admits.
