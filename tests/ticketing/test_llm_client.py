# SPDX-License-Identifier: Apache-2.0

"""
Characterization net for the ticketing LLM surface — DPG-10 (ticketing half).

The source narrative for this sprint said there was one LLM surface. There are two:
`ticketing/clients/llm_client.py` is a second, entirely independent OpenAI client, and its own
docstring explains why — *"DO NOT import from backend/services/ — keep ticketing independent.
Replicate the pattern here."* That instruction was right about the service boundary and is exactly
why the hard-coded model names are duplicated.

This surface is not a side path. It produces `Ticket.ai_summary_en`, the officer-facing case
findings, and the **complainant-facing** resolved-case summary. A migration that fixed only
`backend/` would leave the indicator-4 claim false and leave complainant-facing output on a closed
model.

Pinned here, for all three call sites: the request (model, `response_format`, temperature, token
cap), the happy-path parse, and the failure contract — which on this surface is uniformly `None`,
unlike the chatbot surface's three different idioms.

⚠ **The standard/SEAH model split is deliberate** (a cost/quality decision documented at the
constants) and must survive DPG-12 as **two registry keys**, not one. The tests below pin both
branches so a collapse to a single model shows up as a failure rather than as a cheaper bill.

⚠ **Mock boundary:** the `OpenAI` class, with the cached `_client` reset — the module memoises its
client in a global, so patching the class alone would be defeated by a client cached in an earlier
test.

Spec: docs/sprints/2026-08-llm/02-llm-agnostic-spec.md §DPG-10 · Ledger: TESTS.md T-10-a … T-10-c
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ticketing.clients import llm_client


def _chat(content: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


class _OpenAIFactory:
    """Stands in for the `OpenAI` class; records construction kwargs and the request."""

    def __init__(self) -> None:
        self.built: list[MagicMock] = []
        self.response: SimpleNamespace = _chat("{}")
        self.error: Exception | None = None

    def __call__(self, **kwargs) -> MagicMock:
        inst = MagicMock()
        inst.build_kwargs = kwargs
        if self.error is not None:
            inst.chat.completions.create.side_effect = self.error
        else:
            inst.chat.completions.create.return_value = self.response
        self.built.append(inst)
        return inst

    @property
    def last_request(self) -> dict:
        return self.built[-1].chat.completions.create.call_args.kwargs


@pytest.fixture
def openai_class(monkeypatch) -> _OpenAIFactory:
    factory = _OpenAIFactory()
    monkeypatch.setattr(llm_client, "OpenAI", factory)
    monkeypatch.setattr(llm_client, "_client", None)  # defeat the cached client
    return factory


NEPALI_NOTE = "स्थलगत निरीक्षण गरियो, सडकमा धुलो धेरै छ।"

FINDINGS_JSON = {
    "summary_en": "Dust from the works is affecting nearby houses.",
    "key_findings": ["Watering has not been done", "Two households affected"],
    "recommended_action": "Instruct the contractor to wet-spray twice daily.",
    "urgency": "HIGH",
    "languages_detected": ["ne", "en"],
}

RESOLVED_JSON = {
    "field_reports_digest_en": "Three site visits were recorded.",
    "other_notes_digest_en": "The supervisor confirmed the schedule.",
    "combined_digest_en": "The complaint was investigated over two weeks.",
    "resolution_text_public": "सडकमा दिनको दुई पटक पानी छर्किने भएको छ।",
    "findings_summary_public": "The contractor must wet-spray the road twice daily.",
}

CONTEXT = {"ticket_id": "TCK-1", "events": [{"type": "NOTE_ADDED", "text": "dust"}]}
BUNDLE = {"ticket_id": "TCK-1", "field_reports": ["visit 1"]}


# ═════════════════════════════════════════════════════════════════════════════
# The client factory itself
# ═════════════════════════════════════════════════════════════════════════════

def test_the_client_is_built_from_settings_and_cached(openai_class, monkeypatch):
    """
    Today: the key comes from `TicketingSettings.openai_api_key` and the timeout is the literal
    30.0 declared in `_get_client()`. DPG-12 moves both into the shared registry; T-12-a then
    pins the replacement.
    """
    settings = SimpleNamespace(openai_api_key="sk-test-key")
    monkeypatch.setattr(llm_client, "get_settings", lambda: settings)

    first = llm_client._get_client()
    second = llm_client._get_client()

    assert first is second, "the client is memoised in a module global"
    assert len(openai_class.built) == 1
    assert openai_class.built[0].build_kwargs == {"api_key": "sk-test-key", "timeout": 30.0}


# ═════════════════════════════════════════════════════════════════════════════
# T-10-a / T-10-b — translate_to_english (call site 7)
# ═════════════════════════════════════════════════════════════════════════════

def test_translate_to_english_sends_gpt_4(openai_class):
    openai_class.response = _chat("A site inspection was carried out; there is a lot of dust.")

    result = llm_client.translate_to_english(NEPALI_NOTE)

    assert result == "A site inspection was carried out; there is a lot of dust."
    request = openai_class.last_request
    assert request["model"] == "gpt-4"
    assert request["temperature"] == 0.2
    assert request["max_tokens"] == 1024
    assert [m["role"] for m in request["messages"]] == ["system", "user"]
    assert request["messages"][1]["content"] == NEPALI_NOTE
    assert "response_format" not in request, "free text out — no JSON mode on this call site"


def test_translate_to_english_skips_the_call_for_text_that_looks_english(openai_class):
    """The >5% non-ASCII heuristic is a cost control; it returns the input unchanged."""
    assert llm_client.translate_to_english("The road is dusty.") == "The road is dusty."
    assert openai_class.built == []


def test_translate_to_english_returns_none_for_empty_input(openai_class):
    assert llm_client.translate_to_english("   ") is None
    assert openai_class.built == []


def test_translate_to_english_returns_none_on_provider_error(openai_class):
    openai_class.error = RuntimeError("provider down")
    assert llm_client.translate_to_english(NEPALI_NOTE) is None


def test_translate_to_english_returns_none_when_the_body_is_empty(openai_class):
    openai_class.response = _chat("   ")
    assert llm_client.translate_to_english(NEPALI_NOTE) is None


# ═════════════════════════════════════════════════════════════════════════════
# T-10-a / T-10-b — generate_case_findings (call site 8)
# ═════════════════════════════════════════════════════════════════════════════

def test_generate_case_findings_sends_gpt_4o_mini_for_a_standard_case(openai_class):
    openai_class.response = _chat(json.dumps(FINDINGS_JSON))

    assert llm_client.generate_case_findings(CONTEXT) == FINDINGS_JSON

    request = openai_class.last_request
    assert request["model"] == "gpt-4o-mini"
    assert request["response_format"] == {"type": "json_object"}
    assert request["temperature"] == 0.0
    assert request["max_tokens"] == 400


def test_generate_case_findings_sends_gpt_4o_for_a_seah_case(openai_class):
    """⚠ The split is deliberate: SEAH investigations get the more careful model."""
    openai_class.response = _chat(json.dumps(FINDINGS_JSON))

    llm_client.generate_case_findings(CONTEXT, is_seah=True)

    assert openai_class.last_request["model"] == "gpt-4o"


def test_generate_case_findings_fills_defaults_for_missing_keys(openai_class):
    """Kept as-is: DPG-13's schema makes this branch unreachable but does not delete it."""
    openai_class.response = _chat(json.dumps({"summary_en": "Only a summary."}))

    findings = llm_client.generate_case_findings(CONTEXT)

    assert findings == {
        "summary_en": "Only a summary.",
        "key_findings": [],
        "recommended_action": "",
        "urgency": "MEDIUM",
        "languages_detected": ["en"],
    }


