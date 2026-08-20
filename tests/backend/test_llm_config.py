# SPDX-License-Identifier: Apache-2.0

"""
The shared LLM registry — DPG-17 (T-17-a), and the alias behaviour DPG-12 depends on (T-12-c).

`backend/config/llm_config.py` is the one place any model name, endpoint, timeout, retry count or
structured-output mode is declared, for **both** LLM surfaces. These tests pin that it resolves
today's values by default — the behaviour-preserving property that keeps DPG-10's characterization
net green through the migration — and that every value is overridable by its documented env var,
which is the property the DPG indicator-4 claim rests on.

⚠ **Isolation matters here.** `LLMSettings` reads `env.local` / `.env` from the working directory,
and the dev `env.local` really does set `OPENAI_API_KEY`. Every test below chdirs to a tmp
directory and clears the cache, so it measures the *declared defaults* rather than the developer's
machine. A test that silently read `env.local` would pass on a laptop and fail in CI, or worse.

Spec: docs/sprints/2026-08-llm/02-llm-agnostic-spec.md §DPG-17 · Ledger: TESTS.md T-17-a, T-12-c
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import BaseModel, Field

from backend.config import llm_config

ENV_VARS = (
    "LLM_BASE_URL", "LLM_API_KEY", "LLM_TIMEOUT", "LLM_MAX_RETRIES", "LLM_STRUCTURED_OUTPUT",
    "ASR_BASE_URL", "ASR_API_KEY", "ASR_TIMEOUT",
    "MODEL_CLASSIFY", "MODEL_EXTRACT", "MODEL_TRANSLATE", "MODEL_DETECT", "MODEL_ASR",
    "MODEL_TICKET_TRANSLATE", "MODEL_TICKET_FINDINGS", "MODEL_TICKET_FINDINGS_SEAH",
    "TIMEOUT_CLASSIFY", "TIMEOUT_TICKET",
    "STRUCTURED_CLASSIFY", "STRUCTURED_EXTRACT", "STRUCTURED_TRANSLATE", "STRUCTURED_DETECT",
    "STRUCTURED_TICKET_FINDINGS",
    "OPENAI_API_KEY", "OPENAI_CLASSIFICATION_TIMEOUT",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    """No inherited env, no `env.local` on the path, no cached settings."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    llm_config.get_llm_settings.cache_clear()
    llm_config._warned.clear()
    yield
    llm_config.get_llm_settings.cache_clear()
    llm_config._warned.clear()


# ═════════════════════════════════════════════════════════════════════════════
# T-17-a — every task key resolves, and every one is overridable
# ═════════════════════════════════════════════════════════════════════════════

# ✅ **Two models (Q-21).** Eight keys, two values: one for transcription, one for everything else.
# ⚠ What this replaced was not a decision but an accident — the Sept-2025 nano migration moved one
# call site of five, and the rest kept July-2025 models for eleven months because each name lived
# at its own call site. The keys stay so a task can be moved back without touching code.
TODAYS_MODELS = {
    "classify": "gpt-5-nano",
    "extract": "gpt-5-nano",
    "translate": "gpt-5-nano",
    "detect": "gpt-5-nano",
    "asr": "whisper-1",
    "ticket_translate": "gpt-5-nano",      # falls back to `translate`
    "ticket_findings": "gpt-5-nano",
    "ticket_findings_seah": "gpt-5-nano",
}


@pytest.mark.parametrize("task,model", sorted(TODAYS_MODELS.items()))
def test_every_task_resolves_to_todays_model_by_default(task, model):
    """
    Behaviour preservation is the whole point of shipping today's values as the defaults: the
    open-configuration flip is a Sprint-2 commit against this file (Q-10), not a side effect of
    introducing it. An open base URL with `gpt-4o` model ids serves nothing.
    """
    assert llm_config.model_for(task).model == model


@pytest.mark.parametrize(
    "task,env_var",
    [
        ("classify", "MODEL_CLASSIFY"),
        ("extract", "MODEL_EXTRACT"),
        ("translate", "MODEL_TRANSLATE"),
        ("detect", "MODEL_DETECT"),
        ("asr", "MODEL_ASR"),
        ("ticket_translate", "MODEL_TICKET_TRANSLATE"),
        ("ticket_findings", "MODEL_TICKET_FINDINGS"),
        ("ticket_findings_seah", "MODEL_TICKET_FINDINGS_SEAH"),
    ],
)
def test_every_task_model_is_overridable_by_its_documented_env_var(task, env_var, monkeypatch):
    monkeypatch.setenv(env_var, "openai/gpt-oss-120b:groq")
    llm_config.get_llm_settings.cache_clear()

    assert llm_config.model_for(task).model == "openai/gpt-oss-120b:groq"


