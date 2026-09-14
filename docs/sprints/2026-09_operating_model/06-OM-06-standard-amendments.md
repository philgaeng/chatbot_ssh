# OM-06 — Amend the standards that already own their concern

> **kind:** feature (process) · **profile:** chore+SPEC · **size:** M · **depends on:** OM-01
> Independent of the register — can run in parallel.

## Context

Only the work-item model is genuinely new. Everything else discussed belongs to a standard that already
owns that concern. Putting it all in one new document would create a second place where the design gate
is defined — making fragmentation worse while trying to fix it.

## Scope — four amendments, each in its owner

| Amendment | Goes in | What |
|---|---|---|
| **Reference packs** | `00_engineering_index.md` | 5–6 named read-sets, each **a folder plus one entry point**, never a file list — that is what survives a growing tree. Plus an 11th rule pointing at `07`. |
| **The design gate** | `05_frontend.md` | brief → IA → wireframe → direction → state/responsive contract → **implementation contract frozen before build**. Followed once by instinct (the settings redesign); write it down. Say what the two `ui/*.html` mockups are and what they bind. |
| **The verification ladder** | `06_documentation_lifecycle.md` §4 | `planned → implemented → tested → applied locally → deployed → verified in production`, beside the existing document honesty markers. §4 currently covers documents only, not items. |
| **Session close + capabilities** | `AGENTS.md` | the six-line handoff block (result · completed · next item · read first · start with), and an inventory of the tooling that exists — `doc_headers.py`, `test_doc_code_refs.py`, `security-preflight.sh`, `restore_drill.sh`, and the Playwright harness once QA-04 lands. |

## Not in scope

Rewriting the standards. Each amendment is a section, not a revision.

## Acceptance

- [x] Each amendment lands in the standard that owns the concern — **no duplication into `07`**. `07` gained no new content; its §11 rows 5 and 6 now point at where each landed
- [x] Every touched file's `**Last updated:**` bumped in the same commit — `doc_headers.py --check` reports the same 11 pre-existing violations as before this ticket, and none of them is one of these commits
- [x] `00_engineering_index.md` lists `07` in the standards table (already did) **and now in the reading order**, between `SPINE.md` and the layer standard — before you start, not at merge
- [x] Reference packs name folders and entry points, not file lists — six packs, each a folder + one entry point + the code it governs. ⭐ The **Sensitive path** pack is marked as the one that changes *how* the work is done, not just what you read: entering it means `+SENSITIVE`, which means Opus
- [x] `07_work_items.md` §11 rows 5 and 6 closed — the standard moved from "partly in force" to "mostly in force"; only rows 2 (OM-05) and 8 (OM-07) remain

## Done 2026-09-06

**A fifth thing was amended that the ticket did not list.** `AGENTS.md` gained the session-close block
*and* a **"What already exists"** inventory of the twelve enforcement tools already in this repository
— every row verified to exist before it was written, per rule 9. The inventory is the half that earns
its keep: the failure it prevents is an agent writing a second checker for a rule that already has one,
which is how a rule ends up with two homes that disagree.

**What was deliberately not done:** none of the four standards was rewritten (§ *Not in scope*). Each
amendment is a section added to the standard that already owns the concern.

⚠ **`ui/04_projects_packages_redesign.html` is stale and is now marked stale where it is cited**
(`05_frontend.md` §9a), rather than only in the register where a frontend agent would not look.
