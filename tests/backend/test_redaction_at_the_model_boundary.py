# SPDX-License-Identifier: Apache-2.0
"""
T-33-a … T-33-c — grievance text is pseudonymised before it leaves the process (DPG-33 step 1).

**Why the chokepoint and not the call sites.** Sprint 1 (DPG-11/12/18) collapsed nine call sites
into **two** `call_llm()` entry points. That is what makes this two hooks instead of nine, and it is
why DPG-33 depends on Sprint 1 rather than merely following it.

**Opt-OUT, not opt-in, and the tests below pin that specifically.** `redact=True` is the default so a
new call site is pseudonymised without its author knowing this exists; switching it off is a visible
decision in the diff. Opt-in is the shape that fails — one forgotten keyword and a grievance crosses
the border in clear.

⚠ **These tests import the OpenAI SDK** (both clients do, at module level), so they run in-container
alongside `test_llm_services.py` rather than on a bare host.

Spec: docs/sprints/2026-08-llm/04-pii-redaction-spec.md §DPG-33
"""
from __future__ import annotations

import inspect
import logging
from unittest.mock import MagicMock, patch

import pytest

import backend.services.llm_client as chatbot_client
import ticketing.clients.llm_client as ticketing_client

# A grievance that names an official, a phone, and a settlement address — the three things §31.2
# and §31.2b exist for, in one string.
NARRATIVE = "Er. Rajesh Shrestha called from 9812345678 about ward 5 Duhabi"


def _capture(module, monkeypatch):
    """Swap the module's client for one that records the request, and return the record."""
    sent: dict = {}

    def fake_create(**kwargs):
        sent.update(kwargs)
        response = MagicMock()
        response.choices = [MagicMock(finish_reason="stop")]
        response.choices[0].message.content = "{}"
        response.usage = None
        return response

    client = MagicMock()
    client.chat.completions.create = fake_create
    if module is chatbot_client:
        monkeypatch.setattr(module, "get_llm_client", lambda: client)
    else:
        monkeypatch.setattr(module, "_get_client", lambda: client)
    return sent


def _call(module, messages, **kwargs):
    """Drive call_llm, tolerating the parse stage failing on our stub response."""
    try:
        module.call_llm("classify" if module is chatbot_client else "ticket_findings",
                        messages, **kwargs)
    except Exception:  # noqa: BLE001 - the stub response is not valid for every schema
        pass


# ═════════════════════════════════════════════════════════════════════════════
# T-33-a — the text that reaches the provider is pseudonymised
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "module", [chatbot_client, ticketing_client], ids=["chatbot", "ticketing"]
)
def test_pii_is_replaced_before_the_request_leaves(module, monkeypatch):
    """⭐ The property the whole ticket is for, asserted on BOTH surfaces.

    Checked on what the provider actually receives, not on what the helper returns — a redactor
    that runs and is then bypassed would satisfy a weaker test.
    """
    sent = _capture(module, monkeypatch)
    _call(module, [{"role": "user", "content": NARRATIVE}])

    delivered = sent["messages"][0]["content"]
    assert "Rajesh Shrestha" not in delivered
    assert "9812345678" not in delivered
    assert "<PERSON_1>" in delivered
    assert "<PHONE_1>" in delivered


@pytest.mark.parametrize(
    "module", [chatbot_client, ticketing_client], ids=["chatbot", "ticketing"]
)
def test_the_callers_own_messages_are_not_mutated(module, monkeypatch):
    """The caller usually still needs the original — the prompt it built, the text it will store.

    Redacting in place would be a silent data change three frames away from the decision.
    """
    _capture(module, monkeypatch)
    messages = [{"role": "user", "content": NARRATIVE}]
    _call(module, messages)

    assert messages[0]["content"] == NARRATIVE, "call_llm mutated the caller's list"


@pytest.mark.parametrize(
    "module", [chatbot_client, ticketing_client], ids=["chatbot", "ticketing"]
)
def test_non_pii_text_crosses_unchanged(module, monkeypatch):
    """Redaction must not disturb the prompt itself — the classifier reads these words."""
    prompt = "Categorise this grievance. Reply only with keys from the dictionary."
    sent = _capture(module, monkeypatch)
    _call(module, [{"role": "system", "content": prompt}])

    assert sent["messages"][0]["content"] == prompt


