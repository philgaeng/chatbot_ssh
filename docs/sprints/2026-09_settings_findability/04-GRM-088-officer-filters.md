# `GRM-088` — the officer directory has no structured filters

**Origin:** user request (client, 2026-09-07) · **Lane:** `settings-ui` · **Reported:** 2026-09-07
**Design:** [`DESIGN-settings-findability.md`](DESIGN-settings-findability.md) §2.2, §4, §5

## Kind

**`feature`** — question 1: no live spec claims it.

## Profile

| ✓ | Question | Fires |
|---|---|---|
| ✔ | Changes user-visible behaviour | `G-PRODUCT` · `G-SPEC` · `G-VERIFY` |
| ✔ | A UI surface changes shape | `G-DESIGN` — **shares `GRM-086`'s design; produces no second wireframe** |
| ✗ | Schema changes | — |
| ✗ | PII · auth · SEAH · complainant channel · new egress | — |
| ✗ | API or event shape changes | — |
| ✔ | Deployed | `G-RELEASE` |
| ■ | always | `G-TEST` |

> **profile:** `UI feature` · **gates:** PRODUCT · DESIGN · SPEC · TEST · VERIFY · RELEASE
> **model:** Opus · **size:** M
> **state:** `blocked` — **blocker: `GRM-086`. Unblock condition: `GRM-086` merged**, so this reuses
> the shipped filter component rather than a second copy of it. See Q-06 — this is a sequencing
> preference, reversible, not a dependency.

## The change

Filters over the roster, using the component `GRM-086` establishes: **Organization · Project ·
Area**, composed with the existing All / Standard / SEAH track filter, which is untouched.

## Files it may touch

- [`components/settings/officers-v2/OfficersDirectory.tsx`](../../../channels/ticketing-ui/components/settings/officers-v2/OfficersDirectory.tsx)
- the shared filter component from `GRM-086`
- [`07_officer_management_and_assignment.md`](../../ticketing_system/07_officer_management_and_assignment.md) — G-SPEC

## Gates — evidence

- **G-DESIGN** — no new wireframe: the control is `GRM-086`'s, reused. What this item owes is the
  **frozen contract** for filter state shape, and the composition rule with the track filter.
- **G-TEST** — composition is the risk: two filters plus a search term must intersect, not union.
  ⚠ Key specs on the email (`GRM-081`), and do not assert a roster count — fresh is **17**, this dev
  box is **67**.
- **G-VERIFY** — extends the officers spec.

## Non-goals

No server-side filtering or pagination. No change to SEAH visibility rules.

## Register line

```
| `GRM-088` — the officer directory has no structured filters | feature | UI feature | `blocked` | M | settings-ui | … |
```

## Notes

Q-01 answered "both, in that order" precisely so this item can be **dropped or deferred without loss**
if `GRM-087` turns out to be enough at this scale. Filters earn their place at 500 officers; there are 57.
