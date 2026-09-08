# `GRM-085` — the Settings tab strip does not open on the tab it opens on

**Origin:** user request (client, 2026-09-07) · **Lane:** `settings-ui` · **Reported:** 2026-09-07
**Design:** [`DESIGN-settings-findability.md`](DESIGN-settings-findability.md) §2.1

## Kind

**`feature`** — question 1 resolves it: no live spec claims a tab *ordering rule*.
[`10_settings_overview.md`](../../ticketing_system/10_settings_overview.md) enumerates the tabs in
three tables, but describes what each one is for, never that the order is deliberate.

⚠ **The alternative reading, recorded because §2.4 makes classification cheap and revisable:** this
has a defect inside it (see Notes). It is still filed as a feature, because the fix the owner asked
for is a new arrangement, not a restoration of one a spec already promised.

## Profile

| ✓ | Question | Fires |
|---|---|---|
| ✔ | Changes user-visible behaviour | `G-PRODUCT` · `G-SPEC` · `G-VERIFY` |
| ✔ | A UI surface changes shape | `G-DESIGN` — navigation IA. **Discharged by DESIGN §2.1** |
| ✗ | Schema changes | — |
| ✗ | PII · auth · SEAH · complainant channel · new egress | — |
| ✗ | API or event shape changes | — |
| ✔ | Deployed | `G-RELEASE` |
| ■ | always | `G-TEST` |

> **profile:** `UI feature` · **gates:** PRODUCT · DESIGN · SPEC · TEST · VERIFY · RELEASE
> **model:** Opus · **size:** XS

## The change

`MAIN_TABS` becomes: **Projects & packages · Organizations & officers · Workflows · Settings.**

## Files it may touch

- [`app/settings/page.tsx`](../../../channels/ticketing-ui/app/settings/page.tsx#L51) — the `MAIN_TABS` array. **Reorder only**; do not touch `MainTab`'s union order, which is unrelated to render order.
- [`10_settings_overview.md`](../../ticketing_system/10_settings_overview.md) — three tables list the tabs in the old order (§ rows at lines ~18, ~31, ~57). **G-SPEC: same commit, header bumped.**

## Gates — evidence

- **G-TEST** — ✅ **verified 2026-09-07: nothing breaks.** [`settings-sections.spec.ts`](../../../channels/ticketing-ui/e2e/flows/settings-sections.spec.ts) selects tabs **by accessible name** (`getByRole("button", { name: tab, exact: true })`), never by index, so a reorder is invisible to it. Add one assertion pinning the strip's order, since after this item the order is a decision rather than an accident.
- **G-VERIFY** — the existing settings specs already screenshot every section.
- **G-DESIGN** — DESIGN §2.1 carries the argument, including why outcome-first order is right *despite* inverting the dependency order.

## Non-goals

No tab renamed (Q-05: "Workshop" was a typo for Workflows), none added or removed, and the sub-tab
strips are untouched.

## Register line

```
| `GRM-085` — the Settings tab strip does not open on the tab it opens on | feature | UI feature | `ready` | XS | settings-ui | … |
```

## Notes

⭐ **The reorder makes the strip agree with behaviour that already ships.** The page defaults to
`useState<MainTab>("projects")`
([`page.tsx:134`](../../../channels/ticketing-ui/app/settings/page.tsx#L134)) — so opening
`/settings` today lands on **Projects & packages** while the strip's **first** tab reads
Organizations & officers, leaving the active underline in third position on arrival. The client asked
for a preference and named a real inconsistency; the fix is one line either way, and moving the tab
is the one that matches what the default already asserts is most important.
