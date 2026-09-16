# Follow-up — 112 backticked paths in `docs/` point at files that do not exist

> **Raised:** 2026-08-19, while widening the `docs-links` CI gate after `CLAUDE.md` was found
> pointing at a file renamed months earlier.
> **Logged as deviation D-48** in [`../PROGRESS.md`](../PROGRESS.md).
> **Status:** 🔵 open · **Size:** M — 112 references, 39 distinct targets, and each needs a
> judgement, not a rewrite rule.
> **Not gated,** deliberately. See §Why the gate stops at the root files.

---

## The measurement

`docs/` (excluding `archive/`), counting only backticked paths into a real source tree and
skipping `<placeholder>` forms:

```
1362 backticked paths ·  112 broken ·  39 distinct missing targets
```

| Kind of target | Broken refs |
|---|---|
| Source `.py` — renamed, split or deleted | 66 |
| `docs/` — a planned spec, or one that moved | 39 |
| Other source (`.sh`, `.ts`, …) | 7 |

The worst single target is **`ticketing/api/routers/tickets.py` — 22 references** to a module that
was split into `ticketing/api/routers/tickets/` (a package) and never chased through the prose.
Next are `backend/api/routers/voice_grievance.py` and `backend/api/routers/gsheet.py` at 8 each.

Densest documents: `docs/ticketing_system/agents/officer_sms_project_messaging.md` and
`docs/sprints/2026-07_schema_and_legacy_cleanup/AUDIT_FINDINGS.md`, 8 apiece.

## Why the gate stops at the root files

The widened `docs-links` job checks backticked paths in the **root** `*.md` only. That is not
squeamishness about the number — it is that **a backticked path in prose does not always mean "go
read this."**

Three legitimate reasons a document names a file that is not there:

* **A post-mortem names what it just deleted.** `followups/a-tracked-file-is-rewritten-on-import.md`
  says `backend/scripts/task_queue/config.sh` five times, in the past tense, explaining why it is
  gone. Every one would be flagged. Every flag would be wrong.
* **A spec names what it proposes to create.** `docs/dpg/model-benchmarks.md` (×4) is a Sprint 2
  deliverable. The reference is a commitment, not a citation.
* **A migration guide names both sides of a rename**, and one side is meant to be absent.

Markdown links carry that distinction by themselves — nobody writes a markdown link to a file they
just deleted — which is why the **link** check runs everywhere and is safe. Root-level files are
instructions rather than history, so the stricter check holds there and was verified at **0 broken**
before it was turned on.

## What fixing it would take

Not a sweep. Each of the 39 targets needs one of three answers:

1. **Re-point** — the file moved (`ticketing/api/routers/tickets.py` → the package). Mechanical once
   the new home is known; this is most of the 66.
2. **Rewrite the sentence** — the file is gone on purpose and the prose should say so in a form a
   checker will not read as a citation (name it in plain text, not backticks).
3. **Leave and annotate** — the file is a future deliverable. Needs a convention the checker can
   recognise; a `⏳` marker or a `planned:` prefix would do.

Only after (2) and (3) have a convention can the check be extended to `docs/` without either a red
build or a wall of ignore rules — and an ignore list is how a gate quietly stops gating.

## Why it is worth doing at all

The same reason `CLAUDE.md`'s two dead pointers were worth three lines of CI: **a reference that
does not resolve is worse than no reference.** It costs a reader the search before they conclude it
is gone, and it is silent — the document keeps looking authoritative. 22 of them point at the same
module, which means anyone following the ticket-API prose hits a dead path 22 times.
