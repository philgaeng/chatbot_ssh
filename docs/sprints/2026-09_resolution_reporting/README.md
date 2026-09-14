# Lane — Resolution reporting (September 2026)

**Audience:** internal — excluded from the public repository (lifecycle §10.4).
**Lane id:** `resolution-reporting` · **Origin:** user request (client, 2026-09-15).

> **Status:** 📋 **Specified, not started.** Tier 3 per [`engineering/06_documentation_lifecycle.md`](../../engineering/06_documentation_lifecycle.md) §1.
> **Read first:** [`DESIGN-resolution-reporting.md`](DESIGN-resolution-reporting.md).
> ✅ **Q-01 … Q-04 answered by the owner 2026-09-15** ([`QUESTIONS.md`](QUESTIONS.md)).
> ⏳ **Q-05 blocks the start of `GRM-118`. Q-06 blocks the merge of `GRM-116`.** Q-07 blocks nothing.

## Goal, in one sentence

**Managers can see from the Excel what was done about each case and which office did it, without
the file holding anything that names a person.**

## Why this and not what was asked

The client asked for the whole case summarised in the Excel. That would put free-text narrative —
names included — into a file that is emailed and forwarded outside every access control we have.
What managers need from it is two answers per case, and both can be picked from lists instead of
typed. DESIGN §1 has the full reasoning; use it when explaining the decision to the client.

## Items

| # | Item | Kind | Profile | Size | State |
|---|---|---|---|---|---|
| [`GRM-116`](01-GRM-116-resolution-actions-per-workflow.md) | Every case resolves from the same five outcomes, whatever its workflow | feature | UI feature +DATA +CONTRACT +SENSITIVE | M | `ready` · merge waits on Q-06 |
| [`GRM-117`](02-GRM-117-resolution-actor.md) | A resolved case does not record which office took the action | feature | UI feature +CONTRACT +SENSITIVE | M | `ready` |
| [`GRM-118`](03-GRM-118-report-resolution-columns.md) | The Excel says how a case was classified, not what was done or by whom | feature | Backend feature +CONTRACT +SENSITIVE | S | `blocked` — Q-05, `GRM-116`, `GRM-117` |

**Order:** `GRM-116`, then `GRM-117` (same form, same `RESOLVE` branch — sequential avoids a
conflict, not a dependency), then `GRM-118`. One PR per item.

## Opened on the way through

| Id | Kind | What |
|---|---|---|
| [`GRM-119`](followups/resolution-list-editor.md) | debt | A workflow's resolution actions can only be changed by a migration — the Settings editor was deferred (Q-04) |

## Three things the spec found in the code

1. ⭐ **The resolution list already exists twice** — in Python and hand-copied in the UI
   (`lib/resolution.ts`). `GRM-116` deletes the UI copy rather than making it per-workflow too.
2. ⭐ **No project on the dev DB binds a road-hazard workflow**, so today a road-hazard report
   resolves in the general workflow. Per-workflow lists make that visible; they do not paper over
   it. A project that wants road-works actions needs a road-hazard workflow bound.
3. ⭐ **The key `resolution_category` is persisted in three places** that a rename would break
   silently — append-only events, saved quarterly templates, and the action API. Hence Q-05.

## Live specs this lane will amend

`08_ticket_resolution_and_case_summary.md` · `09_reports_and_report_builder.md` ·
`12_workflows_configuration.md` · `04_ticketing_schema.md` — each by the item that makes the change
true, in the same PR.