def test_generate_case_findings_returns_none_for_an_empty_context(openai_class):
    assert llm_client.generate_case_findings({}) is None
    assert openai_class.built == []


def test_generate_case_findings_returns_none_on_an_empty_body(openai_class):
    openai_class.response = _chat("")
    assert llm_client.generate_case_findings(CONTEXT) is None


def test_generate_case_findings_returns_none_on_malformed_json(openai_class):
    openai_class.response = _chat("{not json")
    assert llm_client.generate_case_findings(CONTEXT) is None


def test_generate_case_findings_returns_none_on_provider_error(openai_class):
    openai_class.error = RuntimeError("provider down")
    assert llm_client.generate_case_findings(CONTEXT) is None


# ═════════════════════════════════════════════════════════════════════════════
# T-10-a / T-10-b — generate_resolved_case_summary_llm (call site 9)
# ═════════════════════════════════════════════════════════════════════════════

def test_generate_resolved_case_summary_sends_gpt_4o_mini_for_a_standard_case(openai_class):
    """⚠ Complainant-facing output — the text a person reads at the end of their grievance."""
    openai_class.response = _chat(json.dumps(RESOLVED_JSON))

    assert llm_client.generate_resolved_case_summary_llm(BUNDLE, primary_language="ne") == RESOLVED_JSON

    request = openai_class.last_request
    assert request["model"] == "gpt-4o-mini"
    assert request["response_format"] == {"type": "json_object"}
    assert request["temperature"] == 0.0
    assert request["max_tokens"] == 1200


def test_generate_resolved_case_summary_sends_gpt_4o_for_a_seah_case(openai_class):
    openai_class.response = _chat(json.dumps(RESOLVED_JSON))

    llm_client.generate_resolved_case_summary_llm(BUNDLE, is_seah=True)

    assert openai_class.last_request["model"] == "gpt-4o"


def test_generate_resolved_case_summary_passes_the_primary_language_in_the_payload(openai_class):
    """The public fields are written in the complainant's language — the model is told which."""
    openai_class.response = _chat(json.dumps(RESOLVED_JSON))

    llm_client.generate_resolved_case_summary_llm(BUNDLE, primary_language="ne")

    payload = json.loads(openai_class.last_request["messages"][1]["content"])
    assert payload["primary_language"] == "ne"
    assert payload["ticket_id"] == "TCK-1"


def test_generate_resolved_case_summary_fills_the_five_documented_keys(openai_class):
    openai_class.response = _chat(json.dumps({"combined_digest_en": "Only the digest."}))

    out = llm_client.generate_resolved_case_summary_llm(BUNDLE)

    assert out == {
        "combined_digest_en": "Only the digest.",
        "field_reports_digest_en": "",
        "other_notes_digest_en": "",
        "resolution_text_public": "",
        "findings_summary_public": "",
    }


def test_generate_resolved_case_summary_returns_none_for_an_empty_bundle(openai_class):
    assert llm_client.generate_resolved_case_summary_llm({}) is None
    assert openai_class.built == []


def test_generate_resolved_case_summary_returns_none_on_an_empty_body(openai_class):
    openai_class.response = _chat("")
    assert llm_client.generate_resolved_case_summary_llm(BUNDLE) is None


def test_generate_resolved_case_summary_returns_none_on_malformed_json(openai_class):
    openai_class.response = _chat("{not json")
    assert llm_client.generate_resolved_case_summary_llm(BUNDLE) is None


def test_generate_resolved_case_summary_returns_none_on_provider_error(openai_class):
    openai_class.error = RuntimeError("provider down")
    assert llm_client.generate_resolved_case_summary_llm(BUNDLE) is None