# ═════════════════════════════════════════════════════════════════════════════
# T-33-b — opt-OUT, and it is the default
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "module", [chatbot_client, ticketing_client], ids=["chatbot", "ticketing"]
)
def test_redaction_defaults_to_on(module):
    """⭐ The shape of the parameter is the control.

    A new call site must get pseudonymisation without knowing it exists. Opt-in is what fails: one
    forgotten keyword and grievance text crosses the border in clear.
    """
    default = inspect.signature(module.call_llm).parameters["redact"].default
    assert default is True, "redaction must be opt-OUT; a default of False silently leaks"


@pytest.mark.parametrize(
    "module", [chatbot_client, ticketing_client], ids=["chatbot", "ticketing"]
)
def test_redaction_is_keyword_only(module):
    """`redact` cannot be set by accident from a positional argument."""
    param = inspect.signature(module.call_llm).parameters["redact"]
    assert param.kind is inspect.Parameter.KEYWORD_ONLY


@pytest.mark.parametrize(
    "module", [chatbot_client, ticketing_client], ids=["chatbot", "ticketing"]
)
def test_opting_out_is_possible_and_visible(module, monkeypatch):
    """The escape hatch exists — it just has to be typed, which is the point."""
    sent = _capture(module, monkeypatch)
    _call(module, [{"role": "user", "content": NARRATIVE}], redact=False)

    assert "Rajesh Shrestha" in sent["messages"][0]["content"]


def test_no_production_call_site_opts_out():
    """⚠ The escape hatch must stay unused in production code.

    A `redact=False` in the tree is not automatically wrong — but it is always a decision someone
    should have argued for, and this is where the argument gets noticed.
    """
    out = _git_grep("redact=False", "backend/", "ticketing/")
    assert not out, f"a production call site opts out of redaction:\n{out}"


# ═════════════════════════════════════════════════════════════════════════════
# T-33-c — the mapping does not escape with the text
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "module", [chatbot_client, ticketing_client], ids=["chatbot", "ticketing"]
)
def test_the_mapping_is_never_sent_to_the_provider(module, monkeypatch):
    """⚠ The clause "the re-identification key never leaves Nepal" rests on exactly this.

    Serialise the mapping into the same request as the redacted text and the whole argument
    collapses silently: the key travelled with the ciphertext.
    """
    sent = _capture(module, monkeypatch)
    _call(module, [{"role": "user", "content": NARRATIVE}])

    blob = repr(sent)
    assert "Rajesh Shrestha" not in blob
    assert "9812345678" not in blob


@pytest.mark.parametrize(
    "module", [chatbot_client, ticketing_client], ids=["chatbot", "ticketing"]
)
def test_redaction_logs_counts_not_values(module, monkeypatch, caplog):
    """Counts are useful; values are the thing being removed."""
    _capture(module, monkeypatch)
    with caplog.at_level(logging.DEBUG):
        _call(module, [{"role": "user", "content": NARRATIVE}])

    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "Rajesh Shrestha" not in logged
    assert "9812345678" not in logged


@pytest.mark.parametrize(
    "module", [chatbot_client, ticketing_client], ids=["chatbot", "ticketing"]
)
def test_call_llm_does_not_return_the_mapping(module):
    """⚠ Deliberate, and it follows from the 2026-08-27 storage decision.

    The STORED summary carries no names, classification output is machine-consumed, and the
    complainant still sees their own words in `grievance_description` (stored unredacted —
    redaction is at transmission, not storage). So nothing needs `restore()` here, the mapping
    never leaves this frame, and DPG-31's "the mapping is never persisted" stays true by
    construction rather than by discipline.
    """
    source = inspect.getsource(module.call_llm)
    assert "return parse_response" in source, "the return shape changed — re-check the mapping"
    assert "mapping" not in source.split("return parse_response")[1], (
        "call_llm returns the mapping; that puts the key on the same path as the text"
    )


def _git_grep(pattern: str, *paths: str) -> str:
    """`git grep`, or an explicit skip when git is unavailable.

    ⚠ Skips rather than passes. These are repository-hygiene checks and they are meaningless
    outside a checkout — the container images carry no git. A silent pass would be the
    empty-gate pattern: a green tick that asserted nothing (DPG-24's own lesson).
    """
    import shutil
    import subprocess
    from pathlib import Path

    if shutil.which("git") is None:
        pytest.skip("git unavailable — repository-hygiene check cannot run here (not a pass)")
    return subprocess.run(
        ["git", "grep", "-n", pattern, "--", *paths],
        capture_output=True, text=True,
        cwd=Path(__file__).resolve().parents[2],
    ).stdout.strip()
