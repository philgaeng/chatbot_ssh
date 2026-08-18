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

* `extract_contact_info` raises **`UnboundLocalError`** — not `{field_name: ""}` — when the failure
  happens before `response` is bound (deviation **D-27**).
* `translate_grievance_to_english_LLM` raises **`UnboundLocalError`** — not `ValueError` — when the
  failure happens before `result` is bound (deviation **D-28**, found while writing this file).

⚠ **The mock boundary is the `OpenAI` class, not the module-level `client`.**
`classify_and_summarize_grievance` builds its **own** client, shadowing the module attribute; a test
that patches only `LLM_services.client` never touches the product's primary classification path.
DPG-11 collapses that asymmetry — which is why the pin has to exist before it.

Spec: docs/sprints/2026-08-llm/02-llm-agnostic-spec.md §DPG-10 · Ledger: TESTS.md T-10-a … T-10-f
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.services import LLM_services as llm


# ── helpers ──────────────────────────────────────────────────────────────────

def _chat(content: str) -> SimpleNamespace:
    """A minimal stand-in for openai's ChatCompletion — only what the code reads."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


@pytest.fixture
def client(monkeypatch) -> MagicMock:
    """Replace the module-level client. Covers every call site except classification."""
    fake = MagicMock()
    monkeypatch.setattr(llm, "client", fake)
    return fake


class _OpenAIFactory:
    """
    Stands in for the `OpenAI` class so the client built *inside*
    `classify_and_summarize_grievance` is intercepted. Set `.response` (or `.error`) before
    calling the function; read `.built` afterwards for the construction kwargs.
    """

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
    monkeypatch.setattr(llm, "OpenAI", factory)
    return factory


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
    """Call site 1. ⚠ The language kwarg is `language_code` today — the defect DPG-14.3 fixes."""
    audio = tmp_path / "note.ogg"
    audio.write_bytes(b"\x00\x01")
    client.audio.transcriptions.create.return_value = SimpleNamespace(text="धुलो")

    assert llm.transcribe_audio_file(str(audio), "ne") == "धुलो"

    kwargs = client.audio.transcriptions.create.call_args.kwargs
    assert kwargs["model"] == "whisper-1"
    assert kwargs["language_code"] == "ne"


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


def test_classify_sends_gpt_5_nano_with_no_response_format(openai_class):
    """
    Call site 4 — the product's primary AI path.

    Two things pinned here and nowhere else: the model is `gpt-5-nano` (a deliberate cost choice,
    Q-13.1), and the request carries **no `response_format`** — it asks for "strict JSON" in the
    prompt and hopes. DPG-13 closes that.
    """
    openai_class.response = _chat(json.dumps(CLASSIFY_JSON))

    llm.classify_and_summarize_grievance("सडकमा धुलो छ", language_code="ne")

    assert len(openai_class.built) == 1, "classification builds its own client — the shadow client"
    assert openai_class.last_request["model"] == "gpt-5-nano"
    assert "response_format" not in openai_class.last_request
    assert [m["role"] for m in openai_class.last_request["messages"]] == ["system", "user"]


def test_classify_builds_its_own_client_with_the_classification_timeout(openai_class, monkeypatch):
    """The shadow client's timeout is OPENAI_CLASSIFICATION_TIMEOUT, defaulting to 120s."""
    monkeypatch.delenv("OPENAI_CLASSIFICATION_TIMEOUT", raising=False)
    llm.classify_and_summarize_grievance("सडकमा धुलो छ")
    assert openai_class.built[-1].build_kwargs["timeout"] == 120.0

    monkeypatch.setenv("OPENAI_CLASSIFICATION_TIMEOUT", "45")
    llm.classify_and_summarize_grievance("सडकमा धुलो छ")
    assert openai_class.built[-1].build_kwargs["timeout"] == 45.0


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


def test_classify_returns_the_four_documented_keys(openai_class):
    openai_class.response = _chat(json.dumps(CLASSIFY_JSON))
    result = llm.classify_and_summarize_grievance("सडकमा धुलो छ", language_code="ne")
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


def test_extract_contact_info_raises_unbound_local_error_when_the_call_fails(client):
    """
    ⚠ **D-27 — the declared contract is not what callers get.**

    The handler reads `if not response:` but `response` is only bound *after* the API call, so any
    exception raised before that line — a provider failure, a missing field_name — surfaces as
    `UnboundLocalError` from inside the `except`. The documented `{field_name: ""}` is unreachable
    on this path. Pinned as-is; the fix and its own test belong to DPG-14.
    """
    client.chat.completions.create.side_effect = RuntimeError("provider down")

    with pytest.raises(UnboundLocalError):
        llm.extract_contact_info({"complainant_phone": "9841234567"})


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


