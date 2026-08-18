# SPDX-License-Identifier: Apache-2.0

"""
`GET /health/llm` — is the configured model endpoint reachable? (DPG-15)

**Separate from `/health`, and deliberately not part of any container health check.** An LLM
outage must not restart the chatbot: intake writes the grievance to Postgres first and classifies
asynchronously, so a model that is down degrades one enrichment step and nothing else. A probe
wired into `healthcheck:` would convert that survivable outage into a restart loop — which is the
opposite of the property this whole section of the sprint exists to protect.

What it reports, and what it does not:

* **The endpoint host only.** Never the API key, and never the full URL with credentials in it.
* **Reachability, which is a network property — not an auth one.** Any HTTP answer, including 401
  or 404, means the endpoint is *there*: a wrong key and a dead host are different problems with
  different fixes, and collapsing them wastes the first hour of an incident.
* ⚠ **`last_success_at` is this probe's own last success, not the workers'.** The model calls
  happen in `celery_llm` and `grm_celery`, in other processes; this route sees none of them.
  Reporting their last success would need shared state (Redis), and inventing a number that looks
  like it means that would be worse than the honest narrower one. The field is labelled
  `scope: "probe-only"` in the response so nobody has to read this docstring to find out.

Spec: docs/sprints/2026-08-llm/02-llm-agnostic-spec.md §DPG-15 · Ledger: TESTS.md T-15-b, T-15-c
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter

from backend.config.llm_config import asr_endpoint, llm_endpoint

logger = logging.getLogger(__name__)

router = APIRouter()

PROBE_TIMEOUT_SECONDS = 3.0

# Set by a successful probe. Deliberately per-process and in-memory: see the module docstring.
_last_success_at: Optional[str] = None


def _probe(base_url: str) -> tuple[bool, Optional[int], Optional[str]]:
    """Return (reachable, http_status, error). Any HTTP answer counts as reachable."""
    import httpx

    try:
        response = httpx.get(base_url, timeout=PROBE_TIMEOUT_SECONDS)
        return True, response.status_code, None
    except Exception as exc:  # network-level: DNS, refused, timeout, TLS
        return False, None, f"{type(exc).__name__}: {exc}"[:200]


def _endpoint_report(name: str, endpoint) -> dict[str, Any]:
    reachable, status_code, error = _probe(endpoint.base_url)
    report: dict[str, Any] = {
        "name": name,
        "host": endpoint.host,          # host only — never the key, never the query string
        "key_configured": bool(endpoint.api_key),
        "reachable": reachable,
        "http_status": status_code,
        "structured_output": endpoint.structured_output,
    }
    if error:
        report["error"] = error
    return report


@router.get("/health/llm")
def llm_health() -> dict[str, Any]:
    """
    Reachability of the configured LLM and ASR endpoints.

    Always returns 200 with a body describing what it found: this is an observation, not a gate.
    A non-200 here would tempt someone to wire it into a health check, and the first thing that
    would do is restart the chatbot during a provider outage it is designed to survive.
    """
    global _last_success_at

    chat = llm_endpoint()
    asr = asr_endpoint()
    endpoints = [_endpoint_report("llm", chat)]
    if asr.base_url != chat.base_url:
        endpoints.append(_endpoint_report("asr", asr))

    if all(e["reachable"] for e in endpoints):
        _last_success_at = datetime.now(timezone.utc).isoformat()

    unreachable = [e["name"] for e in endpoints if not e["reachable"]]
    if unreachable:
        logger.warning("LLM endpoint(s) unreachable: %s", ", ".join(unreachable))

    return {
        "status": "ok" if not unreachable else "degraded",
        "endpoints": endpoints,
        "last_success_at": _last_success_at,
        # ⚠ This probe observes only itself. Worker calls happen in other processes.
        "scope": "probe-only",
        "note": (
            "Reachability is a network property: a 401 counts as reachable. An unreachable "
            "endpoint degrades classification and translation; intake is unaffected — the "
            "grievance is written to Postgres before any model is called."
        ),
    }
