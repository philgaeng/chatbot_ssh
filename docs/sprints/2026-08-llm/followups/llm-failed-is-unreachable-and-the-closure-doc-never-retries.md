# Follow-up — two terminal states that no code path can reach

> **Raised:** 2026-08-18 by [DPG-15](../02-llm-agnostic-spec.md#dpg-15)'s degraded-mode audit, after
> the two findings it *did* fix (D-32, D-33).
> **Logged as deviations D-34 and D-36** in [`../PROGRESS.md`](../PROGRESS.md).
> **Status:** ✅ **D-34 CLOSED 2026-08-19 by [DPG-15b](../02-llm-agnostic-spec.md#dpg-15b)** — verified
> against the database: the row reaches `LLM_failed` and the poll stops in 0.19 s. ⚠ Two findings came
> out of fixing it: **D-45** (no task has ever had its retry config applied) and **D-46** (the first
> fix reproduced the bug, because `self.retry(exc=…)` re-raises the original exception rather than
> `MaxRetriesExceededError`). Originally scoped as:
> making `LLM_failed` reachable is part of moving the checkpoint, because a checkpoint that waits
> needs a terminal state to stop waiting on. **D-36 remains 🔵 open and unowned** — the ticketing closure
> document is a different path with a different owner, and it is now the last of the three.
> **Size:** S each, M to test properly

## D-34 — `LLM_failed` is written only after retries that never happen

`_persist_classification_failed_if_final` (`backend/task_queue/registered_tasks.py`) writes the
terminal `LLM_failed` status **only** when `self.request.retries >= max_retries`. That guard is
correct in intent — a transient outage should not be recorded as a permanent failure on the first
attempt. But the task's `except` block **returns a FAILED dict instead of re-raising**, so Celery's
`autoretry_for` never fires, `request.retries` never increments, and the condition is never true.

Measured (grievance `DPG15-ed2c9eb5`, endpoint on a dead port): the row stays `pending` forever.

**Why `pending` is not good enough**, even though it is honest:

* `load_grievance_for_classification` short-circuits on terminal statuses. With `pending` it polls
  the **full 20 seconds** before giving up — so every complainant during an outage waits out that
  deadline, which is also the deadline D-30 shows we are already brushing on a *good* day.
* A row stuck at `pending` is indistinguishable from one still in flight. Nothing sweeps it, and no
  officer view flags it.

**The fix is not one line**, which is why it is here rather than in the DPG-15 commit: re-raising
changes the task's terminal state from SUCCESS-with-a-FAILED-payload to Celery FAILURE, and the
frontend polls task status. That needs its own test pass on the live intake path.

### Definition of done
- [ ] A classification whose model call fails is retried (bounded, with backoff) and then lands on
      `LLM_failed`, verified against the database as the DPG-15 runs were
- [ ] The retrieve step short-circuits on that status instead of waiting 20 s
- [ ] Whatever the frontend does with a Celery FAILURE state is checked, not assumed
- [ ] The officer queue distinguishes "AI failed" from "AI classified" — `OFFICER_VALIDATION_REQUIRED`
      already contains both codes, so the data is there and only the presentation is missing

## D-36 — the closure document is never rebuilt after an LLM failure

`generate_resolved_case_summary` sets `generation_status = "llm_failed"` when the model returns
`None`, and returns normally. Nothing retries it (the retry is on the `except` path, and a `None`
return is not an exception), and nothing sweeps `llm_failed` rows.

The complainant **is** told their case is resolved — that notification comes from the resolve action,
not this task — but the closure document with the outcome narrative is never built, and the
`closure_public_url` link is never sent. From the complainant's side: "resolved", with nothing to
read about what was decided.

### Definition of done
- [ ] `llm_failed` closure documents are retried, or a scheduled sweep rebuilds them
- [ ] Or: the deterministic parts of the document are published without the LLM digests, with an
      honest note in place of the narrative — a closure page missing its AI summary is still a
      closure page, and this is a **complainant-facing** artefact
- [ ] Either way, the resolution notification and the closure link stop depending on a model call

## Why these are separate from what DPG-15 fixed

DPG-15 fixed the two failures that were **actively wrong**: a failed classification recorded as a
success (D-32), and a complainant's phone number erased by an outage (D-33). Both were single
guards with no blast radius beyond the enrichment.

These two are **absences** rather than errors: a state nothing reaches, and a rebuild nothing
triggers. Fixing either changes the retry topology of a live path, which is a different kind of
change and deserves its own ticket, its own tests, and its own dead-port run.

## Where they are tracked

`TODO.md` → 🔵 TECH DEBT · `PROGRESS.md` → **D-34**, **D-36** · audit table in the same file
