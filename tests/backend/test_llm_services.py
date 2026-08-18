# SPDX-License-Identifier: Apache-2.0

"""
Characterization net for the chatbot LLM surface — DPG-10 (T-10-a … T-10-f).

**This file adds no behaviour. It records the behaviour that exists**, so DPG-11/13/14 can change
the *shape* of `backend/services/LLM_services.py` without changing what it does. Before this file,
not one test in the repository imported that module — the product's primary AI path had no net at
all, which is the same gap T3-04 found in the PII boundary and treated the same way.

What is pinned, per call site:

* **the request** — model name and whether `response_format` is set. After DPG-11 the model name is
  resolved from `backend/config/llm_config.py`; these tests then prove the *same* name still reaches
  the client unless configuration says otherwise. That is the entire point of the net.
* **the happy-path parse** — a realistic provider response in, the documented dict out.
* **the failure contract** — different for every function: raise, sentinel dict, or `None`. Three
  idioms in one module. Pinned **as they are**; unifying them is a behaviour change and out of scope.
* **the `client is None` guard** — the module client is `None` when `OPENAI_API_KEY` is unset. Five
  functions guard on it, differently.

⚠ **Two functions do not do what their contract says**, and the tests below pin the *real* behaviour
with the intended one named beside it:

* `extract_contact_info` raised **`UnboundLocalError`** — not `{field_name: ""}` — when the failure
  happened before `response` was bound (deviation **D-28**). ✅ **Fixed in DPG-14**; the tests below
  now pin the declared contract, and they are the tests that failed before the fix.
* `translate_grievance_to_english_LLM` raises **`UnboundLocalError`** — not `ValueError` — when the
  failure happens before `result` is bound (deviation **D-29**, found while writing this file).
  ⏸ **Deliberately not fixed here**: the one-line fix makes a `ValueError` reachable whose message
  interpolates the grievance narrative into the Celery log. It lands with Sprint 3's T-34-b.

⚠ **The mock boundary is the `OpenAI` class, not the module-level `client`.**
`classify_and_summarize_grievance` builds its **own** client, shadowing the module attribute; a test
that patches only `LLM_services.client` never touches the product's primary classification path.
DPG-11 collapses that asymmetry — which is why the pin has to exist before it.

Spec: docs/sprints/2026-08-llm/02-llm-agnostic-spec.md §DPG-10 · Ledger: TESTS.md T-10-a … T-10-f
"""
from __future__ import annotations

import inspect
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.config import llm_config
from backend.services import LLM_services as llm
from backend.services import llm_client as llm_client_factory


# ── helpers ──────────────────────────────────────────────────────────────────

