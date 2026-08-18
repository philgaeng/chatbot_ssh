# SPDX-License-Identifier: Apache-2.0

"""
The single source of truth for *which* LLM this product calls — both surfaces.

Endpoints and models are configuration, not code. This module resolves them from the
environment; it constructs no client, and it imports nothing from ``backend.*``,
``ticketing.*`` or ``ops.*`` — either surface may import it, neither owns it.

Consumed by:
  backend/services/llm_client.py   (DPG-11) — chatbot intake
  ticketing/clients/llm_client.py  (DPG-12) — ticketing case analysis

**Why one registry for two factories.** Two independent clients is the right answer for the
service boundary — two surfaces, two lifecycles, two deployment units, one live chatbot that
must not be coupled to the officer portal. Two independent *model registries* is not: it puts
the DPG indicator-4 answer in two files with two default sets and lets them drift. Point
``backend/`` at an open router, miss ``ticketing/``, and the **complainant-facing** resolved-case
summary is still on a closed model while the repository advertises otherwise. That drift had
already happened before this file existed: the standard/SEAH model pair was written out in
*four* places, one of which is a persisted provenance field.

So: **a factory decides how to construct a client. It never decides what to call.**

**Why it lives in ``backend/config/``.** The independence rule in
``ticketing/clients/llm_client.py`` names ``backend/services/`` — the *service layer*.
``backend/config/`` is a different thing, and the precedent is already load-bearing in
production: ``backend/config/smtp_config.py`` is imported by ``ticketing/auth/keycloak_smtp.py``
on the live officer-invite path. Same problem shape: one external provider, two surfaces, one
config. Packaging cost is zero — every Python service runs the same image.

The constraint that keeps that honest is the **no first-party imports** rule above, pinned by
``tests/backend/test_llm_config_pins.py`` (T-17-b). One convenience import from
``backend.config.constants`` would quietly turn a shared file into a backend-owned one, and the
file would stop being copy-portable if ticketing is ever extracted.

Works unchanged against:
  T1  https://router.huggingface.co/v1   hosted open-weights providers
  T2  http://<private-ip>:8000/v1        self-hosted vLLM (designed, parked — Q-03/Q-05)
  T3  http://localhost:8000/v1           on-prem
  --  https://api.openai.com/v1          today's default, and the benchmark comparison

⚠ **The defaults below are today's models and today's endpoint, deliberately.** Flipping
``LLM_BASE_URL`` to an open router while the model names are still ``gpt-3.5-turbo`` and
``whisper-1`` would ship a repository whose default configuration cannot answer a single
request — weaker indicator-4 evidence than an honest proprietary default, not stronger. The
flip is a Sprint-2 commit against this file, once DPG-23 has named the open models (Q-10).

⚠ **Pinning ``model:provider`` fixes the sub-processor; it does not fix the jurisdiction of
execution.** Hugging Face's router selects a partner per request unless the model id carries a
provider suffix. This module makes the *choice* configurable. It does not make the *location*
knowable — see ``docs/dpg/privacy-assessment.md`` F-17.

Spec: docs/sprints/2026-08-llm/02-llm-agnostic-spec.md §DPG-17
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# OpenAI's own default, used when LLM_BASE_URL is unset. Named here rather than left implicit
# so that "which endpoint is this talking to" is answerable without reading the SDK.
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"

# The SDK's default request timeout. Preserved as the endpoint default so that moving the
# backend surface onto this registry changes no timeout behaviour (DPG-10 stays green).
DEFAULT_SDK_TIMEOUT = 600.0


class LLMSettings(BaseSettings):
    """The env surface — the only one, for both surfaces."""

    # ── The chat/completions endpoint ────────────────────────────────────────
    llm_base_url: str = DEFAULT_OPENAI_BASE_URL
    llm_api_key: str = Field(
        "", validation_alias=AliasChoices("LLM_API_KEY", "OPENAI_API_KEY")
    )
    llm_timeout: float = DEFAULT_SDK_TIMEOUT
    llm_max_retries: int = 2
    # Provider capability, not a preference: `json_schema` constrains generation to a grammar,
    # `json_object` asks for "some JSON", `prompt` asks in words and hopes. DPG-13 implements
    # the degradation ladder and moves this default up.
    # The **endpoint's** ceiling. Per-task capability (below) clamps it down; this clamps every
    # task down at once, which is what an endpoint with weaker support needs.
    llm_structured_output: Literal["json_schema", "json_object", "prompt"] = "json_schema"

    # ── The audio/transcriptions endpoint ────────────────────────────────────
    # Separate because ASR commonly runs on a different port, provider, or machine, and its
    # timeout is materially higher — audio is slow. Falls back to the chat endpoint when unset.
    asr_base_url: str = ""
    asr_api_key: str = Field(
        "", validation_alias=AliasChoices("ASR_API_KEY", "OPENAI_API_KEY")
    )
    asr_timeout: float = 0.0

    # ── The models ───────────────────────────────────────────────────────────
    # Every model name in the product. Nothing else may declare one (T-17-c).
    model_classify: str = "gpt-5-nano"
    model_extract: str = "gpt-3.5-turbo"
    model_translate: str = "gpt-4"
    model_detect: str = "gpt-3.5-turbo"
    model_asr: str = "whisper-1"
    # "" → resolves to model_translate. One knob moves translation everywhere; a second exists
    # for whoever needs the two surfaces to differ.
    model_ticket_translate: str = ""
    # The standard/SEAH split is a deliberate cost/quality decision — SEAH investigations get
    # the more careful model. It survives as two keys, never as two literals in a call site.
    model_ticket_findings: str = "gpt-4o-mini"
    model_ticket_findings_seah: str = "gpt-4o"

    # ── Per-task timeouts (0.0 → the endpoint's) ─────────────────────────────
    timeout_classify: float = Field(
        120.0,
        validation_alias=AliasChoices("TIMEOUT_CLASSIFY", "OPENAI_CLASSIFICATION_TIMEOUT"),
    )
    timeout_ticket: float = 30.0

    # ── Meaningful input (DPG-19) ────────────────────────────────────────────
    # Below this many non-whitespace characters, the model is not called at all: there is nothing
    # to summarise, and a model asked to summarise two words returns either noise or nothing.
    # ⚠ 25 characters is not the same amount of information in every script — in Devanagari it is a
    # short sentence, in English roughly four words. It is a registry value precisely so it can
    # differ by language later; today it is one number and this comment is the disclosure.
    min_classify_chars: int = 25

    # ── Per-task structured-output capability (DPG-13) ───────────────────────
    # ⚠ **Capability is a property of the (endpoint, model) pair, not of the endpoint alone**,
    # and the spec's endpoint-only flag would have broken three call sites. Measured against the
    # live provider on 2026-08-18, one request per cell:
    #
    #   model          json_schema   json_object
    #   gpt-5-nano         ✅            ✅
    #   gpt-4o-mini        ✅            ✅
    #   gpt-3.5-turbo   400 ❌            ✅
    #   gpt-4           400 ❌         400 ❌   ← rejects JSON mode entirely
    #
    # So each task declares what **its** model can do; `llm_structured_output` is the endpoint's
    # ceiling, and the effective mode is the weaker of the two. Point the registry at models with
    # better support and one variable lifts every site at once — which is the point of the ladder.
    structured_classify: Literal["json_schema", "json_object", "prompt"] = "json_schema"
    structured_extract: Literal["json_schema", "json_object", "prompt"] = "json_object"
    structured_translate: Literal["json_schema", "json_object", "prompt"] = "prompt"
    structured_detect: Literal["json_schema", "json_object", "prompt"] = "json_object"
    structured_ticket_findings: Literal["json_schema", "json_object", "prompt"] = "json_schema"

    model_config = SettingsConfigDict(
        env_file=("env.local", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@dataclass(frozen=True)
class Endpoint:
    """A read-only view a factory can hand straight to ``OpenAI(...)``."""

    base_url: str
    api_key: str
    timeout: float
    max_retries: int
    structured_output: str

    @property
    def host(self) -> str:
        """Host only — safe to log or return from a health probe. Never the key."""
        without_scheme = self.base_url.split("://", 1)[-1]
        return without_scheme.split("/", 1)[0]


@dataclass(frozen=True)
class TaskModel:
    """What a call site needs: which model, on which endpoint, with which deadline and format."""

    task: str
    model: str
    endpoint: Endpoint
    timeout: float
    structured_output: str = "prompt"


# task key → (settings attribute holding the model, which endpoint, settings attribute holding
# the timeout override). This mapping *is* the registry; the table in the spec mirrors it.
_TASKS: dict[str, tuple[str, str, str, str]] = {
    "classify": ("model_classify", "llm", "timeout_classify", "structured_classify"),
    "extract": ("model_extract", "llm", "", "structured_extract"),
    "translate": ("model_translate", "llm", "", "structured_translate"),
    "detect": ("model_detect", "llm", "", "structured_detect"),
    # ASR and ticket translation return free text, not JSON: no response_format, ever.
    "asr": ("model_asr", "asr", "", ""),
    "ticket_translate": ("model_ticket_translate", "llm", "timeout_ticket", ""),
    "ticket_findings": ("model_ticket_findings", "llm", "timeout_ticket", "structured_ticket_findings"),
    "ticket_findings_seah": (
        "model_ticket_findings_seah", "llm", "timeout_ticket", "structured_ticket_findings",
    ),
}

# Strongest first. The effective mode for a call is the weaker of the endpoint's ceiling and the
# task's own capability — degrade, never guess upward.
_LADDER = ("json_schema", "json_object", "prompt")

# Old name → new name. Resolved by AliasChoices above; warned about here, once each, because a
# stale env.local that authenticates one surface and silently breaks the other is exactly the
# failure this consolidation exists to prevent.
_DEPRECATED_ALIASES: dict[str, str] = {
    "OPENAI_API_KEY": "LLM_API_KEY / ASR_API_KEY",
    "OPENAI_CLASSIFICATION_TIMEOUT": "TIMEOUT_CLASSIFY",
}

_warned: set[str] = set()


def _warn_once_about_deprecated_aliases() -> None:
    import os

    for old, new in _DEPRECATED_ALIASES.items():
        if old in _warned or os.environ.get(old) is None:
            continue
        canonical = new.split(" / ")
        if any(os.environ.get(name) for name in canonical):
            continue  # the new name is set and wins; nothing to warn about
        _warned.add(old)
        logger.warning(
            "%s is deprecated and will be removed: use %s. It is being honoured for now "
            "(backend/config/llm_config.py).",
            old,
            new,
        )


@lru_cache
def get_llm_settings() -> LLMSettings:
    settings = LLMSettings()
    _warn_once_about_deprecated_aliases()
    return settings


def llm_endpoint() -> Endpoint:
    s = get_llm_settings()
    return Endpoint(
        base_url=s.llm_base_url,
        api_key=s.llm_api_key,
        timeout=s.llm_timeout,
        max_retries=s.llm_max_retries,
        structured_output=s.llm_structured_output,
    )


def asr_endpoint() -> Endpoint:
    """The ASR endpoint, falling back to the chat endpoint for anything it does not override."""
    s = get_llm_settings()
    chat = llm_endpoint()
    return Endpoint(
        base_url=s.asr_base_url or chat.base_url,
        api_key=s.asr_api_key or chat.api_key,
        timeout=s.asr_timeout or chat.timeout,
        max_retries=chat.max_retries,
        structured_output=chat.structured_output,
    )


def model_for(task: str) -> TaskModel:
    """Resolve a task key to its model, endpoint and deadline. The only model lookup there is."""
    try:
        model_attr, endpoint_name, timeout_attr, structured_attr = _TASKS[task]
    except KeyError:
        raise KeyError(
            f"Unknown LLM task {task!r}. Known tasks: {', '.join(sorted(_TASKS))}. "
            "Add it to _TASKS in backend/config/llm_config.py — not to the call site."
        ) from None

    s = get_llm_settings()
    endpoint = asr_endpoint() if endpoint_name == "asr" else llm_endpoint()

    model = getattr(s, model_attr)
    if not model and task == "ticket_translate":
        model = s.model_translate  # documented fallback: one knob moves translation everywhere

    timeout = getattr(s, timeout_attr) if timeout_attr else 0.0
    task_capability = getattr(s, structured_attr) if structured_attr else "prompt"
    return TaskModel(
        task=task,
        model=model,
        endpoint=endpoint,
        timeout=timeout or endpoint.timeout,
        structured_output=weaker_mode(endpoint.structured_output, task_capability),
    )


def weaker_mode(*modes: str) -> str:
    """The weakest of the given structured-output modes — the degradation ladder's only rule."""
    return max(modes, key=_LADDER.index)


