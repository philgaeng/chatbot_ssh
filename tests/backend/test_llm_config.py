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

import pytest

from backend.config import llm_config

ENV_VARS = (
    "LLM_BASE_URL", "LLM_API_KEY", "LLM_TIMEOUT", "LLM_MAX_RETRIES", "LLM_STRUCTURED_OUTPUT",
    "ASR_BASE_URL", "ASR_API_KEY", "ASR_TIMEOUT",
    "MODEL_CLASSIFY", "MODEL_EXTRACT", "MODEL_TRANSLATE", "MODEL_DETECT", "MODEL_ASR",
    "MODEL_TICKET_TRANSLATE", "MODEL_TICKET_FINDINGS", "MODEL_TICKET_FINDINGS_SEAH",
    "TIMEOUT_CLASSIFY", "TIMEOUT_TICKET",
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

TODAYS_MODELS = {
    "classify": "gpt-5-nano",
    "extract": "gpt-3.5-turbo",
    "translate": "gpt-4",
    "detect": "gpt-3.5-turbo",
    "asr": "whisper-1",
    "ticket_translate": "gpt-4",           # falls back to `translate`
    "ticket_findings": "gpt-4o-mini",
    "ticket_findings_seah": "gpt-4o",
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


def test_findings_task_is_the_seah_ternary_and_it_maps_to_two_distinct_models():
    assert llm_config.findings_task(is_seah=False) == "ticket_findings"
    assert llm_config.findings_task(is_seah=True) == "ticket_findings_seah"

    standard = llm_config.model_for(llm_config.findings_task(False)).model
    seah = llm_config.model_for(llm_config.findings_task(True)).model
    assert standard != seah, "the standard/SEAH split is a cost/quality decision — keep both keys"


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


def test_retries_and_structured_output_mode_are_configuration(monkeypatch):
    assert llm_config.llm_endpoint().max_retries == 2
    assert llm_config.llm_endpoint().structured_output == "json_object"

    monkeypatch.setenv("LLM_MAX_RETRIES", "5")
    monkeypatch.setenv("LLM_STRUCTURED_OUTPUT", "json_schema")
    llm_config.get_llm_settings.cache_clear()

    assert llm_config.llm_endpoint().max_retries == 5
    assert llm_config.llm_endpoint().structured_output == "json_schema"


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