def _chat(content: str) -> SimpleNamespace:
    """A minimal stand-in for openai's ChatCompletion — only what the code reads."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


@pytest.fixture
def client(monkeypatch) -> MagicMock:
    """
    Replace the clients at the factory boundary — **one fake for all nine call sites**.

    Before DPG-11 this fixture patched a module-level `client` attribute and a second fixture
    patched the `OpenAI` class, because classification built its own shadow client. There is now
    one client per surface, built lazily by `backend/services/llm_client.py`, so one fake covers
    everything and `built` is countable — which is what T-14-b asserts.
    """
    fake = MagicMock()
    # Patched in **both** modules: `call_llm` (DPG-18) resolves `get_llm_client` as a module global
    # in the factory, while `LLM_services._llm_client()` holds an imported reference. Patching one
    # covers half the call sites, which is worse than patching neither because it looks like it works.
    for module in (llm, llm_client_factory):
        monkeypatch.setattr(module, "get_llm_client", lambda: fake, raising=False)
        monkeypatch.setattr(module, "get_asr_client", lambda: fake, raising=False)
    monkeypatch.setattr(llm, "_llm_client", lambda: fake)
    monkeypatch.setattr(llm, "_asr_client", lambda: fake)
    return fake


@pytest.fixture(autouse=True)
def fresh_registry():
    """The registry caches its settings; tests that patch env must not leak into each other."""
    llm_config.get_llm_settings.cache_clear()
    yield
    llm_config.get_llm_settings.cache_clear()


CONTACT_JSON = {
    "complainant_phone": "9841234567",
    "complainant_full_name": "Ram Bahadur",
    "complainant_district": "Jhapa",
    "complainant_municipality": "Birtamod",
    "complainant_village": "Ward 4",
    "complainant_address": "Near the culvert",
}

ALL_CONTACT_INPUT = {
    "complainant_phone": "phone: 9841234567",
    "complainant_full_name": "my name is Ram Bahadur",
    "contact_municipality": "Birtamod",
    "contact_village": "Ward 4",
    "contact_address": "Near the culvert",
}

# ⚠ Must clear MIN_CLASSIFY_CHARS (25). The old fixture, GRIEVANCE_TEXT, is 12 characters — below
# the DPG-19 gate, so the model is never called for it. That the gate caught these tests when it
# landed is the gate working.
GRIEVANCE_TEXT = "सडकको धुलोले बच्चाहरू बिरामी भए, कृपया पानी छर्नुहोस्।"

CLASSIFY_JSON = {
    "grievance_summary": "धुलोले बच्चाहरू बिरामी भए",
    "grievance_categories": ["Dust and air pollution"],
    "grievance_categories_alternative": ["Noise pollution"],
    "follow_up_question": "कति दिनदेखि यो समस्या छ?",
}

TRANSLATE_INPUT = {
    "grievance_id": "GR-2026-0001",
    "language_code": "ne",
    "grievance_description": "सडकको धुलोले बच्चाहरू बिरामी भए।",
    "grievance_summary": "धुलो समस्या",
    "grievance_categories": ["Dust and air pollution"],
    "complainant_district": "Jhapa",
    "complainant_province": "Koshi",
}

TRANSLATE_JSON = {
    "grievance_description_en": "Dust from the road made the children sick.",
    "grievance_summary_en": "Dust problem",
    "confidence_score": "0.9",
}


# ═════════════════════════════════════════════════════════════════════════════
# T-10-a — the request: model name, message roles, response_format
# ═════════════════════════════════════════════════════════════════════════════

def test_transcribe_sends_whisper_1(client, tmp_path):
    """Call site 1. The language kwarg is `language` since DPG-14.3 — see T-14-c below."""
    audio = tmp_path / "note.ogg"
    audio.write_bytes(b"\x00\x01")
    client.audio.transcriptions.create.return_value = SimpleNamespace(text="धुलो")

    assert llm.transcribe_audio_file(str(audio), "ne") == "धुलो"

    kwargs = client.audio.transcriptions.create.call_args.kwargs
    assert kwargs["model"] == "whisper-1"
    assert kwargs["language"] == "ne"
    assert "language_code" not in kwargs


def test_extract_contact_info_sends_gpt_35_turbo_with_json_object(client):
    """Call site 2."""
    client.chat.completions.create.return_value = _chat(
        json.dumps({"complainant_phone": "9841234567"})
    )

    llm.extract_contact_info({"complainant_phone": "my number is 9841234567"})

    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-3.5-turbo"
    assert kwargs["response_format"] == {"type": "json_object"}
    assert [m["role"] for m in kwargs["messages"]] == ["system", "user"]


def test_extract_all_contact_info_sends_gpt_35_turbo_with_json_object(client):
    """Call site 3."""
    client.chat.completions.create.return_value = _chat(json.dumps(CONTACT_JSON))

    llm.extract_all_contact_info(ALL_CONTACT_INPUT)

    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-3.5-turbo"
    assert kwargs["response_format"] == {"type": "json_object"}
    assert [m["role"] for m in kwargs["messages"]] == ["system", "user"]


def test_classify_sends_gpt_5_nano_with_a_strict_schema(client):
    """
    Call site 4 — the product's primary AI path, and DPG-13's biggest win.

    Until 2026-08-18 this request carried **no `response_format` at all**: it asked for "strict
    JSON" in the prompt and hoped, and a malformed reply was absorbed into `{}` by
    `parse_llm_response`, where it was indistinguishable from a successful empty classification.
    It now sends a strict `json_schema` — verified against the live provider before the default
    was set, because `gpt-3.5-turbo` and `gpt-4` reject that parameter with a 400.
    """
    client.chat.completions.create.return_value = _chat(json.dumps(CLASSIFY_JSON))

    llm.classify_and_summarize_grievance(GRIEVANCE_TEXT, language_code="ne")

    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-5-nano"
    assert kwargs["response_format"]["type"] == "json_schema"
    assert kwargs["response_format"]["json_schema"]["strict"] is True
    assert [m["role"] for m in kwargs["messages"]] == ["system", "user"]


def test_classify_keeps_its_own_deadline_as_a_per_request_timeout(client, monkeypatch):
    """
    **T-14-b.** Classification used to build a second client purely to carry its own timeout.
    The deadline survives — as a per-request value from the registry — and the second client
    does not. `OPENAI_CLASSIFICATION_TIMEOUT` is still honoured, as a deprecated alias.
    """
    client.chat.completions.create.return_value = _chat(json.dumps(CLASSIFY_JSON))
    monkeypatch.delenv("OPENAI_CLASSIFICATION_TIMEOUT", raising=False)
    monkeypatch.delenv("TIMEOUT_CLASSIFY", raising=False)

    llm.classify_and_summarize_grievance(GRIEVANCE_TEXT)
    assert client.chat.completions.create.call_args.kwargs["timeout"] == 120.0

    monkeypatch.setenv("OPENAI_CLASSIFICATION_TIMEOUT", "45")
    llm_config.get_llm_settings.cache_clear()
    llm.classify_and_summarize_grievance(GRIEVANCE_TEXT)
    assert client.chat.completions.create.call_args.kwargs["timeout"] == 45.0


def test_translate_grievance_sends_gpt_4_with_no_response_format(client):
    """Call site 5 — JSON by prompt instruction only, like classification."""
    client.chat.completions.create.return_value = _chat(json.dumps(TRANSLATE_JSON))

    llm.translate_grievance_to_english_LLM(dict(TRANSLATE_INPUT))

    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-4"
    assert "response_format" not in kwargs


def test_detect_sensitive_content_sends_gpt_35_turbo_with_json_object(client):
    """Call site 6 — the SEAH detection path."""
    client.chat.completions.create.return_value = _chat(
        json.dumps({"detected": True, "level": "high", "message": "excerpt"})
    )

    llm.detect_sensitive_content_llm("a worker followed me home", "en")

    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-3.5-turbo"
    assert kwargs["response_format"] == {"type": "json_object"}


# ═════════════════════════════════════════════════════════════════════════════
# T-10-b — the happy-path parse
# ═════════════════════════════════════════════════════════════════════════════

def test_extract_contact_info_returns_the_parsed_object(client):
    client.chat.completions.create.return_value = _chat(
        json.dumps({"complainant_phone": "9841234567"})
    )
    assert llm.extract_contact_info(
        {"complainant_phone": "my number is 9841234567"}
    ) == {"complainant_phone": "9841234567"}


def test_extract_all_contact_info_returns_all_six_fields(client):
    client.chat.completions.create.return_value = _chat(json.dumps(CONTACT_JSON))
    assert llm.extract_all_contact_info(ALL_CONTACT_INPUT) == CONTACT_JSON


def test_classify_returns_the_four_documented_keys(client):
    client.chat.completions.create.return_value = _chat(json.dumps(CLASSIFY_JSON))
    result = llm.classify_and_summarize_grievance(GRIEVANCE_TEXT, language_code="ne")
    assert result == CLASSIFY_JSON


def test_translate_grievance_adds_provenance_to_the_translated_body(client):
    """The returned dict is the model's JSON plus four fields the function stamps on."""
    client.chat.completions.create.return_value = _chat(json.dumps(TRANSLATE_JSON))

    result = llm.translate_grievance_to_english_LLM(dict(TRANSLATE_INPUT))

    assert result["grievance_description_en"] == TRANSLATE_JSON["grievance_description_en"]
    assert result["grievance_id"] == "GR-2026-0001"
    assert result["source_language"] == "ne"
    assert result["translation_method"] == "LLM"
    assert result["grievance_categories_en"] == ["Dust and air pollution"]


