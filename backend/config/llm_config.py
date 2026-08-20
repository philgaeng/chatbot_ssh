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
    # ── Two models (Q-21, 2026-08-18) ────────────────────────────────────────
    # One model for transcription, one for everything else. Eight keys, two values: the KEYS stay
    # because they are the seam that lets a task be moved later without touching code — Q-11's
    # "one text model first, then downsize" depends on that seam existing.
    #
    # ⚠ What this replaced was not a decision but an accident: the September 2025 migration to
    # gpt-5-nano moved ONE call site of five, and the other four kept gpt-3.5-turbo (from July
    # 2025) and gpt-4 for eleven months, because a model name lived at each call site and nobody
    # could see them together. That is what DPG-17 was written from.
    model_classify: str = "gpt-5-nano"
    model_extract: str = "gpt-5-nano"
    model_translate: str = "gpt-5-nano"
    model_detect: str = "gpt-5-nano"
    model_asr: str = "whisper-1"
    # "" → resolves to model_translate. One knob moves translation everywhere; a second exists
    # for whoever needs the two surfaces to differ.
    model_ticket_translate: str = ""
    # ⚠ **The standard/SEAH split survives as two KEYS pointing at one model.** It was a deliberate
    # cost/quality decision (gpt-4o-mini / gpt-4o) and it stays *configurable* — one env var
    # re-opens it — so DPG-23 can re-decide it with measurements rather than by assumption.
    model_ticket_findings: str = "gpt-5-nano"
    model_ticket_findings_seah: str = "gpt-5-nano"

    # ── Per-task timeouts (0.0 → the endpoint's) ─────────────────────────────
    timeout_classify: float = Field(
        120.0,
        validation_alias=AliasChoices("TIMEOUT_CLASSIFY", "OPENAI_CLASSIFICATION_TIMEOUT"),
    )
    timeout_ticket: float = 30.0
    # ⚠ **The first attempt is short because somebody is waiting on it; the retries are long
    # because nobody is** (DPG-15b). Before this split the chat waited 20 s while a single attempt
    # was allowed 120 s — so the poll could only ever succeed if the model happened to be fast, and
    # gave up six times over before one attempt was due to finish.
    timeout_classify_interactive: float = 30.0
    # How long the conversation waits for a classification before carrying on without it. The
    # grievance is already filed by then and the result reaches the officer either way, so this is
    # a courtesy to the complainant, not a gate — 30 s covers the measured 14–20.5 s with margin.
    classification_wait_seconds: float = 30.0

    # ── Meaningful input (DPG-19) ────────────────────────────────────────────
    # Below this many characters — the text with leading and trailing whitespace stripped, so
    # internal spaces still count — the model is not called at all: there is nothing to summarise,
    # and a model asked to summarise two words returns either noise or nothing.
    # ⚠ This comment said "non-whitespace characters" until 2026-08-20. It was wrong, and the two
    # readings diverge on exactly the spaced-out input a person types when they are unsure what to
    # write: "a b c d e f g h i j k l m" is 25 characters and 13 non-whitespace, and it IS sent.
    # `tests/backend/test_benchmark_set.py::test_the_gate_counts_stripped_length_...` is the pin.
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
    # ⚠ **Empty means "ask the model's profile"** (DPG-18 §18.3). These were per-task constants
    # until the profile existed; now capability follows the model, so consolidating onto one model
    # lifts every site at once instead of needing five edits. They remain as **escape hatches** —
    # a provider whose profile we get wrong is corrected by an operator, not by a release.
    structured_classify: Literal["", "json_schema", "json_object", "prompt"] = ""
    structured_extract: Literal["", "json_schema", "json_object", "prompt"] = ""
    structured_translate: Literal["", "json_schema", "json_object", "prompt"] = ""
    structured_detect: Literal["", "json_schema", "json_object", "prompt"] = ""
    structured_ticket_findings: Literal["", "json_schema", "json_object", "prompt"] = ""

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
class ModelProfile:
    """
    What a model can be *told*, as opposed to what it can be *asked for*.

    ⚠ **Every field here was measured against the live provider on 2026-08-18, not read off a
    docs page** — and each one would have broken a call site if assumed:

    | Model | `json_schema` | `temperature` | token cap | reasoning |
    |---|---|---|---|---|
    | `gpt-5-nano` | ✅ | ❌ *"Only the default (1) value is supported"* | `max_completion_tokens` | **~4,000** |
    | `gpt-4o-mini` | ✅ | ✅ | `max_tokens` | 0 |
    | `gpt-3.5-turbo` | **400** | ✅ | `max_tokens` | 0 |
    | `gpt-4` | **400** | ✅ | `max_tokens` — but **400 on `json_object` too** | 0 |

    `reasoning_overhead` is the one that bites silently: a cap of 400 *or 2000* on `gpt-5-nano`
    returns `finish_reason: length` with **empty content**, because the reasoning consumed the
    budget before a single output token. The resolved-case summary needed 4,287 completion tokens,
    3,904 of them reasoning, against a cap of 1,200. See D-40.
    """

    structured_output: str = "json_object"
    supports_temperature: bool = True
    token_cap_param: str = "max_tokens"
    reasoning_overhead: int = 0