def test_extract_all_contact_info_returns_an_empty_dict_on_a_malformed_body(client):
    """
    Not the same as the failure contract above: a malformed body reaches `parse_llm_response`,
    which swallows the `JSONDecodeError` and returns `{}` — so the caller cannot tell a parse
    failure from an empty extraction. DPG-13 is the ticket that removes this ambiguity.
    """
    client.chat.completions.create.return_value = _chat("{not json")

    assert llm.extract_all_contact_info(ALL_CONTACT_INPUT) == {}


def test_classify_returns_a_status_error_dict_when_the_call_fails(openai_class):
    openai_class.error = RuntimeError("model not found for this account")

    result = llm.classify_and_summarize_grievance("सडकमा धुलो छ")

    assert result["status"] == "error"
    assert "model not found" in result["error"]
    assert result["grievance_summary"] == ""
    assert result["grievance_categories"] == []
    assert result["grievance_categories_alternative"] == []
    assert result["follow_up_question"] == ""


def test_classify_short_circuits_on_empty_text_without_calling_the_model(openai_class):
    """The empty-text guard returns *five* keys — no `follow_up_question`, unlike the error path."""
    result = llm.classify_and_summarize_grievance("")

    assert openai_class.built == []
    assert result == {
        "grievance_summary": "",
        "grievance_categories": [],
        "grievance_categories_alternative": [],
        "status": "error",
        "error": "No grievance text provided",
    }


def test_translate_grievance_raises_unbound_local_error_when_the_call_fails(client):
    """
    ⚠ **D-28 — the same shape of defect as D-27, in the translation path.**

    The handler interpolates `result` into its `ValueError` message, but `result` is bound *after*
    the API call. A provider failure therefore raises `UnboundLocalError`, not the documented
    `ValueError`. Callers catching `ValueError` do not catch this.

    It also means the *documented* failure message — which interpolates the whole `input_data`,
    grievance narrative included — is only reachable on the malformed-JSON path below. That
    interpolation is a Sprint-3 concern (T-34-b); it is recorded here, not fixed here.
    """
    client.chat.completions.create.side_effect = RuntimeError("provider down")

    with pytest.raises(UnboundLocalError):
        llm.translate_grievance_to_english_LLM(dict(TRANSLATE_INPUT))


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
    """`OPENAI_API_KEY` unset → the module-level client is None (LLM_services.py lines 31-36)."""
    monkeypatch.setattr(llm, "client", None)


def test_transcribe_raises_runtime_error_without_a_client(no_client, tmp_path):
    audio = tmp_path / "note.ogg"
    audio.write_bytes(b"\x00")

    with pytest.raises(RuntimeError, match="not available for transcription"):
        llm.transcribe_audio_file(str(audio), "ne")


def test_extract_contact_info_raises_unbound_local_error_without_a_client(no_client):
    """⚠ D-27 again: the guard raises `ValueError`, and the handler turns it into this."""
    with pytest.raises(UnboundLocalError):
        llm.extract_contact_info({"complainant_phone": "9841234567"})


def test_extract_all_contact_info_returns_the_sentinel_without_a_client(no_client):
    assert llm.extract_all_contact_info(ALL_CONTACT_INPUT) == {
        "complainant_phone": "",
        "complainant_full_name": "",
        "complainant_district": "",
        "complainant_municipality": "",
        "complainant_village": "",
        "complainant_address": "",
    }


def test_classify_ignores_the_module_client_entirely(no_client, openai_class):
    """
    ⚠ The reason the mock boundary is the class. Classification builds its own client, so the
    module-level `None` never reaches it: with no key configured this path still constructs a
    client and calls the provider. DPG-11 removes the shadow.
    """
    openai_class.response = _chat(json.dumps(CLASSIFY_JSON))

    assert llm.classify_and_summarize_grievance("सडकमा धुलो छ") == CLASSIFY_JSON
    assert len(openai_class.built) == 1


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


def test_parse_llm_response_returns_an_empty_dict_on_malformed_json():
    """
    ⚠ The silent failure this sprint is aimed at: a malformed body and a legitimately empty result
    are indistinguishable to every caller. DPG-13 makes them distinguishable.
    """
    assert llm.parse_llm_response("grievance_response", "{not json") == {}


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