def strict_json_schema(schema: dict) -> dict:
    """
    Normalise a Pydantic-generated JSON Schema into one the provider will accept as `strict`.

    Strict mode requires `additionalProperties: false` and *every* property listed as required,
    at every level — Pydantic emits neither, because they are not what JSON Schema means by
    "required". Inlining `$defs` is left alone: the providers that support strict mode resolve
    local `$ref`s themselves.
    """
    import copy

    def _walk(node: object) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"])
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    out = copy.deepcopy(schema)
    _walk(out)
    return out


def response_format_kwargs(name: str, schema: dict | None, mode: str) -> dict:
    """
    The `response_format=` keyword for a call — or **nothing at all** on the `prompt` rung.

    Returned as kwargs to splat rather than as a value, because `response_format=None` is not the
    same as omitting it: the SDK serialises an explicit None into the request body, and a provider
    that has never heard of the parameter is entitled to reject it. The weakest rung must produce
    the request the code sent before any of this existed.
    """
    fmt = response_format_for(name, schema, mode)
    # Which rung was actually used, per call. Silent degradation is the failure mode here: a
    # provider that quietly ignores `json_schema` and a provider that never received it look
    # identical from the outside, and the second one is a config bug you want to find.
    logger.debug("structured output: %s → %s", name, mode)
    return {"response_format": fmt} if fmt is not None else {}


