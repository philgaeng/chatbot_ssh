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

from backend.config.llm_config import Endpoint, asr_endpoint, llm_endpoint

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


def reset_clients() -> None:
    """Drop the cached clients so the next call re-reads configuration (tests, config reload)."""
    get_llm_client.cache_clear()
    get_asr_client.cache_clear()