def test_ticket_translate_follows_translate_unless_it_is_given_its_own_model(monkeypatch):
    """One knob moves translation on both surfaces; a second exists for when they must differ."""
    monkeypatch.setenv("MODEL_TRANSLATE", "qwen/qwen3-32b")
    llm_config.get_llm_settings.cache_clear()
    assert llm_config.model_for("ticket_translate").model == "qwen/qwen3-32b"

    monkeypatch.setenv("MODEL_TICKET_TRANSLATE", "meta-llama/llama-3.3-70b")
    llm_config.get_llm_settings.cache_clear()
    assert llm_config.model_for("ticket_translate").model == "meta-llama/llama-3.3-70b"
    assert llm_config.model_for("translate").model == "qwen/qwen3-32b"


def test_an_unknown_task_key_names_the_known_ones_and_says_where_to_add_it():
    """The error is the documentation: a call site must not invent a task key locally."""
    with pytest.raises(KeyError) as exc:
        llm_config.model_for("summarise_everything")

    message = str(exc.value)
    assert "summarise_everything" in message
    assert "ticket_findings_seah" in message
    assert "llm_config.py" in message


def test_findings_task_is_the_seah_ternary_and_the_split_stays_configurable(monkeypatch):
    """
    **T-12-b, restated by Q-21.** The split was `gpt-4o-mini` / `gpt-4o` — a deliberate
    cost/quality decision. Consolidating points both at one model, so the assertion moves from
    *"they resolve to different models"* to *"they are independently overridable"*: the split
    survives as **configuration**, and DPG-23 can re-open it with measurements instead of a
    code change.
    """
    assert llm_config.findings_task(is_seah=False) == "ticket_findings"
    assert llm_config.findings_task(is_seah=True) == "ticket_findings_seah"

    monkeypatch.setenv("MODEL_TICKET_FINDINGS_SEAH", "gpt-4o")
    llm_config.get_llm_settings.cache_clear()

    standard = llm_config.model_for(llm_config.findings_task(False)).model
    seah = llm_config.model_for(llm_config.findings_task(True)).model
    assert seah == "gpt-4o" and standard == "gpt-5-nano", (
        "one env var must re-open the split without touching code"
    )


# ═════════════════════════════════════════════════════════════════════════════
# The endpoints
# ═════════════════════════════════════════════════════════════════════════════

def test_the_chat_endpoint_defaults_to_openai_and_is_moved_by_one_variable(monkeypatch):
    assert llm_config.llm_endpoint().base_url == "https://api.openai.com/v1"

    monkeypatch.setenv("LLM_BASE_URL", "https://router.huggingface.co/v1")
    llm_config.get_llm_settings.cache_clear()
    assert llm_config.llm_endpoint().base_url == "https://router.huggingface.co/v1"


def test_the_asr_endpoint_falls_back_to_the_chat_endpoint_but_can_be_moved_alone(monkeypatch):
    """ASR commonly runs on a different port or provider — and its timeout is much higher."""
    monkeypatch.setenv("LLM_BASE_URL", "https://router.huggingface.co/v1")
    llm_config.get_llm_settings.cache_clear()
    assert llm_config.asr_endpoint().base_url == "https://router.huggingface.co/v1"

    monkeypatch.setenv("ASR_BASE_URL", "http://vllm-whisper:8000/v1")
    monkeypatch.setenv("ASR_TIMEOUT", "900")
    llm_config.get_llm_settings.cache_clear()

    asr = llm_config.asr_endpoint()
    assert asr.base_url == "http://vllm-whisper:8000/v1"
    assert asr.timeout == 900.0
    assert llm_config.llm_endpoint().base_url == "https://router.huggingface.co/v1"
    assert llm_config.model_for("asr").endpoint.base_url == "http://vllm-whisper:8000/v1"


