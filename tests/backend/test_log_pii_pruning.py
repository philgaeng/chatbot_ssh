# SPDX-License-Identifier: Apache-2.0
"""
D-62 — PII is pruned from application logs to a *findable* prefix, and the pruning actually fires.

**The finding this exists for.** `form_status_check.py` truncated the complainant's phone with
`slot_value[:20]` before logging it. A Nepali mobile is **10 digits**, so the branch never fired and
the full number was logged behind something that reads, to anyone skimming, as a redaction. A guard
that is real code and permanently false is worse than no guard: it stops the next reader looking.

**So these tests assert the OUTPUT, against realistic values.** Not that a helper was called, not
that a slicing expression exists — that the rendered string is shorter than the secret and does not
contain it. That is the assertion the dead truncation would have failed on the day it was written.

The owner's rule (2026-08-27), per field type, because one length does not fit all:
  * free text (narrative, summary)  → first 8 characters + length  (`text_prefix_for_log`)
  * phone                           → last 4 digits only           (`mask_phone_for_log`)
  * OTP                             → never logged, at any length
  * whole grievance dict            → ids and lengths              (`grievance_row_summary`)

⚠ Eight characters of a narrative is still narrative. This is a bounded trade for findability, not
anonymisation, and the tests below pin the bound rather than pretending it is a stronger claim.

Spec: docs/sprints/2026-08-llm/04-pii-redaction-spec.md §DPG-34
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from backend.services.db_debug_log import (
    grievance_row_summary,
    mask_phone_for_log,
    text_prefix_for_log,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

# Realistic fixtures. The lengths are the whole point — a rule that passes on a 40-character
# placeholder and fails on a real 10-digit number is the defect this file exists for.
NEPALI_MOBILE = "9841234567"          # 10 digits, the real shape
OTP_CODE = "482915"                   # 6 digits, the real shape
NARRATIVE = "My name is Ram Bahadur and the contractor's dust is making my children sick."


# ── The phone rule: last four, and it must actually shorten a real number ────


def test_phone_masking_keeps_only_the_last_four_digits_of_a_real_number():
    out = mask_phone_for_log(NEPALI_MOBILE)

    assert NEPALI_MOBILE not in out, f"the full number survived masking: {out!r}"
    assert out.endswith("4567")
    # The specific failure that made this file necessary: a bound that cannot fire.
    digits = re.sub(r"\D", "", out)
    assert len(digits) == 4, f"expected 4 digits, got {len(digits)} in {out!r}"


def test_phone_masking_does_not_leak_a_short_value_by_passing_it_through():
    """A 4-digit value has no 'last four' to hide behind — it must be dropped, not echoed."""
    assert mask_phone_for_log("4567") == "(redacted)"
    assert mask_phone_for_log("") == "(none)"
    assert mask_phone_for_log(None) == "(none)"


# ── The free-text rule: 8 characters, and the length so it is findable ───────


def test_text_prefix_keeps_eight_characters_and_drops_the_rest():
    out = text_prefix_for_log("summary", NARRATIVE)

    assert NARRATIVE not in out
    assert "My name " in out, "the first 8 characters are what makes the record findable"
    assert "children sick" not in out, "the tail must not survive"
    assert str(len(NARRATIVE)) in out, "the length travels, so a reader can tell it was truncated"


def test_text_prefix_marks_truncation_so_a_reader_is_not_misled():
    assert text_prefix_for_log("s", "short").endswith("(5 chars)")
    assert "…" not in text_prefix_for_log("s", "short"), "nothing was cut; do not imply it was"
    assert "…" in text_prefix_for_log("s", NARRATIVE), "something was cut; say so"


# ── The OTP rule: no length of prefix is a redaction, so it is never logged ──


def test_no_prefix_of_an_otp_is_a_redaction():
    """The arithmetic behind 'never log the OTP', pinned so nobody re-adds a truncation.

    The owner's free-text rule is 8 characters. An OTP is 6 digits. Any prefix of 8 or more
    characters of a 6-character secret **is the entire secret** — which is why the OTP is excluded
    from the prefix rule rather than given a smaller one.
    """
    assert len(OTP_CODE) < 8
    assert OTP_CODE[:8] == OTP_CODE, "an 8-char prefix of a 6-digit code is the whole code"


def test_the_otp_value_is_not_logged_anywhere_in_the_otp_form():
    """The pin. Parses the form and fails if any logging call takes the OTP slot value.

    Source-level rather than behavioural because the alternative — driving the form and reading a
    caplog — passes just as well when someone adds a *second*, unlogged path. This asserts the
    property over the whole file.
    """
    src = (REPO_ROOT / "backend/actions/forms/form_otp.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    offenders: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr in {"info", "debug", "warning", "error"}):
            continue
        for arg in node.args:
            # A bare f-string or a direct reference to the OTP slot value reaching a log call.
            names = {n.id for n in ast.walk(arg) if isinstance(n, ast.Name)}
            if "slot_value" in names and not _is_length_only(arg):
                offenders.append(node.lineno)

    assert not offenders, (
        f"form_otp.py logs the OTP slot value at line(s) {offenders}. "
        "The OTP is a credential and no truncation of a 6-digit code is a redaction — "
        "log len() and the outcome, never the value."
    )


def _is_length_only(node: ast.AST) -> bool:
    """True when `slot_value` appears only inside a len(...) call."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id == "slot_value":
            if not _wrapped_in_len(node, sub):
                return False
    return True