def response_format_for(name: str, schema: dict | None, mode: str) -> dict | None:
    """
    Build the `response_format` for a call, or None when the mode is `prompt`.

    This is the degradation ladder, implemented once for both surfaces. Seven call sites across
    two surfaces hit the same provider; a per-surface implementation would let ticketing ask for
    a schema the endpoint cannot honour, and the first fix under time pressure would be to weaken
    the test rather than the config.
    """
    if mode == "json_schema" and schema is not None:
        return {
            "type": "json_schema",
            "json_schema": {"name": name, "schema": strict_json_schema(schema), "strict": True},
        }
    if mode in ("json_schema", "json_object"):
        # No schema to send (a dynamic call site that could not build one) → the weaker rung.
        return {"type": "json_object"}
    return None


def is_too_short_to_process(text: str | None) -> bool:
    """
    Is there too little here for a model to say anything useful?

    ⚠ **An empty result is not a failure** — that distinction is the whole point of this function.
    A three-word grievance *cannot* be summarised, and the model answering "not enough information"
    is the model being right. What was missing was any way to tell that apart from a model that
    failed, and the fact that the three words were sent at all.

    So: below the threshold, do not call. At or above it, an empty answer is a legitimate answer
    and is logged as such, never as an error.
    """
    return len((text or "").strip()) < get_llm_settings().min_classify_chars


def findings_task(is_seah: bool) -> str:
    """
    The SEAH model ternary, declared once.

    ⚠ This exists because that ternary had been written out four times — in the ticketing
    client, in ``resolved_summary_builder`` (whose copy is written into a **persisted**
    provenance field), in a log line, and once more by reaching into the client module's
    privates, which made it invisible to ``grep "gpt-"``. Every one of those sites now calls
    this function. T-17-c fails if a fifth appears.
    """
    return "ticket_findings_seah" if is_seah else "ticket_findings"


def declared_env_vars() -> tuple[str, ...]:
    """
    Every environment variable this registry reads, canonical names only.

    ``.env.example`` is generated from this and pinned against it (T-16-a) rather than
    hand-maintained beside it — a hand-kept mirror is the failure mode that made CLAUDE.md's
    data-rules table false for months.
    """
    return tuple(
        sorted(name.upper() for name in LLMSettings.model_fields if name != "model_config")
    )


def deprecated_env_vars() -> dict[str, str]:
    """Old name → what replaced it. Honoured, warned about once, and documented as legacy."""
    return dict(_DEPRECATED_ALIASES)