def test_the_endpoint_host_property_never_carries_the_key():
    """`/health/llm` (DPG-15) reports the host. The key must not be derivable from what it prints."""
    endpoint = llm_config.Endpoint(
        base_url="https://router.huggingface.co/v1",
        api_key="hf_secret_value",
        timeout=30.0,
        max_retries=2,
        structured_output="json_object",
    )
    assert endpoint.host == "router.huggingface.co"
    assert "hf_secret_value" not in endpoint.host


def test_task_timeouts_preserve_todays_behaviour(monkeypatch):
    """
    Classification had its own 120 s budget and ticketing's client its own 30 s; everything else
    ran on the SDK default. All three survive the move, as per-task values rather than literals.
    """
    assert llm_config.model_for("classify").timeout == 120.0
    assert llm_config.model_for("ticket_findings").timeout == 30.0
    assert llm_config.model_for("translate").timeout == llm_config.DEFAULT_SDK_TIMEOUT

    monkeypatch.setenv("TIMEOUT_CLASSIFY", "45")
    llm_config.get_llm_settings.cache_clear()
    assert llm_config.model_for("classify").timeout == 45.0


def test_retries_and_the_endpoint_structured_output_ceiling_are_configuration(monkeypatch):
    assert llm_config.llm_endpoint().max_retries == 2
    assert llm_config.llm_endpoint().structured_output == "json_schema"

    monkeypatch.setenv("LLM_MAX_RETRIES", "5")
    monkeypatch.setenv("LLM_STRUCTURED_OUTPUT", "json_object")
    llm_config.get_llm_settings.cache_clear()

    assert llm_config.llm_endpoint().max_retries == 5
    assert llm_config.llm_endpoint().structured_output == "json_object"


# ═════════════════════════════════════════════════════════════════════════════
# T-13-a / T-13-c — the structured-output ladder
# ═════════════════════════════════════════════════════════════════════════════

# ✅ **Every text task is on gpt-5-nano now (Q-21), so every one gets `json_schema`.** That is the
# second dividend of consolidating: three of the four sites on a weaker rung were there because of
# the MODEL, not the endpoint, and the ladder goes back to being what it was designed as — a
# provider fallback for the open configuration rather than a workaround for four OpenAI vintages.
# The per-model measurements that produced these rungs are pinned in `test_the_profile_...` below.
MEASURED_CAPABILITY = {
    "classify": "json_schema",
    "extract": "json_schema",
    "detect": "json_schema",
    "translate": "json_schema",
    "ticket_findings": "json_schema",
    "ticket_findings_seah": "json_schema",
}


@pytest.mark.parametrize("task,mode", sorted(MEASURED_CAPABILITY.items()))
def test_each_task_declares_what_its_model_can_actually_do(task, mode):
    """
    **T-13-a.** ⚠ Capability is a property of the **(endpoint, model) pair**, not of the endpoint
    — the spec assumed otherwise, and an endpoint-only flag would have sent `json_schema` to
    `gpt-3.5-turbo` and `json_object` to `gpt-4`, both of which answer 400. Each row above was
    measured with one request per cell before this default was written.
    """
    assert llm_config.model_for(task).structured_output == mode


def test_the_endpoint_ceiling_clamps_every_task_down_at_once(monkeypatch):
    """
    **T-13-c.** The ladder degrades; it never guesses upward. Pointing at an endpoint that only
    does `json_object` must not leave the classification path asking for a schema — this is the
    one knob that moves every site, which is why DPG-24's CI job can run against providers with
    weaker support instead of the test being weakened to suit them.
    """
    monkeypatch.setenv("LLM_STRUCTURED_OUTPUT", "json_object")
    llm_config.get_llm_settings.cache_clear()
    assert llm_config.model_for("classify").structured_output == "json_object"
    assert llm_config.model_for("extract").structured_output == "json_object"

    monkeypatch.setenv("LLM_STRUCTURED_OUTPUT", "prompt")
    llm_config.get_llm_settings.cache_clear()
    assert llm_config.model_for("classify").structured_output == "prompt"
    assert llm_config.model_for("ticket_findings").structured_output == "prompt"


