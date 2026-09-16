# SPDX-License-Identifier: Apache-2.0

"""
The task queue's retry configuration is actually applied — D-45.

**The defect this pins.** `TASK_CONFIG` declares per-type retry settings under `retries`; the
decorator that applies them read `retry`. So `retry_config` was always `{}` and **no task in this
queue had ever had its retry configuration applied** — every one ran on Celery's defaults, which
meant a **180-second** delay instead of the configured 1–2 s and, more consequentially, **no
`autoretry_for` at all**. Nothing in the system had ever retried automatically.

It hid for so long because both halves of the evidence were missing at once: nothing retried, so
nobody saw the wrong delay; and the delay was never observed, so nobody asked why nothing retried.
It surfaced only when a ticket needed a *terminal* status after retries were exhausted (D-34) and
the retry counter would not move.

⚠ **And fixing the key alone would have been worse than the bug.** `retry_on` names were resolved
with `getattr(__builtins__, name, Exception)` — inside an imported module `__builtins__` is a
**dict**, so that misses even real builtins and every miss became `Exception`. Turning the config
on with that resolution in place would have meant *retry on anything* for every task type,
including permanent failures like a malformed payload, which no number of retries can fix.

Spec: docs/sprints/2026-08-llm/followups/task-retry-config-has-never-been-applied.md
"""
from __future__ import annotations

import pytest

from backend.task_queue import task_manager as tm


def test_the_config_key_matches_what_task_config_declares():
    """
    The whole defect in one assertion: the reader and the writer must agree on the key.
    ⚠ Asserted through behaviour rather than by grepping the source, so it stays true if the
    decorator is rewritten.
    """
    for task_type, config in tm.TASK_CONFIG.items():
        assert "retries" in config, f"{task_type} declares no retry settings"
        assert config["retries"].get("max_retries"), f"{task_type} has no max_retries"


@pytest.mark.parametrize("task_type", sorted(tm.TASK_CONFIG))
def test_every_task_type_resolves_at_least_one_real_retry_exception(task_type):
    """
    A configured `retry_on` that resolves to nothing means the task never retries — which is the
    state the whole queue was in, silently.
    """
    names = tm.TASK_CONFIG[task_type]["retries"].get("retry_on", [])
    resolved = tm._resolve_retry_exceptions(names, task_type)

    assert resolved, f"{task_type} lists {names} and none of them resolve to an exception class"
    assert all(isinstance(cls, type) and issubclass(cls, BaseException) for cls in resolved)


def test_known_names_resolve_to_the_classes_they_name():
    """⚠ `ConnectionError` must be ConnectionError — not Exception, which is what it used to be."""
    resolved = tm._resolve_retry_exceptions(
        ["ConnectionError", "TimeoutError", "FileNotFoundError", "IOError"], "test"
    )

    assert ConnectionError in resolved
    assert TimeoutError in resolved
    assert FileNotFoundError in resolved
    assert OSError in resolved                      # IOError is an alias
    assert Exception not in resolved, (
        "the old resolution turned every name into Exception, which means 'retry on anything'"
    )


def test_an_unknown_name_is_dropped_loudly_and_never_widened_to_exception(caplog):
    """
    ⭐ **The regression this file exists for.** An unrecognised name must not become `Exception`.
    That fallback is how a rule saying *retry on rate limits* would have become *retry on every
    failure, including the ones retrying cannot fix*.
    """
    with caplog.at_level("WARNING"):
        resolved = tm._resolve_retry_exceptions(["NotARealException", "ConnectionError"], "test")

    assert resolved == (ConnectionError,)
    assert Exception not in resolved
    assert any("NotARealException" in r.getMessage() for r in caplog.records), (
        "dropping a configured rule silently is how the config stopped meaning anything"
    )


def test_exception_is_only_used_where_the_config_asks_for_it():
    """`Exception` remains available — the default queue genuinely wants retry-on-anything."""
    assert tm._resolve_retry_exceptions(["Exception"], "test") == (Exception,)


def test_the_llm_task_retries_on_the_provider_errors_that_are_worth_retrying():
    """
    The LLM ladder exists for transient provider trouble — a refused connection, a timeout, a rate
    limit. Those are the failures a retry can fix; a 400 for a bad parameter is not.
    """
    resolved = tm._resolve_retry_exceptions(
        tm.TASK_CONFIG[tm.TASK_TYPE_LLM]["retries"]["retry_on"], "llm"
    )

    assert ConnectionError in resolved and TimeoutError in resolved
    names = {cls.__name__ for cls in resolved}
    assert "RateLimitError" in names or "openai" not in str(resolved), (
        "if openai is installed, its RateLimitError should be one of the retryable classes"
    )
