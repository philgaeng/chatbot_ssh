# `GRM-086` — the organization tree has no way to find anything in it

**Origin:** user request (client, 2026-09-07) · **Lane:** `settings-ui` · **Reported:** 2026-09-07
**Design:** [`DESIGN-settings-findability.md`](DESIGN-settings-findability.md) §2.2, §5, §6

## Kind

**`feature`** — question 1: no live spec claims this behaviour. The control does not exist:
[`OrgTree.tsx`](../../../channels/ticketing-ui/components/settings/org/OrgTree.tsx) has no search
state, no filter state, and passes no `q`.

## Profile

| ✓ | Question | Fires |
|---|---|---|
| ✔ | Changes user-visible behaviour | `G-PRODUCT` · `G-SPEC` · `G-VERIFY` |
| ✔ | A UI surface changes shape | `G-DESIGN` — **fully. A filter bar over a tree exists on no shipped screen** |
| ✗ | Schema changes | — |
| ✗ | PII · auth · SEAH · complainant channel · new egress | — |
| ✗ | API or event shape changes | ⚠ **assumed yes at first pass; verified no** — see below |
| ✔ | Deployed | `G-RELEASE` |
| ■ | always | `G-TEST` |

> **profile:** `UI feature` −`G-CONTRACT` · **gates:** PRODUCT · DESIGN · SPEC · TEST · VERIFY · RELEASE
> **model:** Opus · **size:** M

⭐ **`G-CONTRACT` was retired at intake, and the reason matters more than the gate.** It was assumed
to fire — type and area filters look like query parameters. Reading
[`locations.py:362`](../../../ticketing/api/routers/locations.py#L362) says otherwise: the existing
server-side `q` returns a **flat filtered set**, so an organization whose parent does not match comes
back **without its parent** and the forest cannot be rebuilt. Server-side search is structurally
incapable of the ancestor rule this item is built on. Meanwhile `OrgTree` already fetches the whole
forest in one call with `org_category`, `unit_type` and `territory_location_code` on every node.
**Client-side is both less work and the only correct option.** No endpoint changes.

## The change

1. **Search box** over the tree. Matches organization name, Nepali name, and id. A match keeps its
   **ancestor chain visible** as de-emphasised context — matches are counted, ancestors are not.
2. **Two filters: Type and Area.** Type from `org_category` / `unit_type`; Area from
   `territory_location_code`, with the dropdown's level labels read from `location_level_defs`
   (`level_name_en`), never hardcoded, so the control survives outside Nepal.
3. **No parent-organization filter** (Q-02) — the tree is the parent relationship.

## Files it may touch

- [`components/settings/org/OrgTree.tsx`](../../../channels/ticketing-ui/components/settings/org/OrgTree.tsx) — filter state, match + ancestor computation
- [`components/settings/org/OrgTreeNode.tsx`](../../../channels/ticketing-ui/components/settings/org/OrgTreeNode.tsx) — the de-emphasised ancestor rendering
- [`components/settings/org/orgVocab.ts`](../../../channels/ticketing-ui/components/settings/org/orgVocab.ts) — `buildForest` / `groupRoots` gain a filtered variant
- **New:** `docs/ticketing_system/ui/07_org_directory_filters.html` — the wireframe (below)
- [`10_settings_overview.md`](../../ticketing_system/10_settings_overview.md) §3 — G-SPEC

## Gates — evidence

- **G-DESIGN** — ⚠ **the one item in this lane that owes a committed `.html` wireframe** before
  build, per [`05_frontend`](../../engineering/05_frontend.md) rule 9a.1, because it adds a surface
  no shipped screen has. DESIGN §3 says why the other five do not.
  It binds **IA and layout only** (rule 9a.2): not colour, not copy, not component structure.
- **G-TEST** — component tests for match + ancestor computation (a match at depth 3 keeps all three
  ancestors; an ancestor that is *itself* a match is counted once). Plus the empty-vs-no-match
  distinction, which is a rendering decision and belongs in an e2e assertion.
- **G-VERIFY** — extends [`settings-sections.spec.ts`](../../../channels/ticketing-ui/e2e/flows/settings-sections.spec.ts).
- **G-PRODUCT** — DESIGN + Q-02.

## Non-goals

No server-side search or pagination; the existing `q` param is left in place for other callers
(DESIGN §6). No change to the two-group split (government line vs independent roots). No change to
what an organization is.

## Register line

```
| `GRM-086` — the organization tree has no way to find anything in it | feature | UI feature −CONTRACT | `ready` | M | settings-ui | … |
```

## Notes

The tree currently renders whole, always. That is fine at today's size and is exactly why the fix is
client-side — but it is also the reason this item should not grow a pagination scope: the day the
forest is too big to hold in memory, the answer is a different screen, not a filter bolted onto this one.