def test_a_task_capability_follows_its_model_and_can_still_be_overridden(monkeypatch):
    """
    Capability derives from the model (DPG-18's profile), so moving one task to a weaker model
    lowers only that task — and an explicit `STRUCTURED_*` remains as the escape hatch for a
    provider whose profile we have wrong.
    """
    monkeypatch.setenv("MODEL_TRANSLATE", "gpt-3.5-turbo")
    llm_config.get_llm_settings.cache_clear()
    assert llm_config.model_for("translate").structured_output == "json_object"
    assert llm_config.model_for("extract").structured_output == "json_schema"

    monkeypatch.setenv("STRUCTURED_TRANSLATE", "prompt")
    llm_config.get_llm_settings.cache_clear()
    assert llm_config.model_for("translate").structured_output == "prompt"


def test_free_text_tasks_never_ask_for_json():
    """ASR and note translation return prose. A `response_format` on either is a bug."""
    assert llm_config.model_for("asr").structured_output == "prompt"
    assert llm_config.model_for("ticket_translate").structured_output == "prompt"
    assert llm_config.response_format_kwargs("asr", None, "prompt") == {}


def test_the_prompt_rung_sends_no_response_format_key_at_all():
    """
    Not `response_format=None`: the SDK serialises an explicit None into the body, and a provider
    that has never heard of the parameter is entitled to reject it. The weakest rung must produce
    the request this code sent before the ladder existed.
    """
    assert llm_config.response_format_kwargs("x", {"type": "object"}, "prompt") == {}
    assert llm_config.response_format_kwargs("x", {"type": "object"}, "json_object") == {
        "response_format": {"type": "json_object"}
    }


def test_a_schema_is_made_strict_before_it_is_sent():
    """
    Strict mode requires `additionalProperties: false` and every property listed as required, at
    every level — Pydantic emits neither, because they are not what JSON Schema means by
    "required". Providers reject a schema that claims `strict: true` without them.
    """
    schema = {
        "type": "object",
        "properties": {
            "a": {"type": "string"},
            "nested": {"type": "object", "properties": {"b": {"type": "string"}}},
        },
        "required": ["a"],
    }

    out = llm_config.response_format_kwargs("t", schema, "json_schema")["response_format"]

    assert out["json_schema"]["strict"] is True
    body = out["json_schema"]["schema"]
    assert body["additionalProperties"] is False
    assert sorted(body["required"]) == ["a", "nested"]
    assert body["properties"]["nested"]["additionalProperties"] is False
    assert body["properties"]["nested"]["required"] == ["b"]
    assert schema["required"] == ["a"], "the caller's schema must not be mutated"


def test_the_mode_used_is_logged(caplog):
    """A provider that silently ignores json_schema and one that never received it look the same."""
    with caplog.at_level("DEBUG", logger="backend.config.llm_config"):
        llm_config.response_format_kwargs("case_findings", {"type": "object"}, "json_object")

    assert any(
        "case_findings" in r.getMessage() and "json_object" in r.getMessage()
        for r in caplog.records
    )


def test_an_unsupported_structured_output_mode_is_rejected_at_load(monkeypatch):
    """A typo here would silently degrade every structured call site. Fail at boot instead."""
    import pydantic

    monkeypatch.setenv("LLM_STRUCTURED_OUTPUT", "json-schema")
    llm_config.get_llm_settings.cache_clear()

    with pytest.raises(pydantic.ValidationError):
        llm_config.get_llm_settings()


# ═════════════════════════════════════════════════════════════════════════════
# T-12-c — the deprecated aliases, resolved once and warned about once
# ═════════════════════════════════════════════════════════════════════════════

def test_the_legacy_openai_key_still_authenticates_both_surfaces(monkeypatch):
    """
    A deployment whose `env.local` predates this sprint must keep working. The alias is honoured
    on **both** endpoints — a key that authenticated chat but not ASR would be a worse failure
    than none, because it would look like a model problem.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "sk-legacy")
    llm_config.get_llm_settings.cache_clear()

    assert llm_config.llm_endpoint().api_key == "sk-legacy"
    assert llm_config.asr_endpoint().api_key == "sk-legacy"


def test_the_new_name_wins_when_both_are_set(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-legacy")
    monkeypatch.setenv("LLM_API_KEY", "hf_new")
    llm_config.get_llm_settings.cache_clear()

    assert llm_config.llm_endpoint().api_key == "hf_new"


def test_a_deprecated_alias_warns_exactly_once(monkeypatch, caplog):
    """
    ⚠ Warn, do not fail. The alternative — refusing an old variable name — turns a documentation
    problem into an intake outage. But warn *once*: a per-call warning on a Celery worker is
    noise, and noise is how the next real warning gets missed.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "sk-legacy")
    monkeypatch.setenv("OPENAI_CLASSIFICATION_TIMEOUT", "90")
    llm_config.get_llm_settings.cache_clear()

    with caplog.at_level("WARNING", logger="backend.config.llm_config"):
        llm_config.get_llm_settings()
        llm_config.get_llm_settings.cache_clear()
        llm_config.get_llm_settings()

    deprecation_warnings = [r for r in caplog.records if "deprecated" in r.getMessage()]
    assert len(deprecation_warnings) == 2, "one per alias, not one per resolution"
    assert {"OPENAI_API_KEY", "OPENAI_CLASSIFICATION_TIMEOUT"} == {
        r.getMessage().split()[0] for r in deprecation_warnings
    }
    assert not any("sk-legacy" in r.getMessage() for r in caplog.records)


