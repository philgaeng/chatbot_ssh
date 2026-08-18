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


def test_classify_sends_gpt_5_nano_with_no_response_format(client):
    """
    Call site 4 — the product's primary AI path.

    Two things pinned here and nowhere else: the model is `gpt-5-nano` (a deliberate cost choice,
    Q-13.1), and the request carries **no `response_format`** — it asks for "strict JSON" in the
    prompt and hopes. DPG-13 closes that.
    """
    client.chat.completions.create.return_value = _chat(json.dumps(CLASSIFY_JSON))

    llm.classify_and_summarize_grievance("सडकमा धुलो छ", language_code="ne")

    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-5-nano"
    assert "response_format" not in kwargs
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

    llm.classify_and_summarize_grievance("सडकमा धुलो छ")
    assert client.chat.completions.create.call_args.kwargs["timeout"] == 120.0

    monkeypatch.setenv("OPENAI_CLASSIFICATION_TIMEOUT", "45")
    llm_config.get_llm_settings.cache_clear()
    llm.classify_and_summarize_grievance("सडकमा धुलो छ")
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


def test_extract_all_contact_info_returns_an_empty_dict_on_a_malformed_body(client):
    """
    Not the same as the failure contract above: a malformed body reaches `parse_llm_response`,
    which swallows the `JSONDecodeError` and returns `{}` — so the caller cannot tell a parse
    failure from an empty extraction. DPG-13 is the ticket that removes this ambiguity.
    """
    client.chat.completions.create.return_value = _chat("{not json")

    assert llm.extract_all_contact_info(ALL_CONTACT_INPUT) == {}


def test_classify_returns_a_status_error_dict_when_the_call_fails(client):
    client.chat.completions.create.side_effect = RuntimeError("model not found for this account")

    result = llm.classify_and_summarize_grievance("सडकमा धुलो छ")

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
    """No API key configured → the factory raises → the helpers return None, as before DPG-11."""
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
    result = llm.classify_and_summarize_grievance("सडकमा धुलो छ")

    assert result["status"] == "error"
    assert "client initialization failed" in result["error"]


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
