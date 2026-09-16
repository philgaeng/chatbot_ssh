# `GRM-091` — `07 §5.1` describes an officer roster the UI does not build

**Deferred 2026-09-07**, while implementing `GRM-087`. Logged here and in
[`SPINE.md`](../../../SPINE.md) per the standing deferral rule.
**Kind:** `deviation` — question 2 resolves it: a live spec claims the behaviour, the code disagrees,
and **the spec is the side that is wrong**.

## What was measured

Reading [`07_officer_management_and_assignment.md`](../../../ticketing_system/07_officer_management_and_assignment.md)
§5.1 against the screen it describes:

| §5.1 says | The screen renders |
|---|---|
| Columns: Name · Email · Role · **Area covered** · Status · Actions | **Officer · Position · Office · Project / area · Status · ⋯** |
| One row per officer | **One row per active position** — a dual-hat officer appears twice (doc 16 §3.3) |
| Filters: Search, **role, project, package, location** | Search, and an **All / Standard / SEAH** track filter. The other four do not exist |

Source: [`OfficersDirectory.tsx`](../../../../channels/ticketing-ui/components/settings/officers-v2/OfficersDirectory.tsx),
whose own header cites a later design (`DESIGN §7.F` / frame-11) than §5.1 does.

## Why it was not fixed in passing

`GRM-087` is a search change. Resolving this is a **fork** — either §5.1 is rewritten to the built
roster, or the roster is changed to match §5.1 — and [07 §2.3](../../../engineering/07_work_items.md)
is explicit that a fork decided silently inside another item is how a spec acquires a change nobody
agreed to. The two candidate resolutions are not equivalent:

- **The spec moves.** Likely correct — the built roster came from a *later* design than §5.1, so §5.1
  is probably a superseded target rather than an unmet requirement. Cheap. Needs someone to confirm
  the position-per-row model is intended, which is a product question.
- **The code moves.** Only if "Role" and "Area covered" as *named columns* are a real requirement —
  they may be, for an ADB reviewer reading a screenshot.

⚠ **Do not treat `GRM-088` as the fix.** It builds the structured filters §5.1 promises, which closes
one of the three rows above and leaves the columns and the row model untouched.

## Definition of done

- The fork is decided by the owner of this screen, and recorded — a [`DECISIONS.md`](../../../DECISIONS.md)
  entry if the roster model itself is the thing being settled.
- §5.1 and the screen agree, whichever side moved.
- The honesty marker added to §5.1 on 2026-09-07 is removed, because it is no longer true.

## Interim state

§5.1 carries a dated marker naming exactly which of its paragraphs are as-built (the search block,
`GRM-087`) and which are not (everything above it). *An honest marker is not a fix, and this item
stays open until the marker can be deleted.*