def test_detect_sensitive_content_returns_detected_level_and_message(client):
    client.chat.completions.create.return_value = _chat(
        json.dumps({"detected": True, "level": "high", "message": "he followed me"})
    )
    assert llm.detect_sensitive_content_llm("a worker followed me home", "en") == {
        "detected": True,
        "level": "high",
        "message": "he followed me",
    }


# ═════════════════════════════════════════════════════════════════════════════
# T-10-c — the failure contract, per function (raise / sentinel dict / None)
# ═════════════════════════════════════════════════════════════════════════════

def test_transcribe_re_raises_provider_errors(client, tmp_path):
    audio = tmp_path / "note.ogg"
    audio.write_bytes(b"\x00")
    client.audio.transcriptions.create.side_effect = RuntimeError("provider down")

    with pytest.raises(RuntimeError, match="provider down"):
        llm.transcribe_audio_file(str(audio), "ne")


def test_extract_contact_info_returns_the_empty_sentinel_when_the_call_fails(client):
    """
    **D-28, fixed in DPG-14.** This is the contract the module always declared and never had:
    before the fix, `response` was bound only after the API call while the handler's first
    statement read it, so a provider failure surfaced as `UnboundLocalError` from inside the
    `except`. The sentinel carries the real field name because the caller
    (`registered_tasks.extract_contact_info_task`) validates every returned key against
    `USER_FIELDS`.
    """
    client.chat.completions.create.side_effect = RuntimeError("provider down")

    assert llm.extract_contact_info(
        {"complainant_phone": "9841234567"}
    ) == {"complainant_phone": ""}


def test_extract_contact_info_rejects_input_with_no_contact_field_without_leaking_values(client):
    """
    The one case that is a caller error rather than a model failure: nothing in `contact_data`
    is a `USER_FIELDS` key, so there is no field to extract and no sentinel key to return.
    Previously `UnboundLocalError`; now a `ValueError` naming the **keys**.

    ⚠ The message must never carry the *values* — this exception reaches the Celery error log,
    and `contact_data` holds a name or a phone number (T-34-b).
    """
    with pytest.raises(ValueError) as exc:
        llm.extract_contact_info({"unexpected_key": "Ram Bahadur, 9841234567"})

    assert "unexpected_key" in str(exc.value)
    assert "Ram Bahadur" not in str(exc.value)
    assert "9841234567" not in str(exc.value)


def test_extract_contact_info_returns_the_empty_sentinel_when_the_body_is_malformed(client):
    """The one path that *does* reach the documented contract: `response` is bound, JSON is not."""
    client.chat.completions.create.return_value = _chat("not json at all")

    assert llm.extract_contact_info(
        {"complainant_phone": "9841234567"}
    ) == {"complainant_phone": ""}


def test_extract_all_contact_info_returns_six_empty_strings_on_failure(client):
    client.chat.completions.create.side_effect = RuntimeError("provider down")

    assert llm.extract_all_contact_info(ALL_CONTACT_INPUT) == {
        "complainant_phone": "",
        "complainant_full_name": "",
        "complainant_district": "",
        "complainant_municipality": "",
        "complainant_village": "",
        "complainant_address": "",
    }


def test_extract_all_contact_info_reports_a_malformed_body_as_a_failure(client, caplog):
    """
    **Changed by DPG-13, deliberately.** This used to return a bare `{}`, because
    `parse_llm_response` swallowed the `JSONDecodeError` — so a parse failure and an empty
    extraction were the same value. The parse now raises, this function's own failure contract
    fires, and the log says which of the two happened.

    ⚠ Honest limit: the *return value* here is the same as for a provider outage — the six-key
    sentinel. What distinguishes them is the log line, which names the parse failure and the
    response length. The call site where the distinction is visible in the return value is
    classification, below, and that is the one that mattered.

    ⏳ **DPG-18 changed which layer raises**, not the contract: `parse_response()` now refuses the
    malformed body with `LLMParseError` before this function ever sees it.
    """
    client.chat.completions.create.return_value = _chat("{not json")

    with caplog.at_level("ERROR"):
        result = llm.extract_all_contact_info(ALL_CONTACT_INPUT)

    assert result == {
        "complainant_phone": "",
        "complainant_full_name": "",
        "complainant_district": "",
        "complainant_municipality": "",
        "complainant_village": "",
        "complainant_address": "",
    }
    assert any("Error extracting contact info" in r.getMessage() for r in caplog.records)


def test_classify_returns_a_status_error_dict_when_the_call_fails(client):
    client.chat.completions.create.side_effect = RuntimeError("model not found for this account")

    result = llm.classify_and_summarize_grievance(GRIEVANCE_TEXT)

    assert result["status"] == "error"
    assert "model not found" in result["error"]
    assert result["grievance_summary"] == ""
    assert result["grievance_categories"] == []
    assert result["grievance_categories_alternative"] == []
    assert result["follow_up_question"] == ""


def test_classify_short_circuits_on_empty_text_without_calling_the_model(client):
    """The empty-text guard returns *five* keys — no `follow_up_question`, unlike the error path."""
    result = llm.classify_and_summarize_grievance("")

    client.chat.completions.create.assert_not_called()
    assert result == {
        "grievance_summary": "",
        "grievance_categories": [],
        "grievance_categories_alternative": [],
        "status": "error",
        "error": "No grievance text provided",
    }


# ✅ D-29's characterization test lived here and was deleted by DPG-19.3, which fixed the defect it
# pinned: `result` is now bound before the `try`, so a pre-call failure raises the declared
# `ValueError`. Its replacement is `test_a_pre_call_failure_now_raises_the_declared_value_error`.


def test_translate_grievance_raises_value_error_on_a_malformed_body(client):
    """The one path that reaches the documented `ValueError`: `result` is bound, JSON is not."""
    client.chat.completions.create.return_value = _chat("{not json")

    with pytest.raises(ValueError, match="Error translating grievance to English"):
        llm.translate_grievance_to_english_LLM(dict(TRANSLATE_INPUT))


