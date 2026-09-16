# SPDX-License-Identifier: Apache-2.0

"""
OpenAI-compatible client factory for the chatbot surface.

**Constructs clients. Chooses nothing.** Every endpoint, model, timeout, retry count and
capability flag comes from `backend/config/llm_config.py` — the one registry both LLM surfaces
read (DPG-17). There is no model name in this file and there must never be one: a factory decides
*how* to build a client, never *what* to call.

What this replaces, and why it matters beyond tidiness:

* **An import-time client.** `LLM_services.py` used to run `OpenAI(...)` at module import and
  swallow its own failure into `client = None`, which is why five functions each carried a
  different `if not client` guard. Import-time construction also freezes configuration at import,
  so a settings change needs a module reload — untestable without one.
* **A shadow client.** `classify_and_summarize_grievance` built a *second* client inside the
  function with its own timeout, shadowing the module one, then tested it for falsiness with a
  guard that could never fire (`OpenAI(...)` either returns an object or raises). The product's
  primary AI path therefore ran on a client no test could reach by patching the module attribute.
* **`load_dotenv('/home/ubuntu/nepal_chatbot/.env')`.** An absolute path to a directory that
  exists on one EC2 host and in no container. In a Docker-only stack that is dead code reading as
  live configuration — the worst kind, because it invites the next reader to "fix" the path
  instead of deleting it. Configuration arrives through `env_file:`.

**Two clients, not one**, because ASR routinely runs on a different provider, port or machine and
its timeout is materially higher — audio is slow. Which endpoint each task uses is the registry's
decision (`model_for("asr").endpoint`), not this file's.

Spec: docs/sprints/2026-08-llm/02-llm-agnostic-spec.md §DPG-11
"""
from __future__ import annotations

import logging
from functools import lru_cache

from openai import OpenAI

from backend.config.llm_config import (
    Endpoint,
    asr_endpoint,
    llm_endpoint,
    parse_response,
    request_for,
)

logger = logging.getLogger(__name__)


def _build(endpoint: Endpoint, what: str) -> OpenAI:
    if not endpoint.api_key:
        # Reproduces the pre-DPG-11 contract: no key ⇒ no client, and every call site's guard
        # fires with its own documented fallback. The alternative — a keyless client that 401s
        # per request — turns a configuration error into a provider error at the worst moment.
        raise RuntimeError(
            f"No API key configured for the {what} endpoint "
            f"({endpoint.host}). Set LLM_API_KEY (or ASR_API_KEY)."
        )
    logger.info("Building %s client for %s", what, endpoint.host)
    return OpenAI(
        base_url=endpoint.base_url,
        api_key=endpoint.api_key,
        timeout=endpoint.timeout,
        max_retries=endpoint.max_retries,
    )


@lru_cache(maxsize=1)
def get_llm_client() -> OpenAI:
    """The chat/completions client. Built on first use, then cached."""
    return _build(llm_endpoint(), "LLM")


@lru_cache(maxsize=1)
def get_asr_client() -> OpenAI:
    """The audio/transcriptions client — separate endpoint, separate deadline."""
    return _build(asr_endpoint(), "ASR")


def call_llm(
    task: str,
    messages: list[dict],
    *,
    schema: type | None = None,
    schema_name: str | None = None,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
    timeout: float | None = None,
    redact: bool = True,
):
    """
    One entry point for the chatbot surface: the layer picks the model and shapes the request.

    The call site brings a prompt and, if it wants structure, a Pydantic model. Everything else —
    which model, which deadline, whether this model accepts `temperature`, what its token-cap
    parameter is called, how to ask for JSON and how to read it back — comes from
    `backend/config/llm_config.py`, because all of it varies by provider and none of it varies by
    call site.

    Raises `LLMTruncatedError` / `LLMParseError` rather than returning something empty that a
    caller could mistake for an empty answer.
    """
    # ── Redaction, at the chokepoint, OPT-OUT (DPG-33 step 1) ────────────────────────────
    # `redact=True` is the default deliberately: a new call site gets pseudonymisation without
    # knowing it exists, and switching it off is a visible decision in the diff. Opt-IN is the
    # shape that fails — one forgotten keyword and grievance text crosses the border in clear.
    #
    # ⚠ The mapping is NOT returned and the output is NOT auto-restored. Both follow from the
    # 2026-08-27 decision that the STORED summary carries no names: classification output is
    # machine-consumed, the summary is stored pseudonymised, and the complainant still sees their
    # own words in `grievance_description`, which is stored unredacted (redaction is at
    # transmission, not storage — Q-12b). So no caller needs `restore()` here, and DPG-31's
    # "the mapping is never persisted" stays true because it never leaves this frame.
    if redact:
        messages = _redact_messages(messages, task=task)

    # ⚠ Chat completions only. ASR is a different API surface (`audio.transcriptions.create`,
    # multipart, no messages), so `transcribe_audio_file` keeps its own three lines and resolves
    # its model through the same registry. Pretending one function covers both would mean a
    # `messages` parameter that is meaningless for half its callers.
    request = request_for(
        task,
        messages,
        schema=schema.model_json_schema() if schema is not None else None,
        schema_name=schema_name,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        timeout=timeout,
    )
    return parse_response(get_llm_client().chat.completions.create(**request), schema)


def _redact_messages(messages: list[dict], *, task: str) -> list[dict]:
    """Pseudonymise every message body before it leaves the process.

    Returns NEW message dicts — the caller's list is untouched, because the caller often still
    needs the original (the prompt it built, the text it is about to store).

    ⚠ Redacts `content` only. Roles, names and tool metadata are structural.
    """
    # Imported here, not at module top, to keep `llm_client` importable in the minimal environment
    # DPG-24's CI job installs (the OpenAI SDK, pydantic and pytest — no service layer). A
    # module-level import would drag the constants package into that job for no reason.
    from backend.services.pii_service import redact_for_model

    out: list[dict] = []
    spans_total = 0
    for message in messages:
        content = message.get("content")
        if not isinstance(content, str) or not content:
            out.append(message)
            continue
        result = redact_for_model(content)
        spans_total += len(result.mapping)
        out.append({**message, "content": result.text})

    if spans_total:
        # Counts only — the values are exactly what this function exists to keep out of the logs.
        logger.info(
            "call_llm(%s): %d placeholder(s) substituted before transmission", task, spans_total
        )
    return out


def reset_clients() -> None:
    """Drop the cached clients so the next call re-reads configuration (tests, config reload)."""
    get_llm_client.cache_clear()
    get_asr_client.cache_clear()
