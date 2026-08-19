# Follow-up — every Celery task's retry configuration has been ignored since it was written

> **Raised:** 2026-08-19 by [DPG-15b](../02-llm-agnostic-spec.md#dpg-15b), while making `LLM_failed`
> reachable. Found by running the retry ladder and reading the countdown Celery actually chose.
> **Logged as deviation D-45** in [`../PROGRESS.md`](../PROGRESS.md).
> **Status:** 🔵 open · **Size:** XS to fix, M to verify · **Blast radius:** every task in the queue

## The defect

`backend/task_queue/task_manager.py` declares per-type retry settings under the key **`retries`**:

```python
TASK_CONFIG = {
    TASK_TYPE_LLM: {'service': ..., 'queue': {...},
                    'retries': {'max_retries': 3, 'initial_delay': 2,
                                'backoff_factor': 2, 'max_delay': 30,
                                'retry_on': ['ConnectionError', 'TimeoutError', 'RateLimitError']}},
```

…and the decorator that applies them reads **`retry`**:

```python
retry_config = config.get('retry', {})      # always {}
...
if retry_config:                            # never true
    celery_options.update({'max_retries': ..., 'default_retry_delay': ..., 'autoretry_for': ...})
```

`retry_config` is therefore always empty and **none of it has ever been applied — for any task
type.** Every task in the queue runs on Celery's defaults instead:

| Setting | Intended | Actually in force |
|---|---|---|
| `max_retries` | 3 | 3 — by coincidence |
| `default_retry_delay` | 2 s, doubling to 30 s | **180 s** |
| `autoretry_for` | ConnectionError, TimeoutError, RateLimitError | **nothing** |

## Why it went unnoticed, and what it explains

`autoretry_for` being absent is the interesting half: **nothing has ever retried automatically**, so
the 180-second delay never had a chance to be noticed either. It also explains a puzzle in D-34 —
`_persist_classification_failed_if_final` waited for `request.retries` to reach `max_retries`, and
the number could never move, partly because the task returned instead of raising and partly because
no automatic retry was configured to catch it if it had.

Observed directly: `self.retry()` on the classification task reported *"Retry in 180s"*.

## What DPG-15b did about it

Nothing to the shared config — it passes an **explicit** `countdown=2 * (2 ** retries)` on the one
task it owns, giving 2/4/8 s. That matters for the design: a fast failure has to exhaust its ladder
inside the complainant's 30-second wait, and 3 × 180 s is nine minutes.

**Fixing the key was deliberately not done here.** Correcting `retries` → `retry` would switch on
`autoretry_for=(Exception,)` for **every** task type at once — file upload, messaging, database —
because `getattr(__builtins__, 'RateLimitError', Exception)` resolves unrecognised names to
`Exception`. That is a queue-wide behaviour change, and it belongs in a ticket that can test it.

## Definition of done

- [ ] Key corrected, **and** `retry_on` resolved to real exception classes rather than
      `getattr(__builtins__, …)`, which silently turns every unrecognised name into `Exception`
- [ ] Each task type's retry ladder chosen deliberately — the current numbers were never in force,
      so they are a proposal, not a regression baseline
- [ ] The interaction with tasks that already handle their own failures checked: several catch
      broadly and return a status dict, which `autoretry_for` would not see
- [ ] Verified by driving a failure per task type and reading the actual countdown

## Where it is tracked

`TODO.md` → 🔵 TECH DEBT · `PROGRESS.md` → **D-45**
