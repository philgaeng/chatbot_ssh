# Lane — Settings findability & inline creation (September 2026)

**Audience:** internal — excluded from the public repository (lifecycle §10.4).
**Lane id:** `settings-ui` · **Origin:** user request (client feedback, 2026-09-07).

> **Status:** 📋 **Proposed — not approved.** Tier 3 per [`engineering/06_documentation_lifecycle.md`](../../engineering/06_documentation_lifecycle.md) §1.
> **Read first:** [`DESIGN-settings-findability.md`](DESIGN-settings-findability.md).
> ✅ **Q-01 … Q-05 answered by the owner 2026-09-07** ([`QUESTIONS.md`](QUESTIONS.md)); every answer is
> folded into the item that needs it, so an agent works from its spec alone.
> **Q-06 is open and blocks nothing** — whether `GRM-088` waits for `GRM-086`'s shipped component or
> only its frozen contract. The register takes the conservative reading meanwhile.

## Goal, in one sentence

**Find things, and add things, without leaving the screen you are on.**

## Items

| # | Item | Kind | Profile | Size | State |
|---|---|---|---|---|---|
| [`GRM-085`](01-GRM-085-settings-tab-order.md) | The tab strip does not open on the tab it opens on | feature | UI feature | XS | `ready` |
| [`GRM-086`](02-GRM-086-organizations-search-and-filters.md) | The organization tree has no way to find anything in it | feature | UI feature −CONTRACT | M | `ready` |
| [`GRM-087`](03-GRM-087-officer-search-fields.md) | Officer search ignores the two columns admins scan by | feature | UI feature −DESIGN | XS | `ready` |
| [`GRM-088`](04-GRM-088-officer-filters.md) | The officer directory has no structured filters | feature | UI feature | M | `blocked` |
| [`GRM-089`](05-GRM-089-create-organization-from-project.md) | The project's Organizations pane can only pick an org that exists | feature | UI feature | S | `ready` |
| [`GRM-090`](06-GRM-090-staffing-add-officer-and-collapse.md) | Staffing shows every level expanded, so the blockers are below the fold | feature | UI feature | S | `ready` |

**Suggested order:** `GRM-085` and `GRM-087` first — both XS, both independent, both shippable the
day the lane is approved. Then `GRM-089` and `GRM-090` (independent of each other, and of the search
work). Then `GRM-086`, which owes a wireframe. `GRM-088` last, if at all.

## Three things this lane found before writing any code

1. ⭐ **`G-CONTRACT` does not fire, and the obvious implementation is wrong.** Adding type/area
   filters to `GET /api/v1/organizations` looks right and is not: its existing `q` returns a flat set,
   so a match whose parent does not match comes back **without its parent** and the forest cannot be
   rebuilt. Server-side search cannot express the ancestor rule. `GRM-086` §Profile.
2. ⭐ **The tab reorder fixes an inconsistency nobody filed.** `/settings` already defaults to
   `projects` while the strip's first tab is Organizations & officers. `GRM-085` §Notes.
3. ⭐ **`GRM-064` is closed by a decision, not by work.** The stale `ui/04` mockup is marked
   superseded and the shipped screens become the baseline (Q-04).

## Closes

- **`GRM-064`** — the `ui/04` mockup is stale. Resolved by Q-04.

## Depends on nothing; two traps to know about

- **`GRM-081`** — a fresh seed derives officer display names from the email. **Key specs on the
  email.** Fresh roster **17** officers, this dev box **67** — never assert a count.
- **`GRM-080`** — a cold stack renders as `super_admin` for ~10 s. A settings spec asserting on the
  admin gate races it.
