# Follow-up — the translation path raises `UnboundLocalError`, and the "fix" would leak PII

> **Raised:** 2026-08-18, by [DPG-10](../02-llm-agnostic-spec.md#dpg-10)'s characterization net —
> the test that pinned the failure contract found the contract was not the one the code has.
> **Logged as deviation D-29** in [`../PROGRESS.md`](../PROGRESS.md).
> **Status:** 🟡 **superseded 2026-08-18 — now owned by [DPG-19 §19.3](../02-llm-agnostic-spec.md#dpg-19)**,
> in this sprint. · **Size:** XS
>
> ⚠ **The reason for deferring it has been removed.** This document argued the fix must wait for
> Sprint 3, because binding `result` early makes a `ValueError` reachable whose message interpolates
> the whole grievance. The owner's answer: *"trim the grievance — we just need the first 3 words to
> easily find it."* With `grievance_id` plus three words, the message is bounded, the binding is
> safe, and both halves land together. The analysis below stands; its conclusion does not.

## What was found

`backend/services/LLM_services.py` → `translate_grievance_to_english_LLM`:

```python
try:
    response = client.chat.completions.create(...)      # ← if this raises …
    ...
    result = {}                                          # ← … `result` is never bound
    ...
except Exception as e:
    raise ValueError(f"Error translating grievance to English: {str(e)} - "
                     f"input_data: {input_data} - result: {result}")   # ← UnboundLocalError
```

Any failure **before** `result` is bound — a provider outage, a timeout, a bad model name, an
empty-object response, a missing `complainant_district` key — surfaces as
`UnboundLocalError: local variable 'result' referenced before assignment`, not the declared
`ValueError`. A caller catching `ValueError` does not catch it.

This is the same shape as **D-28** in `extract_contact_info` (`if not response:` in a handler that
runs before `response` is bound). Two instances, one module, both in `except` blocks that read a
variable the `try` had not reached yet. Neither was reachable by any test, because there were no
tests.

Pinned as-is by `tests/backend/test_llm_services.py::test_translate_grievance_raises_unbound_local_error_when_the_call_fails`.
The declared `ValueError` path is pinned separately — it is reachable, but only when the body is
malformed JSON.

## Why it is not fixed in Sprint 1

**Because the obvious one-line fix makes a PII leak more likely, not less.**

Binding `result = {}` before the `try` turns the common failure — the provider being unreachable —
into the declared `ValueError`, whose message interpolates **`input_data` in full**: the grievance
narrative, its summary, the district and province. That message is then logged by the Celery task
layer. Today the same failure produces a message naming a variable and nothing else.

So the correct fix is two changes, not one:

1. bind `result` (and drop `input_data` from the message), and
2. keep the exception message free of narrative text — which is exactly **T-34-b** in
   [`04-pii-redaction-spec.md`](../04-pii-redaction-spec.md#dpg-34): *"the translation error path does
   not interpolate `grievance_description` into its exception message"*.

Doing (1) without (2) is a privacy regression dressed as a bug fix. Sprint 1's own convention —
*no behaviour change outside the ticket's scope* — points the same way, and DPG-14's list does not
include this site.

## Definition of done

- [ ] `result` is bound before the `try`, so the declared `ValueError` is what callers actually get
- [ ] The exception message names the grievance **id** and the exception, and interpolates neither
      `input_data` nor any narrative field (T-34-b)
- [ ] `test_translate_grievance_raises_unbound_local_error_when_the_call_fails` is rewritten to assert
      the `ValueError` contract, and a new test asserts the message contains no narrative text
- [ ] The same sweep is run for the remaining `except` blocks in the module — this is the second
      instance of one pattern, which is enough to suspect a third

## Where it is tracked

`TODO.md` → 🔵 TECH DEBT · `PROGRESS.md` → **D-29** · Sprint 3 → **DPG-34 / T-34-b**