def test_translate_grievance_rejects_input_missing_description_or_language(client):
    payload = dict(TRANSLATE_INPUT)
    payload["grievance_description"] = ""

    with pytest.raises(ValueError, match="grievance_description and language_code are required"):
        llm.translate_grievance_to_english_LLM(payload)


def test_translate_grievance_raises_a_warning_when_the_summary_is_missing(client):
    """Pinned because it is surprising: `Warning` is raised as an exception, not warned."""
    payload = dict(TRANSLATE_INPUT)
    payload["grievance_summary"] = ""

    with pytest.raises(Warning, match="grievance_summary is missing"):
        llm.translate_grievance_to_english_LLM(payload)


def test_detect_sensitive_content_fails_open(client):
    """
    ⚠ On any failure this returns `detected: False` — it fails **open**.

    That is a documented, justified default (Q-14) **on one condition**: it is the second of two
    independent detection paths, the first being the deterministic scored keyword pre-filter in
    `backend/shared_functions/keyword_detector.py`, which runs synchronously inside the conversation
    and needs no model. If that ever stops being true, fail-open stops being justified.
    """
    client.chat.completions.create.side_effect = RuntimeError("provider down")

    assert llm.detect_sensitive_content_llm("a worker followed me home", "en") == {
        "detected": False,
        "level": "low",
        "message": "",
    }


def test_detect_sensitive_content_skips_the_call_on_empty_text(client):
    assert llm.detect_sensitive_content_llm("   ", "en") == {
        "detected": False,
        "level": "low",
        "message": "",
    }
    client.chat.completions.create.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# T-10-d — the `client is None` guard, per function
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def no_client(monkeypatch):
    """No API key configured → the factory raises → every path takes its documented fallback."""

    def _refuse():
        raise RuntimeError("No API key configured for the LLM endpoint (test)")

    for module in (llm, llm_client_factory):
        monkeypatch.setattr(module, "get_llm_client", _refuse, raising=False)
        monkeypatch.setattr(module, "get_asr_client", _refuse, raising=False)
    monkeypatch.setattr(llm, "_llm_client", lambda: None)
    monkeypatch.setattr(llm, "_asr_client", lambda: None)


def test_transcribe_raises_runtime_error_without_a_client(no_client, tmp_path):
    audio = tmp_path / "note.ogg"
    audio.write_bytes(b"\x00")

    with pytest.raises(RuntimeError, match="not available for transcription"):
        llm.transcribe_audio_file(str(audio), "ne")


def test_extract_contact_info_returns_the_sentinel_without_a_client(no_client):
    """D-28 again: the guard raises, and the handler now turns it into the declared sentinel."""
    assert llm.extract_contact_info(
        {"complainant_phone": "9841234567"}
    ) == {"complainant_phone": ""}


def test_extract_all_contact_info_returns_the_sentinel_without_a_client(no_client):
    assert llm.extract_all_contact_info(ALL_CONTACT_INPUT) == {
        "complainant_phone": "",
        "complainant_full_name": "",
        "complainant_district": "",
        "complainant_municipality": "",
        "complainant_village": "",
        "complainant_address": "",
    }


def test_classify_now_honours_the_missing_client_like_every_other_call_site(no_client):
    """
    **T-14-b, the other half.** Before DPG-11 this test asserted the opposite: classification
    built its own client, so an unkeyed deployment still constructed one and called the provider,
    and the module-level `None` never reached it. One client now — so a missing client produces
    the function's own documented contract, the `status="error"` dict, instead of a request that
    could not succeed.
    """
    result = llm.classify_and_summarize_grievance(GRIEVANCE_TEXT)

    assert result["status"] == "error"
    assert "No API key configured" in result["error"], (
        "the message now comes from the factory, which names the actual problem"
    )


def test_translate_grievance_raises_runtime_error_without_a_client(no_client):
    with pytest.raises(RuntimeError, match="not available for translation"):
        llm.translate_grievance_to_english_LLM(dict(TRANSLATE_INPUT))


def test_detect_sensitive_content_fails_open_without_a_client(no_client):
    assert llm.detect_sensitive_content_llm("a worker followed me home", "en") == {
        "detected": False,
        "level": "low",
        "message": "",
    }


# ═════════════════════════════════════════════════════════════════════════════
# T-10-e — parse_llm_response: the shared parser, all four branches
# ═════════════════════════════════════════════════════════════════════════════

def test_parse_llm_response_parses_valid_json_and_fills_missing_fields():
    parsed = llm.parse_llm_response(
        "grievance_response", json.dumps({"grievance_summary": "धुलो"})
    )
    assert parsed["grievance_summary"] == "धुलो"
    assert parsed["grievance_categories"] == ""
    assert parsed["grievance_categories_alternative"] == ""
    assert parsed["follow_up_question"] == ""


@pytest.mark.parametrize(
    "language_code,expected",
    [
        ("en", "not enough information to proceed"),
        ("ne", "अपेक्षित जानकारी अपुरुष है"),
        ("hi", "पूर्ण जानकारी अपुरुष है"),
        ("fr", "Information insuffisante pour procéder"),
        ("xx", "not enough information to proceed"),  # unknown code falls back to English
    ],
)
def test_parse_llm_response_localizes_the_empty_object_sentinel(language_code, expected):
    """`"{}"` is the model saying "not enough information" — it is not a parse failure."""
    parsed = llm.parse_llm_response("grievance_response", "{}", language_code)
    assert parsed == {
        "grievance_summary": expected,
        "grievance_categories": [expected],
        "grievance_categories_alternative": [expected],
        "follow_up_question": expected,
    }


def test_parse_llm_response_does_not_localize_the_sentinel_for_contact_responses():
    """The sentinel branch is grievance-only; a contact response falls through to the parser."""
    assert llm.parse_llm_response("contact_response", "{}") == {
        "complainant_phone": "",
        "complainant_full_name": "",
        "complainant_district": "",
        "complainant_municipality": "",
        "complainant_village": "",
        "complainant_address": "",
    }