# First match wins, so `gpt-4o` must precede `gpt-4`. A model id this does not recognise —
# including every open-weights id, which carry provider prefixes and suffixes — falls through to
# the conservative default: JSON mode but no schema, temperature allowed, the classic cap.
_PROFILES: tuple[tuple[str, ModelProfile], ...] = (
    ("gpt-5", ModelProfile("json_schema", False, "max_completion_tokens", 4000)),
    ("o1", ModelProfile("json_schema", False, "max_completion_tokens", 4000)),
    ("o3", ModelProfile("json_schema", False, "max_completion_tokens", 4000)),
    ("gpt-4o", ModelProfile("json_schema", True, "max_tokens", 0)),
    ("gpt-4.1", ModelProfile("json_schema", True, "max_tokens", 0)),
    ("gpt-3.5", ModelProfile("json_object", True, "max_tokens", 0)),
    ("gpt-4", ModelProfile("prompt", True, "max_tokens", 0)),
    ("whisper", ModelProfile("prompt", True, "max_tokens", 0)),
    # ── Open weights, measured 2026-08-20 (DPG-21, scripts/ops/llm_smoke.py) ─────────────────
    # Against Hugging Face Inference Providers, served by Groq. Six probes, one request each,
    # same method as the OpenAI rows above.
    #
    # ⚠ **What was measured on which variant, because this one row covers both:**
    #
    #   |                        | 20b | 120b |
    #   |------------------------|-----|------|
    #   | `json_schema` honoured | ✅  | ✅   |
    #   | `json_object`          | ✅  | ✅   |
    #   | `temperature`          | ✅  | —    |
    #   | `max_tokens`           | ✅  | —    |
    #   | reasoning tokens seen  | 186 | 182  |
    #
    # The 120b run hit the account's credit ceiling (HTTP 402) after three probes, so its
    # `temperature` and token-cap cells are **unmeasured**. They are covered by this row anyway
    # because the values it asserts for them are the same ones DEFAULT_PROFILE already asserts —
    # so the row adds the two facts that WERE measured (a honoured grammar, and a non-zero
    # reasoning budget) and extrapolates nothing that changes behaviour. Re-run the probe when the
    # account has credit and split this row if 120b disagrees.
    #
    # ⭐ **`json_schema` is honoured, and the probe proves it was applied rather than accepted.**
    # The probe schema requires a `district` field the prompt never mentions; an ignored schema
    # produces a reply without it. That distinction matters because a silently-dropped
    # `response_format` and an honoured one are identical from the caller's side, and the first one
    # only shows up as malformed output under load.
    #
    # ⚠ **`reasoning_overhead` is the entry that actually earns its keep.** gpt-oss is a reasoning
    # model, and without a row here it fell through to DEFAULT_PROFILE, whose overhead is **0** —
    # the exact configuration that produced D-40 (a cap consumed entirely by reasoning returns
    # `finish_reason: length` with EMPTY content, which is not an error and looks like nothing at
    # all). `.env.open` ships `gpt-oss-20b` as the default open model, so the repository's own open
    # configuration was one long ticket timeline away from that failure.
    #
    # ⚠ Measured from small probes: treat the overhead as a **floor**. A resolved-case summary over
    # a real ticket timeline reasons harder than a two-line dust complaint (D-40 needed 3,904).
    ("gpt-oss", ModelProfile("json_schema", True, "max_tokens", 1000)),
    # ── The rest of the DPG-23 shortlist, measured 2026-08-20 (second pass, paced) ────────────
    # Six probes each, one request per cell. Full matrix and method:
    # docs/dpg/open-model-configuration.md.
    #
    # ⚠ **`Qwen3.5-9B` accepts `json_schema` and does not honour it.** The request returned 200 and
    # the reply omitted every field the schema declares required — the silent-degradation case
    # DPG-13's ladder exists for, caught in the wild. It is pinned to `json_object` here, which is
    # the strongest rung it actually applies. **This is why the probe asks for a field the prompt
    # never mentions:** "returned JSON" and "was constrained" are indistinguishable otherwise, and
    # the difference only shows up as malformed output under load.
    #
    # ⚠ **The `reasoning_overhead` values for the Qwen family are inferred, not itemised.** These
    # models report `reasoning_tokens: 0` while emitting 1,450–2,048 completion tokens for a
    # one-sentence probe — their reasoning goes to a non-standard `reasoning_content` field, so it
    # is billed as completion and invisible in `completion_tokens_details`. Taking the API at its
    # word would set an overhead of 0 and truncate them exactly as D-40 truncated `gpt-5-nano`.
    # The value below is the **observed completion for a trivial prompt**, which is a floor.
    ("Qwen3.5-9B", ModelProfile("json_object", True, "max_tokens", 2000)),
    ("Qwen3.5", ModelProfile("json_schema", True, "max_tokens", 2000)),
    ("phi-4", ModelProfile("json_schema", True, "max_tokens", 0)),
    # ⚠ No entry for `swiss-ai/Apertus-*`: its only reply was "Your request was blocked" — a content
    # filter, on a grievance about children falling ill from construction dust. See the follow-up;
    # an unmeasured model gets the conservative default, never a guess.
)

