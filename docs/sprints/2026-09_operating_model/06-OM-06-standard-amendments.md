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

- [ ] Each amendment lands in the standard that owns the concern — **no duplication into `07`**
- [ ] Every touched file's `**Last updated:**` bumped in the same commit (`doc_headers.py --check`)
- [ ] `00_engineering_index.md` lists `07` in the standards table and the reading order
- [ ] Reference packs name folders and entry points, not file lists
- [ ] `07_work_items.md` §11 rows 5 and 6 updated