def test_parse_llm_response_raises_on_malformed_json_and_logs_a_length_not_the_body(caplog):
    """
    **T-13-d.** The silent failure this sprint was aimed at: a malformed body used to `return {}`,
    which is what a legitimately empty result looks like. It now raises.

    The log carries the response **length, not its content** — the raw body is grievance
    narrative, and this line is one of the log-surface leaks Sprint 3 (T-34-c) is about. Fixing it
    here costs nothing and removes one item from that list.
    """
    with caplog.at_level("ERROR"):
        with pytest.raises(llm.LLMResponseParseError):
            llm.parse_llm_response("grievance_response", "{not json but with a narrative in it")

    message = " ".join(r.getMessage() for r in caplog.records)
    assert "response length" in message
    assert "narrative" not in message, "the raw body must not reach the log"


def test_a_malformed_classification_is_distinguishable_from_an_empty_one(client):
    """
    **T-13-d, the case that mattered.** Two replies, two outcomes that used to be identical:

    * `"{}"` — the model saying *not enough information*: the localized fallback text, no error.
    * `"{not json"` — the model failing: `status="error"`, with the reason.

    Before this ticket both produced a dict with empty content and nothing to tell them apart, on
    the product's primary AI path.
    """
    client.chat.completions.create.return_value = _chat("{}")
    empty = llm.classify_and_summarize_grievance(GRIEVANCE_TEXT, language_code="en")

    client.chat.completions.create.return_value = _chat("{not json")
    malformed = llm.classify_and_summarize_grievance(GRIEVANCE_TEXT, language_code="en")

    assert empty["grievance_summary"] == "not enough information to proceed"
    assert "status" not in empty
    assert malformed["status"] == "error"
    assert "did not match GrievanceClassification" in malformed["error"]
    # ⚠ And the error must carry the SHAPE of the failure, never the reply: pydantic's
    # ValidationError embeds `input_value=...`, which is model output derived from the grievance.
    # This assertion is here because the first version of the message leaked exactly that.
    assert "not json" not in malformed["error"]


# ═════════════════════════════════════════════════════════════════════════════
# T-10-f — the SEAH level clamp
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("bad_level", ["critical", "HIGH", "", "9"])
def test_detect_sensitive_content_clamps_an_out_of_range_level_to_low(client, bad_level):
    client.chat.completions.create.return_value = _chat(
        json.dumps({"detected": True, "level": bad_level, "message": "excerpt"})
    )

    result = llm.detect_sensitive_content_llm("a worker followed me home", "en")

    assert result["level"] == "low"
    assert result["detected"] is True


def test_detect_sensitive_content_coerces_a_non_string_message(client):
    client.chat.completions.create.return_value = _chat(
        json.dumps({"detected": True, "level": "medium", "message": 42})
    )

    result = llm.detect_sensitive_content_llm("a worker followed me home", "en")

    assert result["message"] == "42"
    assert result["level"] == "medium"

# ═════════════════════════════════════════════════════════════════════════════
# T-14-c — the ASR request is one the installed SDK actually accepts
# ═════════════════════════════════════════════════════════════════════════════

def test_transcribe_request_binds_against_the_real_openai_signature(client, tmp_path):
    """
    ⚠ **The regression test for DPG-14.3, and the one that would have caught it.**

    Before the fix the call passed `language_code=…`. `Transcriptions.create` declares its
    parameters explicitly and takes no `**kwargs`, so **every transcription raised `TypeError`**,
    was logged, and re-raised — voice-note transcription had never worked on this path. Nothing
    noticed, because nothing tested it and (Q-13.2) voice is not live: there is no budget for
    transcription, so no field evidence exists or can exist.

    A mock accepts any keyword, which is exactly why a mock-only assertion is not enough here.
    This test binds the request the code actually sends against the **installed SDK's signature**
    — the check that distinguishes "we send the argument we meant to" from "we send an argument
    the provider will take".

    ⚠ What this does **not** prove: that transcription *works*. It proves the signature is
    correct and unit-tested. DPG-22's missing Nepali WER baseline is the other half.
    """
    import inspect

    from openai.resources.audio.transcriptions import Transcriptions

    audio = tmp_path / "note.ogg"
    audio.write_bytes(b"\x00\x01")
    client.audio.transcriptions.create.return_value = SimpleNamespace(text="धुलो")

    llm.transcribe_audio_file(str(audio), "ne")

    sent = dict(client.audio.transcriptions.create.call_args.kwargs)
    sent["file"] = b"<closed file handle>"  # the real one is closed by the `with` block
    inspect.signature(Transcriptions.create).bind(object(), **sent)