DEFAULT_PROFILE = ModelProfile()


def profile_for(model: str) -> ModelProfile:
    """The capability profile for a model id, by prefix. Unknown ids get the safe default."""
    bare = (model or "").split("/")[-1].split(":")[0]
    for prefix, profile in _PROFILES:
        if bare.startswith(prefix):
            return profile
    return DEFAULT_PROFILE


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
    if not structured_attr:
        capability = "prompt"          # free-text tasks: ASR, note translation
    else:
        override = getattr(s, structured_attr)
        capability = override or profile_for(model).structured_output
    return TaskModel(
        task=task,
        model=model,
        endpoint=endpoint,
        timeout=timeout or endpoint.timeout,
        structured_output=weaker_mode(endpoint.structured_output, capability),
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

# ─────────────────────────────────────────────────────────────────────────────
# The call layer's shared half (DPG-18)
# ─────────────────────────────────────────────────────────────────────────────
# A factory builds a client; a call site writes a prompt. Everything between those two — which
# model, which deadline, how to ask for JSON, how to read it back — varies by PROVIDER and not by
# call site, and that is the test for what belongs here.
#
# Only the *shaping* is shared. The *calling* stays on each surface, because the client does:
# `backend/services/llm_client.py::call_llm` and `ticketing/clients/llm_client.py::call_llm` are
# ~15 lines each. Two factories, one config; two callers, one contract.


class LLMTruncatedError(ValueError):
    """
    The model stopped because it ran out of budget, not because it had finished.

    ⚠ **This is a failure, not an empty answer**, and the distinction is not academic: on a
    reasoning model a truncated reply arrives as HTTP 200 with `finish_reason: "length"` and
    **empty content**. Every parse path in this repository treated empty content as an empty
    *result*, so truncation disguised itself as "the model had nothing to say" — which on the
    resolved-case-summary path means a complainant is told their case is closed and never receives
    the closure document (D-40, D-36).
    """


class LLMParseError(ValueError):
    """The model's reply was not the shape we asked for. Distinct from an empty reply."""


def augment_prompt_for_schema(messages: list[dict], schema: dict) -> list[dict]:
    """
    The `prompt` rung: state the required shape **in words**, generated from the same schema the
    `json_schema` rung would have sent.

    ⚠ This exists because the alternative is what the repository had: nine hand-written "return
    strict JSON" paragraphs that had already drifted into three different phrasings, one of them
    carrying a hand-typed example that no longer matched its parser. A fallback nobody can keep in
    step with the schema is a fallback that fails quietly on the provider that needs it most.
    """
    props = (schema or {}).get("properties") or {}
    if not props:
        return messages

    fields = ", ".join(f"{name!r}" for name in props)
    instruction = (
        "Return ONLY a JSON object, with no prose, no markdown fences and no extra keys. "
        f"It must contain exactly these keys: {fields}."
    )
    out = [dict(m) for m in messages]
    for message in out:
        if message.get("role") == "system":
            message["content"] = f"{message['content']}\n\n{instruction}"
            return out
    return [{"role": "system", "content": instruction}, *out]


def request_for(
    task: str,
    messages: list[dict],
    *,
    schema: dict | None = None,
    schema_name: str | None = None,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
    timeout: float | None = None,
) -> dict:
    """
    Everything a call site needs to hand `chat.completions.create(**…)`, decided from the registry.

    The call site says what it *wants*; this decides what the model can be *told*:

    * the model, the endpoint's deadline, and the task's own if it has one;
    * the strongest structured-output rung the model honours — schema, JSON mode, or words;
    * `temperature` **dropped entirely** where the model refuses anything but its default;
    * the token cap under **the name that model uses**, with the reasoning budget added.

    Each of those four is a 400 or an empty response on some model this product already calls
    (D-31, D-40).
    """
    resolved = model_for(task)
    profile = profile_for(resolved.model)
    mode = resolved.structured_output

    if schema is not None and mode == "prompt":
        messages = augment_prompt_for_schema(messages, schema)

    request: dict = {
        "model": resolved.model,
        # An explicit deadline wins over the task's: the caller is the only one who knows whether
        # a person is sitting in a chat window waiting for this (DPG-15b).
        "timeout": timeout or resolved.timeout,
        "messages": messages,
        **response_format_kwargs(schema_name or task, schema, mode),
    }

    if temperature is not None and profile.supports_temperature:
        request["temperature"] = temperature
    elif temperature is not None:
        logger.debug(
            "%s: dropping temperature=%s — %s only accepts its default",
            task, temperature, resolved.model,
        )

    if max_output_tokens:
        # ⚠ The reasoning overhead is added, not assumed away: a cap sized for the visible output
        # alone returns empty content on a reasoning model, which reads as a quality problem.
        request[profile.token_cap_param] = max_output_tokens + profile.reasoning_overhead

    return request


def parse_response(response: object, schema_model: type | None = None) -> object:
    """
    Read a reply back: truncation refused, fences stripped, JSON parsed, schema validated.

    Returns the validated model instance when `schema_model` is given, otherwise the raw text.
    Raises `LLMTruncatedError` or `LLMParseError` — never returns an empty value that a caller
    might mistake for an empty answer.
    """
    choice = response.choices[0]                                    # type: ignore[attr-defined]
    if getattr(choice, "finish_reason", None) == "length":
        raise LLMTruncatedError(
            "The model stopped at its token budget before finishing. This is not an empty "
            "answer: raise the cap (remember reasoning tokens) or remove it."
        )

    raw = (choice.message.content or "").strip()
    if schema_model is None:
        return raw

    if raw.startswith("```"):
        # Providers that cannot do JSON mode fence their output; the `prompt` rung asks them not
        # to, and some do it anyway. Cheaper to strip than to fail.
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        return schema_model.model_validate_json(raw)                # type: ignore[attr-defined]
    except Exception as exc:
        # ⚠ **Report the shape of the failure, never the reply.** Pydantic's ValidationError
        # embeds `input_value=...` — i.e. the model's output, which is derived from the grievance
        # narrative — and this message travels into a `status="error"` payload and the Celery log.
        # Caught by the test that asserted on the old message and found the narrative in it.
        name = getattr(schema_model, "__name__", str(schema_model))
        problems = getattr(exc, "errors", None)
        if callable(problems):
            summary = ", ".join(
                f"{'.'.join(str(p) for p in err.get('loc', ())) or '<root>'}: {err.get('type')}"
                for err in problems()[:5]
            )
        else:
            summary = type(exc).__name__
        raise LLMParseError(
            f"The reply did not match {name} ({len(raw)} chars): {summary}"
        ) from exc