def test_no_alias_warning_when_the_new_name_is_used(monkeypatch, caplog):
    monkeypatch.setenv("LLM_API_KEY", "hf_new")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-legacy")
    llm_config.get_llm_settings.cache_clear()

    with caplog.at_level("WARNING", logger="backend.config.llm_config"):
        llm_config.get_llm_settings()

    assert not [r for r in caplog.records if "deprecated" in r.getMessage()]


def test_declared_env_vars_covers_every_setting_the_registry_reads():
    """DPG-16 generates `.env.example` from this rather than restating the list beside it."""
    declared = llm_config.declared_env_vars()

    assert "LLM_BASE_URL" in declared
    assert "MODEL_TICKET_FINDINGS_SEAH" in declared
    assert len(declared) == len(llm_config.LLMSettings.model_fields)
    assert all(name == name.upper() for name in declared)
    # Deprecated names are honoured but never advertised as configuration.
    assert "OPENAI_API_KEY" not in declared
    assert "OPENAI_API_KEY" in llm_config.deprecated_env_vars()

# ═════════════════════════════════════════════════════════════════════════════
# T-18-b … T-18-f — the call layer: shaping, profiles, and truncation
# ═════════════════════════════════════════════════════════════════════════════

class _Schema(BaseModel):
    summary: str = ""
    findings: list[str] = Field(default_factory=list)


def _reply(content, finish_reason="stop"):
    return SimpleNamespace(
        choices=[SimpleNamespace(
            finish_reason=finish_reason,
            message=SimpleNamespace(content=content),
        )]
    )


def test_the_prompt_rung_states_the_shape_in_words_generated_from_the_schema(monkeypatch):
    """
    **T-18-b.** When the model has no JSON mode at all — `gpt-4` answers 400 to both kinds — the
    requirement has to travel in the prompt. Generating that paragraph from the same schema the
    `json_schema` rung would send is what stops the two descriptions drifting apart, which is what
    nine hand-written "return strict JSON" paragraphs had already done.
    """
    monkeypatch.setenv("MODEL_TRANSLATE", "gpt-4")
    llm_config.get_llm_settings.cache_clear()

    request = llm_config.request_for(
        "translate",
        [{"role": "system", "content": "You translate."}, {"role": "user", "content": "text"}],
        schema=_Schema.model_json_schema(),
    )

    assert "response_format" not in request, "gpt-4 rejects both JSON modes — measured"
    system = request["messages"][0]["content"]
    assert "You translate." in system, "the call site's own prompt survives"
    for field in ("summary", "findings"):
        assert field in system, "every declared field must be named in the generated instruction"


def test_the_prompt_rung_adds_a_system_message_when_there_is_none(monkeypatch):
    monkeypatch.setenv("MODEL_TRANSLATE", "gpt-4")   # the one model with no JSON mode at all
    llm_config.get_llm_settings.cache_clear()

    request = llm_config.request_for(
        "translate", [{"role": "user", "content": "text"}], schema=_Schema.model_json_schema(),
    )
    assert request["messages"][0]["role"] == "system"


