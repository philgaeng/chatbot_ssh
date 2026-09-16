# SPDX-License-Identifier: Apache-2.0
"""
§31.4 — the model's OUTPUT is redacted before it is persisted, on both summary-producing prompts.

**Why an output pass exists at all, given the input is already redacted.** The `call_llm` chokepoint
(DPG-33) pseudonymises everything sent, so the model never receives a name it could echo. This pass
catches the case where **input redaction missed one** — and that is precisely where a prompt
instruction is least dependable, because a missed name reads to the model as ordinary narrative.

It converts *"we asked the model not to name anyone"* into **"a summary carrying a detected name is
not stored"**: deterministic, and pinnable the way a boundary rule is.

⚠ **There are TWO summary-producing prompts and the second is easy to miss.** The classification call
produces `grievance_summary`. The *translation* call produces `grievance_summary_en` — its own prompt
says *"create a new summary from the translated details"*, so it generates text while reading as a
translation step, and its output is the English summary most likely to reach a quarterly report or
ADB. A task to "gate the summary prompt" finds the first and misses the second; one output pass
covers both.

⚠ **Names removed is not identity removed.** A summary keeps ward-level location and circumstance.
The defensible claim is *the summary carries no names* — never *the summary is anonymous*.

Spec: docs/sprints/2026-08-llm/04-pii-redaction-spec.md §31.4
"""
from __future__ import annotations

import ast
import logging
from pathlib import Path

import pytest

from backend.services.LLM_services import _redact_generated_text

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES = REPO_ROOT / "backend/services/LLM_services.py"

# A summary the model might emit if input redaction missed the name.
LEAKED = "Er. Rajesh Shrestha refused to spray water on the road, per the complainant."


# ═════════════════════════════════════════════════════════════════════════════
# The pass itself
# ═════════════════════════════════════════════════════════════════════════════


def test_a_name_the_model_echoed_is_removed_before_storage():
    """⭐ The property. Input redaction missed it; this is the net underneath."""
    values = _redact_generated_text({"grievance_summary": LEAKED}, "grievance_summary")

    assert "Rajesh Shrestha" not in values["grievance_summary"]
    assert "<PERSON_1>" in values["grievance_summary"]


def test_a_clean_summary_is_returned_untouched():
    """The common case must not be disturbed — this text is shown and stored."""
    clean = "Dust from the road works is making children in the ward sick."
    values = _redact_generated_text({"grievance_summary": clean}, "grievance_summary")

    assert values["grievance_summary"] == clean


@pytest.mark.parametrize("value", [None, "", 123, [], {}])
def test_non_string_and_empty_fields_are_left_alone(value):
    """Defensive: the pass runs on whatever the model returned, which is not always a string."""
    values = _redact_generated_text({"grievance_summary": value}, "grievance_summary")
    assert values["grievance_summary"] == value


def test_a_missing_field_is_not_invented():
    values = _redact_generated_text({"other": "x"}, "grievance_summary")
    assert "grievance_summary" not in values


def test_multiple_fields_are_all_covered():
    values = _redact_generated_text(
        {"grievance_summary_en": LEAKED, "grievance_description_en": LEAKED},
        "grievance_summary_en",
        "grievance_description_en",
    )
    assert "Rajesh Shrestha" not in values["grievance_summary_en"]
    assert "Rajesh Shrestha" not in values["grievance_description_en"]


def test_the_miss_log_carries_a_count_and_not_the_name(caplog):
    """⚠ This firing is a SIGNAL, not routine housekeeping.

    If the output pass has work to do, the input recogniser missed a name that then travelled to a
    third-party model. The log line is the only place that fact surfaces — at WARNING, with a count
    and never the value.
    """
    with caplog.at_level(logging.DEBUG, logger="backend.services.LLM_services"):
        _redact_generated_text({"grievance_summary": LEAKED}, "grievance_summary")

    records = [r for r in caplog.records if "output_redaction" in r.getMessage()]
    assert records, "a missed identifier must be logged — it means the input pass failed"
    assert any(r.levelno >= logging.WARNING for r in records), (
        "log it at WARNING: the input recogniser missed a name that reached a third party"
    )
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "Rajesh Shrestha" not in logged


# ═════════════════════════════════════════════════════════════════════════════
# Both producers are covered — the structural half
# ═════════════════════════════════════════════════════════════════════════════


def _returns_of(fn_name: str) -> list[str]:
    tree = ast.parse(SERVICES.read_text(encoding="utf-8"))
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == fn_name
    )
    return [
        ast.dump(node.value)
        for node in ast.walk(fn)
        if isinstance(node, ast.Return) and node.value is not None
    ]


def test_the_classification_result_goes_through_the_output_pass():
    dumps = " ".join(_returns_of("classify_and_summarize_grievance"))
    assert "_redact_generated_text" in dumps, (
        "classify_and_summarize_grievance returns its result without the §31.4 output pass"
    )


def test_the_translation_result_goes_through_the_output_pass():
    """⭐ The one that is easy to miss.

    Its prompt says *"create a new summary from the translated details"* — it GENERATES text while
    reading as a translation step, and its output is the English summary most likely to reach a
    quarterly report.
    """
    dumps = " ".join(_returns_of("translate_grievance_to_english_LLM"))
    assert "_redact_generated_text" in dumps, (
        "translate_grievance_to_english_LLM returns its result without the §31.4 output pass — "
        "this is the summary-producing prompt that reads like a translation step"
    )


def test_the_prompt_instruction_is_not_counted_as_the_control():
    """§31.4 and DPG-33 step 3 both say this, and it is worth a test rather than a sentence.

    A prompt asking the model not to name anybody acts only on what comes back, never on what is
    SENT, and only in the case where redaction already failed. Keep it as defence in depth; the
    output pass is the control. This asserts the control exists in code — the instruction may come
    and go without changing the guarantee.
    """
    source = SERVICES.read_text(encoding="utf-8")
    assert "_redact_generated_text" in source
    assert source.count("_redact_generated_text(") >= 3, (
        "expected the helper plus both call sites"
    )