def _wrapped_in_len(root: ast.AST, target: ast.Name) -> bool:
    for sub in ast.walk(root):
        if (
            isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Name)
            and sub.func.id == "len"
            and any(n is target for n in ast.walk(sub))
        ):
            return True
    return False


# ── The whole-record rule ────────────────────────────────────────────────────


def test_grievance_row_summary_does_not_echo_the_narrative():
    row = {
        "grievance_id": "GR-2026-0001",
        "grievance_description": NARRATIVE,
        "grievance_summary": "Dust from road works is affecting children.",
    }
    out = grievance_row_summary(row)

    assert "GR-2026-0001" in out, "the id is the correlation key and must survive"
    assert NARRATIVE not in out
    assert "Ram Bahadur" not in out


# ── The call-site pins: the helpers must actually be USED ───────────────────
#
# ⚠ These exist because the first version of this file did not have them, and a mutation proved
# it: reverting `mask_phone_for_log(slot_value)` to `slot_value` at BOTH phone call sites left all
# ten tests green. Testing the helper is not testing the call site — that is the D-42 shape (a test
# that passes for a reason unrelated to the property it claims), and the whole finding here was a
# call site logging a raw value.


_LOG_METHODS = {"info", "debug", "warning", "error", "exception", "critical"}
# Wrapping a value in any of these makes it safe to log. Kept as one list so a new helper in
# db_debug_log has exactly one place to be registered.
_SAFE_WRAPPERS = {
    "mask_phone_for_log",
    "text_prefix_for_log",
    "text_len_for_log",
    "grievance_row_summary",
    "email_send_log_summary",
    "len",
}


def _log_calls_passing_bare(src: str, name: str) -> list[int]:
    """Line numbers of logging calls that receive `name` outside a safe wrapper."""
    tree = ast.parse(src)
    bad: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr in _LOG_METHODS):
            continue
        for arg in node.args + [kw.value for kw in node.keywords]:
            for sub in ast.walk(arg):
                if isinstance(sub, ast.Name) and sub.id == name:
                    if not _inside_safe_wrapper(arg, sub):
                        bad.append(node.lineno)
    return sorted(set(bad))


def _inside_safe_wrapper(root: ast.AST, target: ast.Name) -> bool:
    for sub in ast.walk(root):
        if (
            isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Name)
            and sub.func.id in _SAFE_WRAPPERS
            and any(n is target for n in ast.walk(sub))
        ):
            return True
    return False


@pytest.mark.parametrize(
    "path",
    [
        "backend/actions/services/contact/phone.py",
        "backend/actions/forms/form_status_check.py",
        "backend/actions/forms/form_otp.py",
        "backend/actions/forms/form_grievance.py",
    ],
)
def test_no_actions_call_site_logs_a_bare_slot_value(path: str):
    """The pin the mutation asked for: a raw `slot_value` must not reach a log call.

    `slot_value` in `backend/actions/` is whatever the complainant just typed — a phone number, an
    OTP, a grievance narrative. Which one depends on the form, so the rule is uniform: wrap it, or
    do not log it.

    ⚠ Scoped to the four files DPG-30's inventory names, not the whole tree. A repo-wide sweep is
    the right end state and a bigger change than this ticket; widening the list is one line, and
    that is deliberately cheaper than arguing about it.
    """
    src = (REPO_ROOT / path).read_text(encoding="utf-8")
    offenders = _log_calls_passing_bare(src, "slot_value")

    assert not offenders, (
        f"{path} logs a bare `slot_value` at line(s) {offenders}. Wrap it: "
        "mask_phone_for_log for a phone, text_prefix_for_log for free text, len() for an OTP "
        "(which must never be logged as a value)."
    )


# ── The regression pin: the truncation that could never fire ─────────────────


@pytest.mark.parametrize(
    "path",
    [
        "backend/actions/forms/form_status_check.py",
        "backend/actions/services/contact/phone.py",
        "backend/actions/forms/form_otp.py",
    ],
)
def test_no_call_site_reintroduces_a_slice_based_phone_redaction(path: str):
    """`slot_value[:20]` on a 10-digit number is the defect. Ban the shape, not the number.

    ⚠ Deliberately source-level and deliberately broad: any `[:N]` slice applied to a value on its
    way into a log in these three files is either dead (like the original) or a per-field rule that
    belongs in `db_debug_log`, where it can be tested once.
    """
    src = _without_comments((REPO_ROOT / path).read_text(encoding="utf-8"))
    assert "slot_value[:" not in src, (
        f"{path} slices slot_value before logging. A Nepali mobile is 10 digits and an OTP is 6, "
        "so a slice is either dead code or the whole secret — use db_debug_log's helpers."
    )


def _without_comments(src: str) -> str:
    """Strip comments before the check.

    ⚠ Not a convenience — a correctness fix this test needed on its first run. The comment left at
    the repaired call site *explains* the defect, and naming it spelled the banned shape, so the pin
    flagged its own documentation. Same trap `test_doc_code_refs.py` warns about for citations, and
    the same resolution T-15b-d already uses: inspect the code, not the prose about the code.
    """
    import io
    import tokenize

    out: list[str] = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type != tokenize.COMMENT:
            out.append(tok.string)
    return "".join(out)