@pytest.mark.parametrize(
    "model,expects_temperature,cap_param,overhead",
    [
        ("gpt-5-nano", False, "max_completion_tokens", 4000),
        ("gpt-4o-mini", True, "max_tokens", 0),
        ("gpt-3.5-turbo", True, "max_tokens", 0),
        # ⭐ Measured 2026-08-20 (DPG-21). This row said `0` and `# unknown → conservative default`
        # until the probe ran — and the default's zero was the D-40 trap waiting for the open
        # configuration, because `.env.open` ships gpt-oss as the default open model and gpt-oss
        # reasons. The provider-suffixed id is deliberate: `:groq` must not defeat the prefix match.
        ("openai/gpt-oss-120b:groq", True, "max_tokens", 1000),
        # …and a genuinely unrecognised id keeps the fall-through pinned, which is what the row
        # above used to do. A DPG-23 candidate, so it is a real id rather than a made-up one.
        ("Qwen/Qwen3.5-27B", True, "max_tokens", 0),
    ],
)
def test_the_request_is_shaped_to_what_the_model_accepts(
    model, expects_temperature, cap_param, overhead, monkeypatch
):
    """
    ⭐ **T-18-e — the profile pin (D-40).** The call site asks for the same thing every time; the
    layer decides what the model can be *told*. Each row below is a 400 or an empty reply on some
    model this product already calls:

    * `gpt-5-nano` rejects any `temperature` but its default, and rejects `max_tokens` by name;
    * a cap sized for the visible output returns **empty content**, because reasoning spends it first.
    * ⭐ **and the open models reason too** — gpt-oss carries a measured 1,000-token floor. Before
      DPG-21 probed it, it fell through to an overhead of **0**, which is the same shape as D-40 on
      the configuration this repository advertises as its open one. The last row keeps the
      fall-through itself pinned, so adding a profile never silently removes the safe default.
    """
    monkeypatch.setenv("MODEL_CLASSIFY", model)
    llm_config.get_llm_settings.cache_clear()

    request = llm_config.request_for(
        "classify",
        [{"role": "user", "content": "x"}],
        schema=_Schema.model_json_schema(),
        temperature=0.0,
        max_output_tokens=400,
    )

    assert ("temperature" in request) is expects_temperature
    assert request[cap_param] == 400 + overhead
    assert cap_param == "max_completion_tokens" or "max_completion_tokens" not in request


def test_a_truncated_reply_is_a_failure_not_an_empty_answer():
    """
    ⭐ **T-18-f.** `finish_reason: "length"` arrives as HTTP 200 with empty content. Every parse
    path in this repository used to read that as *the model had nothing to say* — and on the
    resolved-case-summary path that means `generation_status = "llm_failed"`, which nothing
    retries, so a complainant is told their case is closed and never receives the document.
    """
    with pytest.raises(llm_config.LLMTruncatedError):
        llm_config.parse_response(_reply("", finish_reason="length"), _Schema)

    # …and it is refused even when the truncated body happens to be parseable.
    with pytest.raises(llm_config.LLMTruncatedError):
        llm_config.parse_response(_reply('{"summary": "half a th', finish_reason="length"), _Schema)


def test_parse_response_reads_what_providers_actually_send():
    """**T-18-c.** A bare object, and the fenced form that models without JSON mode produce."""
    assert llm_config.parse_response(_reply('{"summary": "ok"}'), _Schema).summary == "ok"
    assert llm_config.parse_response(_reply('```json\n{"summary": "ok"}\n```'), _Schema).summary == "ok"
    assert llm_config.parse_response(_reply("plain text"), None) == "plain text"


def test_an_unparseable_reply_raises_and_carries_no_content():
    """
    ⚠ The error names the **shape** of the failure, never the reply. Pydantic's ValidationError
    embeds `input_value=…` — model output derived from the grievance narrative — and this message
    travels into a `status="error"` payload and the Celery log.
    """
    with pytest.raises(llm_config.LLMParseError) as exc:
        llm_config.parse_response(_reply('{"summary": ["a list where prose belongs"]}'), _Schema)

    message = str(exc.value)
    assert "_Schema" in message and "summary" in message
    assert "a list where prose belongs" not in message


def test_one_task_key_change_moves_every_call_site_that_uses_it(monkeypatch):
    """**T-18-d.** The consolidation of §18.2 is a config edit, and this is why."""
    monkeypatch.setenv("MODEL_CLASSIFY", "qwen/qwen3-32b")
    llm_config.get_llm_settings.cache_clear()

    first = llm_config.request_for("classify", [{"role": "user", "content": "a"}])
    second = llm_config.request_for("classify", [{"role": "user", "content": "b"}])

    assert first["model"] == second["model"] == "qwen/qwen3-32b"