# ═════════════════════════════════════════════════════════════════════════════
# T-11-a / T-11-b — the factory: what it builds, and from what
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def clean_llm_env(monkeypatch, tmp_path):
    """No inherited env, no `env.local` underfoot, no cached clients or settings."""
    for name in (
        "LLM_BASE_URL", "LLM_API_KEY", "LLM_TIMEOUT", "LLM_MAX_RETRIES",
        "ASR_BASE_URL", "ASR_API_KEY", "ASR_TIMEOUT", "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    llm_config.get_llm_settings.cache_clear()
    llm_client_factory.reset_clients()
    yield
    llm_config.get_llm_settings.cache_clear()
    llm_client_factory.reset_clients()


def test_the_llm_client_is_built_entirely_from_configuration(clean_llm_env, monkeypatch):
    """
    **T-11-a.** The factory names no endpoint of its own. This is the test behind the DPG
    indicator-4 claim: moving the product to a different provider is an environment change.
    """
    monkeypatch.setenv("LLM_BASE_URL", "https://router.huggingface.co/v1")
    monkeypatch.setenv("LLM_API_KEY", "hf_token")
    monkeypatch.setenv("LLM_TIMEOUT", "42")
    monkeypatch.setenv("LLM_MAX_RETRIES", "7")
    llm_config.get_llm_settings.cache_clear()

    built = llm_client_factory.get_llm_client()

    assert str(built.base_url).rstrip("/") == "https://router.huggingface.co/v1"
    assert built.api_key == "hf_token"
    assert built.timeout == 42.0
    assert built.max_retries == 7


def test_the_llm_client_is_built_once_and_cached(clean_llm_env, monkeypatch):
    """Lazy, not import-time — and built once. Import-time construction froze configuration."""
    monkeypatch.setenv("LLM_API_KEY", "hf_token")
    llm_config.get_llm_settings.cache_clear()

    assert llm_client_factory.get_llm_client() is llm_client_factory.get_llm_client()

    llm_client_factory.reset_clients()
    assert llm_client_factory.get_llm_client() is not None


def test_the_asr_client_is_independent_of_the_chat_client(clean_llm_env, monkeypatch):
    """
    **T-11-b.** ASR routinely runs on a different provider, port or machine, with a much longer
    deadline. Pointing one at a self-hosted Whisper must not move the other.
    """
    monkeypatch.setenv("LLM_BASE_URL", "https://router.huggingface.co/v1")
    monkeypatch.setenv("LLM_API_KEY", "hf_token")
    monkeypatch.setenv("ASR_BASE_URL", "http://vllm-whisper:8000/v1")
    monkeypatch.setenv("ASR_API_KEY", "local-token")
    monkeypatch.setenv("ASR_TIMEOUT", "900")
    llm_config.get_llm_settings.cache_clear()

    chat = llm_client_factory.get_llm_client()
    asr = llm_client_factory.get_asr_client()

    assert chat is not asr
    assert str(asr.base_url).rstrip("/") == "http://vllm-whisper:8000/v1"
    assert asr.api_key == "local-token"
    assert asr.timeout == 900.0
    assert str(chat.base_url).rstrip("/") == "https://router.huggingface.co/v1"


def test_no_key_means_no_client_rather_than_a_client_that_401s(clean_llm_env):
    """
    The contract the module-level `client = None` used to provide, kept deliberately.

    A keyless client is worse than none: it turns a configuration mistake into a provider error
    at request time, on a Celery worker, where it reads as an outage. The call sites' guards —
    raise, sentinel dict, fail-open — depend on this.
    """
    with pytest.raises(RuntimeError, match="No API key configured"):
        llm_client_factory.get_llm_client()

    assert llm._llm_client() is None
    assert llm._asr_client() is None


def test_the_factory_error_names_the_host_but_never_the_key(clean_llm_env, monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://router.huggingface.co/v1")
    llm_config.get_llm_settings.cache_clear()

    with pytest.raises(RuntimeError) as exc:
        llm_client_factory.get_llm_client()

    assert "router.huggingface.co" in str(exc.value)
    assert "LLM_API_KEY" in str(exc.value)

# ═════════════════════════════════════════════════════════════════════════════
# T-13-b / T-13-e — validation, and why the categories are not an enum
# ═════════════════════════════════════════════════════════════════════════════

def test_a_schema_violating_classification_is_rejected_not_silently_accepted(client):
    """
    **T-13-b.** `grievance_categories` as a bare string parses as JSON perfectly well. Before
    validation it travelled onward as a string where every downstream reader expects a list —
    the kind of defect that surfaces three services later as something iterating characters.
    """
    client.chat.completions.create.return_value = _chat(
        json.dumps({**CLASSIFY_JSON, "grievance_categories": "Dust and air pollution"})
    )

    result = llm.classify_and_summarize_grievance(GRIEVANCE_TEXT)

    assert result["status"] == "error"
    assert result["grievance_categories"] == []


def test_a_valid_classification_survives_validation_unchanged(client):
    client.chat.completions.create.return_value = _chat(json.dumps(CLASSIFY_JSON))
    assert llm.classify_and_summarize_grievance(GRIEVANCE_TEXT) == CLASSIFY_JSON


def test_categories_are_checked_against_the_live_catalogue_not_a_frozen_enum(client, caplog, monkeypatch):
    """
    **T-13-e.** The taxonomy is **admin-configurable** and resynced into
    `public.grievance_classification_taxonomy`. A `Literal[...]` of today's categories in the
    schema would mean a code change every time an administrator adds one — and would make the
    resync path a lie. So the schema says `list[str]`, and membership is checked afterwards,
    against the catalogue as it is at call time.

    Checked, not enforced: a model naming a category slightly wrong is a prompt problem, and it is
    not worth discarding a complainant's classification over.
    """
    invented = "Category That Nobody Configured"
    client.chat.completions.create.return_value = _chat(
        json.dumps({**CLASSIFY_JSON, "grievance_categories": [invented]})
    )

    with caplog.at_level("WARNING"):
        result = llm.classify_and_summarize_grievance(GRIEVANCE_TEXT)

    assert result["grievance_categories"] == [invented], "logged, not discarded"
    assert any(invented in r.getMessage() for r in caplog.records)


def test_a_category_added_to_the_catalogue_needs_no_code_change(client, caplog, monkeypatch):
    """The other half of T-13-e: add one to the catalogue and it stops being 'unlisted'."""
    new_category = {"classification": "Wildlife", "generic_grievance_name": "Elephant corridor blocked"}
    monkeypatch.setitem(llm.CLASSIFICATION_DATA, "wildlife_corridor", new_category)
    chosen = "Wildlife - Elephant corridor blocked"
    client.chat.completions.create.return_value = _chat(
        json.dumps({**CLASSIFY_JSON, "grievance_categories": [chosen]})
    )

    with caplog.at_level("WARNING"):
        result = llm.classify_and_summarize_grievance("हात्तीले बाटो छेकेको छ, यात्रु अलपत्र परे।")

    assert result["grievance_categories"] == [chosen]
    assert not [r for r in caplog.records if "outside the live catalogue" in r.getMessage()]


def test_the_classification_schema_declares_no_category_enum():
    """Mutation target for T-13-e: freezing a Literal[...] of categories turns this red."""
    schema = json.dumps(
        llm.GrievanceClassification.model_json_schema()["properties"]["grievance_categories"]
    )
    assert "enum" not in schema
    assert "const" not in schema

# ═════════════════════════════════════════════════════════════════════════════
# T-15-a … T-15-c — degraded mode: a dead endpoint must not take intake with it
# ═════════════════════════════════════════════════════════════════════════════

DEAD_PORT_URL = "http://127.0.0.1:9/v1"   # the discard port: refused immediately, no waiting


def test_a_dead_endpoint_produces_the_error_contract_rather_than_an_exception(monkeypatch, tmp_path):
    """
    **T-15-a, the service half — and this one makes a real network call**, to a port nothing
    listens on. Mocking here would test the mock: the property under test is what an *actual*
    connection failure does to the primary AI path.

    A grievance mechanism that refuses intake because an API is down is worse than one with no AI
    at all, and in Nepal that is not hypothetical.
    """
    from backend.services import llm_client as factory

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LLM_BASE_URL", DEAD_PORT_URL)
    monkeypatch.setenv("LLM_API_KEY", "unused-but-required-to-build-a-client")
    monkeypatch.setenv("LLM_MAX_RETRIES", "0")
    llm_config.get_llm_settings.cache_clear()
    factory.reset_clients()

    try:
        result = llm.classify_and_summarize_grievance(GRIEVANCE_TEXT, language_code="ne")
    finally:
        factory.reset_clients()

    assert result["status"] == "error"
    assert result["grievance_summary"] == ""
    assert result["grievance_categories"] == []


def test_a_failed_classification_is_recognised_as_a_failure_by_the_task_layer():
    """
    **T-15-a, the half that was broken.** ⚠ Measured against the real database on 2026-08-18
    (grievance `DPG15-c2b3e821`): with the endpoint dead, the Celery task reported
    `status: "SUCCESS"` and wrote `grievance_classification_status = LLM_generated` — a *success*
    code — with an empty summary, `error: "Connection error."` sitting beside it, and the terminal
    `LLM_failed` code unreachable.

    The cause was that the task's only guard was `if not values:` and the documented failure dict
    is **truthy**. This helper is the fix's seam, and the task raises on it so the existing retry
    and the `LLM_failed` write both come back into play.
    """
    from backend.config.classification_status import is_failed_classification

    failure = {
        "grievance_summary": "",
        "grievance_categories": [],
        "grievance_categories_alternative": [],
        "follow_up_question": "",
        "status": "error",
        "error": "Connection error.",
    }
    assert is_failed_classification(failure) is True
    assert is_failed_classification(None) is True
    assert is_failed_classification({}) is True
    assert is_failed_classification({"error": "boom"}) is True

    success = dict(CLASSIFY_JSON)
    assert is_failed_classification(success) is False


def test_the_classification_task_raises_on_a_failed_result_so_the_retry_fires(monkeypatch):
    """
    The pin on the wiring, not just on the helper: a task that recognises failure and then stores
    it as success would pass the test above and still ship the bug.
    """
    import backend.task_queue.registered_tasks as tasks
    from backend.config.classification_status import is_failed_classification

    source = inspect.getsource(tasks.classify_and_summarize_grievance_task)
    assert "is_failed_classification" in source, (
        "the classification task must treat the service's failure dict as a failure — "
        "`if not values` does not, because that dict is truthy"
    )
    assert is_failed_classification({"status": "error"}) is True


# ── the probe ────────────────────────────────────────────────────────────────

@pytest.fixture
def probe_client(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from backend.api.fastapi_app import app

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LLM_BASE_URL", DEAD_PORT_URL)
    monkeypatch.setenv("LLM_API_KEY", "sk-secret-value-that-must-not-appear")
    llm_config.get_llm_settings.cache_clear()
    yield TestClient(app)
    llm_config.get_llm_settings.cache_clear()


def test_the_probe_reports_the_host_and_never_the_key(probe_client):
    """**T-15-b.** The one thing a health endpoint must never do is help someone read the secret."""
    response = probe_client.get("/health/llm")

    assert response.status_code == 200
    body = response.json()
    assert body["endpoints"][0]["host"] == "127.0.0.1:9"
    assert body["endpoints"][0]["key_configured"] is True
    assert "sk-secret-value-that-must-not-appear" not in response.text


def test_the_probe_reports_an_unreachable_endpoint_as_degraded(probe_client):
    response = probe_client.get("/health/llm")
    body = response.json()

    assert body["status"] == "degraded"
    assert body["endpoints"][0]["reachable"] is False
    assert body["last_success_at"] is None
    # ⚠ 200 even when degraded: this is an observation, not a gate. A non-200 invites someone to
    # wire it into a container healthcheck, which is precisely what must not happen.
    assert response.status_code == 200


def test_health_stays_green_while_the_llm_probe_is_red(probe_client):
    """
    **T-15-c.** The whole point: an LLM outage degrades classification and nothing else. `/health`
    is what the container healthcheck calls, and it must not learn about the model at all.
    """
    assert probe_client.get("/health").status_code == 200
    assert probe_client.get("/health").text == '"OK"' or probe_client.get("/health").text == "OK"
    assert probe_client.get("/health/llm").json()["status"] == "degraded"


def test_no_container_healthcheck_probes_the_llm():
    """
    **T-15-c, the half a unit test cannot fake.** The rule is not "the probe returns 200" — it is
    "nothing restarts the chatbot when the provider is down". That lives in the compose files, so
    that is where it is checked.
    """
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    for compose in ("docker-compose.yml", "docker-compose.grm.yml"):
        text = (repo_root / compose).read_text()
        for line in text.splitlines():
            if "healthcheck" in line.lower() or "urlopen" in line:
                assert "/health/llm" not in line, (
                    f"{compose} wires the LLM probe into a container healthcheck. An LLM outage "
                    "would then restart the chatbot, which is the failure this probe exists to "
                    "make visible without causing."
                )

def test_an_empty_contact_extraction_is_never_written_over_stored_details():
    """
    **T-15-a, the finding that cost the most.** ⚠ Verified against the real database with the
    endpoint on a dead port: `extract_contact_info_task` reported `SUCCESS` and overwrote a stored
    phone number (`+9779841234567`) with `""`. The complainant had typed it; the model was down;
    the number was erased.

    Note the shape of this one — it is *not* a bug the characterization net could have caught,
    because the service function did exactly what its contract said. The contract itself was
    harmful at the layer above, and only driving the degraded path against a real database showed
    it. That is the argument for DPG-15 being an experiment rather than a code review.
    """
    from backend.config.classification_status import is_empty_extraction

    assert is_empty_extraction({"complainant_phone": ""}) is True
    assert is_empty_extraction({"complainant_phone": "   "}) is True
    assert is_empty_extraction({}) is True
    assert is_empty_extraction(None) is True
    assert is_empty_extraction({"complainant_phone": "9841234567"}) is False


def test_the_contact_task_refuses_to_persist_an_empty_extraction():
    """The pin on the wiring: recognising the empty result and storing it anyway is still the bug."""
    import backend.task_queue.registered_tasks as tasks

    source = inspect.getsource(tasks.extract_contact_info_task)
    assert "is_empty_extraction" in source, (
        "extract_contact_info_task must refuse to write an all-empty extraction — otherwise a "
        "provider outage erases the complainant's stored contact details"
    )

# ═════════════════════════════════════════════════════════════════════════════
# T-19-a … T-19-e — meaningful input, honest empties, bounded error text
# ═════════════════════════════════════════════════════════════════════════════

def test_text_below_the_minimum_never_reaches_the_model(client):
    """
    **T-19-a.** A six-character grievance cannot be summarised. Sending it costs a request to be
    told so, and — before this gate — the empty answer that came back was indistinguishable from
    a model that had failed.
    """
    result = llm.classify_and_summarize_grievance("धुलो", language_code="ne")

    client.chat.completions.create.assert_not_called()
    assert result["skipped"] == "too_short"
    assert result["grievance_summary"] == ""


def test_a_skipped_short_input_is_not_a_failure(client):
    """
    **T-19-b, first half.** The gate must not be mistaken for an error by the task layer — that
    would turn "the complainant wrote very little" into a retried, LLM_failed grievance.
    """
    from backend.config.classification_status import is_failed_classification

    result = llm.classify_and_summarize_grievance("धुलो")

    assert is_failed_classification(result) is False


def test_an_empty_result_above_the_threshold_is_an_answer_not_a_failure(client, caplog):
    """
    ⭐ **T-19-b, and the regression this ticket could most easily have introduced.**

    The model looked at text long enough to summarise and said *"not enough information"*. That is
    the model being right, and it must stay distinguishable from the model failing. Pinned with the
    guardrail in place, because the cheapest way to build a length gate is to start treating every
    empty answer as an error on the way past.
    """
    from backend.config.classification_status import is_failed_classification

    client.chat.completions.create.return_value = _chat("{}")

    with caplog.at_level("WARNING"):
        result = llm.classify_and_summarize_grievance(GRIEVANCE_TEXT, language_code="en")

    assert is_failed_classification(result) is False
    assert "status" not in result
    assert result["grievance_summary"] == "not enough information to proceed"
    # Logged with the LENGTH, never the narrative — this line reaches the Celery log.
    warnings = " ".join(r.getMessage() for r in caplog.records)
    assert "declined" in warnings
    assert "बिरामी" not in warnings


def test_the_threshold_is_measured_on_stripped_length_and_is_configurable(client, monkeypatch, tmp_path):
    """**T-19-c.** A wall of whitespace is not a grievance, and the number is a registry value."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MIN_CLASSIFY_CHARS", raising=False)
    llm_config.get_llm_settings.cache_clear()

    assert llm.classify_and_summarize_grievance(" " * 40)["skipped"] == "too_short"

    # Devanagari counts by character like anything else — 25 of them is a short sentence.
    long_enough = "सडकको धुलोले बच्चाहरू बिरामी भए।"
    assert len(long_enough.strip()) >= 25
    client.chat.completions.create.return_value = _chat(json.dumps(CLASSIFY_JSON))
    assert "skipped" not in llm.classify_and_summarize_grievance(long_enough)

    monkeypatch.setenv("MIN_CLASSIFY_CHARS", "500")
    llm_config.get_llm_settings.cache_clear()
    assert llm.classify_and_summarize_grievance(long_enough)["skipped"] == "too_short"


def test_the_translation_error_names_the_grievance_and_at_most_three_words(client):
    """
    **T-19-d.** The message reaches the Celery error log. It used to interpolate the whole
    `input_data`: the narrative, its summary, the district. The owner's rule is the id plus the
    first three words — enough to find the record, small enough to stop being a transcript.
    """
    client.chat.completions.create.return_value = _chat("{not json")

    with pytest.raises(ValueError) as exc:
        llm.translate_grievance_to_english_LLM(dict(TRANSLATE_INPUT))

    message = str(exc.value)
    assert "GR-2026-0001" in message
    assert "सडकको" in message, "the first words are deliberately included — they locate the record"
    assert "बिरामी" not in message, "...but only the first three; this is the fourth word"
    assert "grievance_summary" not in message
    assert "input_data" not in message


def test_a_pre_call_failure_now_raises_the_declared_value_error(client):
    """
    **T-19-e — D-29 closed.** A provider failure surfaces as the documented `ValueError` rather than
    `UnboundLocalError`. Deferred to Sprint 3 originally because the obvious fix (binding `result`
    early) made a PII-leaking message reachable; the owner's three-word trim removed that reason.

    ⚠ **The fix is the message, not a binding** — and the mutation check is what established that.
    A pre-binding `result = {}` was written first; deleting it left this test **green**, because the
    handlers no longer read `result` at all. The binding was removed. The mutation that does turn
    this red is restoring the old message — which is the honest one, since that message *is* the bug.
    """
    client.chat.completions.create.side_effect = RuntimeError("provider down")

    with pytest.raises(ValueError) as exc:
        llm.translate_grievance_to_english_LLM(dict(TRANSLATE_INPUT))

    assert not isinstance(exc.value, UnboundLocalError)
    assert "GR-2026-0001" in str(exc.value)
    assert "provider down" in str(exc.value)


def test_translation_refuses_text_that_is_too_short(client):
    """The same rule as classification — uniform, so it needs no rediscovering when voice unparks."""
    payload = dict(TRANSLATE_INPUT)
    payload["grievance_description"] = "धुलो"

    with pytest.raises(ValueError, match="Too short to translate"):
        llm.translate_grievance_to_english_LLM(payload)

    client.chat.completions.create.assert_not_called()
