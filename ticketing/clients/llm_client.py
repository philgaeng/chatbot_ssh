# SPDX-License-Identifier: Apache-2.0

"""
LLM client for the ticketing service.

**This module constructs a client. It chooses no model and no endpoint.** Both come from
`backend/config/llm_config.py` — the one registry both LLM surfaces read (DPG-17) — via
`model_for()` and `findings_task()`.

⚠ **The instruction this docstring used to give produced the problem it was warning about.** It
said: *"Uses OpenAI gpt-4 … DO NOT import from backend/services/ — keep ticketing independent.
Replicate the pattern here."* The boundary is real and stays: ticketing does not import the
chatbot's **service layer**, and it keeps its own client, its own lifecycle, its own deployment
unit. But *"replicate the pattern"* was read as *"replicate the model names"*, and they were then
replicated four more times — into `resolved_summary_builder` (which writes one into a **persisted
provenance field**), into a log line, and once by reaching into this module's privates from
`tasks/llm.py`, which made it invisible to `grep "gpt-"`.

So the rule is now precise: **two factories, one config.** `backend/config/` is not the service
layer — ticketing already imports `backend/config/smtp_config.py` on the live officer-invite path,
and the registry imports nothing first-party, so it stays copy-portable if ticketing is ever
extracted (pinned: `tests/backend/test_llm_config_pins.py`).

Auth: `LLM_API_KEY`, with `OPENAI_API_KEY` honoured as a deprecated alias (one warning), resolved
in the registry so **both** surfaces treat a stale `env.local` identically.
"""

import json
import logging
import re
from typing import Optional

from openai import OpenAI
from pydantic import ValidationError

from backend.config.llm_config import (
    LLMParseError,
    LLMTruncatedError,
    findings_task,
    llm_endpoint,
    parse_response,
    request_for,
)
from ticketing.clients.llm_schemas import CaseFindings, ResolvedCaseSummary

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level client (lazy-init — avoids import-time errors if key is absent)
# ---------------------------------------------------------------------------
_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    """Return a cached OpenAI-compatible client, built from the shared registry on first call."""
    global _client
    if _client is None:
        endpoint = llm_endpoint()
        logger.info("Building ticketing LLM client for %s", endpoint.host)
        _client = OpenAI(
            base_url=endpoint.base_url,
            api_key=endpoint.api_key,
            timeout=endpoint.timeout,
            max_retries=endpoint.max_retries,
        )
    return _client


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
    One entry point for the ticketing surface. Same contract as the chatbot surface's, and
    deliberately a **separate function**: the service-layer boundary means this file keeps its own
    client, and a client is the one thing the shared layer cannot hold.

    What is shared is the *shaping* — `request_for()` and `parse_response()` in
    `backend/config/llm_config.py` — so the two surfaces cannot ask the same provider for
    different things. Two factories, one config; two callers, one contract.
    """
    # ── Redaction, at the chokepoint, OPT-OUT (DPG-33 step 1) ────────────────────────────
    # Same default and the same reason as the chatbot surface: a new call site is pseudonymised
    # without knowing this exists, and turning it off is a visible decision in the diff.
    #
    # ⚠ This surface carries the sharper payload. `generate_case_findings` sends **the whole case
    # timeline including officer notes**, and on a sensitive workflow that is a SEAH case file.
    # Step 3 of DPG-33 is about this: the prompt already asks the model not to echo names, but a
    # prompt instruction does nothing about what is SENT — it only acts on what comes back. That
    # instruction stays as defence in depth; this is the control.
    if redact:
        messages = _redact_messages(messages, task=task)

    request = request_for(
        task,
        messages,
        schema=schema.model_json_schema() if schema is not None else None,
        schema_name=schema_name,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        timeout=timeout,
    )
    return parse_response(_get_client().chat.completions.create(**request), schema)


def _redact_messages(messages: list[dict], *, task: str) -> list[dict]:
    """Pseudonymise every message body before it leaves the process.

    Returns NEW message dicts; the caller's list is untouched.

    ⚠ **This imports from `backend.services`, which the module docstring's independence rule
    normally forbids.** The exemption is the same one `backend/config/llm_config.py` already
    holds and is narrower than it looks: `pii_service` is a **pure function library** — no
    session, no client, no I/O, no first-party imports beyond a constants module. Duplicating a
    redaction implementation per surface is the failure mode this sprint exists to avoid: two
    recognisers drift, and the weaker one becomes the border.
    """
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
        logger.info(
            "call_llm(%s): %d placeholder(s) substituted before transmission", task, spans_total
        )
    return out


def reset_client() -> None:
    """Drop the cached client so the next call re-reads configuration (tests, config reload)."""
    global _client
    _client = None


# ---------------------------------------------------------------------------
# Translation helper
# ---------------------------------------------------------------------------

_TRANSLATE_SYSTEM = (
    "You are a professional translator. "
    "Translate the following text to English. "
    "If the text is already in English, return it as-is. "
    "Preserve technical, legal, and proper-noun terms exactly. "
    "Output only the translated text — no commentary, no quotation marks."
)

_LANG_RE = re.compile(
    r"[ऀ-ॿঀ-৿਀-੿઀-૿"
    r"଀-୿஀-௿ఀ-౿ಀ-೿"
    r"ഀ-ൿऀ-ॿ]"  # Devanagari + other Indic scripts
)


def _looks_non_english(text: str) -> bool:
    """
    Cheap heuristic: if >5% of characters are non-ASCII / Indic script,
    assume the text needs translation.  Avoids unnecessary API calls for
    English-only notes.
    """
    if not text:
        return False
    non_ascii = sum(1 for c in text if ord(c) > 127)
    return (non_ascii / len(text)) > 0.05


def translate_to_english(text: str) -> Optional[str]:
    """
    Translate *text* to English using the configured translation model.

    Returns the translated string, or None on error (caller logs and skips).
    If the text already looks like English, returns it unchanged without an API call.
    """
    if not text or not text.strip():
        return None

    if not _looks_non_english(text):
        logger.debug("translate_to_english: text looks English, skipping API call")
        return text

    try:
        translated = call_llm(
            "ticket_translate",
            [
                {"role": "system", "content": _TRANSLATE_SYSTEM},
                {"role": "user", "content": text},
            ],
            temperature=0.2,
            max_output_tokens=1024,
        )
        return (translated or "").strip() or None
    except Exception as exc:
        logger.error("translate_to_english failed: %s", exc, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Findings / summary helper  (Layer 2 — structured JSON output)
# ---------------------------------------------------------------------------

_FINDINGS_SYSTEM = """\
You are an impartial GRM (Grievance Redress Mechanism) case analyst for ADB \
infrastructure projects in Nepal.

Analyse the case timeline and field reports provided as JSON.
Return ONLY valid JSON — no prose, no markdown fences, no extra keys.

Output schema (all fields required):
{
  "summary_en": "<2-4 sentence plain-English case summary>",
  "key_findings": ["<finding 1>", "<finding 2>"],
  "recommended_action": "<one actionable sentence for the case officer>",
  "urgency": "HIGH | MEDIUM | LOW",
  "languages_detected": ["en"]
}

Rules:
- Never invent facts not present in the timeline.
- NEVER include names, phone numbers, email addresses, or physical addresses in output.
  Replace any that appear in notes with role descriptors (e.g. "the complainant").
- urgency HIGH = health/safety risk OR SLA already breached OR SEAH case.
- urgency MEDIUM = unresolved complaint escalated beyond L1.
- urgency LOW = in progress within SLA, no safety risk.
- If field reports contradict earlier notes, flag the discrepancy in key_findings.
- If non-English notes are present, set languages_detected accordingly.
- key_findings: minimum 1, maximum 5 items.
"""

# Model selection: a cost vs. quality tradeoff, and it survives — as two registry keys.
#   ticket_findings       standard cases: quality indistinguishable for structured extraction,
#                         at roughly a fifteenth of the cost
#   ticket_findings_seah  SEAH cases: more careful reasoning for sensitive investigations
# The keys are resolved by findings_task(is_seah); the models behind them are declared in
# backend/config/llm_config.py and nowhere else. The two module constants that used to live here
# were copied into three other modules — see this module's docstring.


def generate_case_findings(
    context: dict,
    is_seah: bool = False,
) -> Optional[dict]:
    """
    Generate structured case findings from a pre-assembled context document.

    *context* is the PII-clean dict produced by context_builder.build_ticket_context().
    Returns a findings dict with keys: summary_en, key_findings, recommended_action,
    urgency, languages_detected — or None on error.

    Caller stores summary_en → Ticket.ai_summary_en (backward compat)
    and full dict → TicketContextCache.findings_json.
    """
    if not context:
        return None

    task_key = findings_task(is_seah)
    # Compact JSON — minimise tokens
    user_content = json.dumps(context, separators=(",", ":"), ensure_ascii=False)

    try:
        findings = call_llm(
            task_key,
            [
                {"role": "system", "content": _FINDINGS_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            schema=CaseFindings,
            schema_name="case_findings",
            temperature=0.0,           # deterministic — dropped for models that refuse it
            max_output_tokens=400,     # the reasoning budget is added by the model's profile
        ).model_dump()

        # ⚠ The "missing keys → fill defaults" branch this replaced is now the schema's own
        # defaults: strict mode requires every declared property, and `CaseFindings` supplies a
        # value for each on the weaker rungs. The behaviour is preserved; the branch is not.
        logger.info(
            "generate_case_findings: ok task=%s urgency=%s keys=%d",
            task_key, findings.get("urgency"), len(findings.get("key_findings", [])),
        )
        return findings

    except (LLMTruncatedError, LLMParseError, ValidationError) as exc:
        logger.error("generate_case_findings: unusable reply from LLM: %s", exc)
        return None
    except Exception as exc:
        logger.error("generate_case_findings failed: %s", exc, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Resolved case summary (closure document — spec §3.6)
# ---------------------------------------------------------------------------

_RESOLVED_SUMMARY_SYSTEM = """\
You are an impartial GRM case analyst for ADB infrastructure projects in Nepal.

Analyse the JSON case bundle. Return ONLY valid JSON with these keys (all required):
{
  "field_reports_digest_en": "<1-3 paragraphs>",
  "other_notes_digest_en": "<1-2 paragraphs>",
  "combined_digest_en": "<2-6 paragraphs — investigation narrative>",
  "resolution_text_public": "<plain-language outcome for complainant>",
  "findings_summary_public": "<1-2 paragraphs max for complainant>"
}

Rules:
- Base every sentence on field_reports, other_officer_notes, original_complaint, resolution.
- Never invent visits, payments, or outcomes not in the input.
- Use investigation_facts counts explicitly where provided (e.g., "3 field visits").
- Present chronology in order: complaint signal -> investigation activities -> observed evidence.
- combined_digest_en must not repeat resolution.text verbatim.
- resolution_text_public and findings_summary_public: write in the language indicated by
  primary_language ("ne" = Nepali, "en" = English). Other digests stay in English.
- No phone numbers, emails, or officer names in public fields.
- SEAH cases: minimal public findings; no third-party names or investigation tactics.
- If field reports conflict with notes, state the discrepancy.
- If insufficient documentation, say so briefly in combined_digest_en.
"""


def generate_resolved_case_summary_llm(
    bundle: dict,
    *,
    is_seah: bool = False,
    primary_language: str = "en",
) -> Optional[dict]:
    """LLM digests + complainant-facing narrative (spec §3.6.2, §3.9.2)."""
    if not bundle:
        return None

    payload = {**bundle, "primary_language": primary_language}
    user_content = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

    try:
        # ⚠ Complainant-facing: the two `*_public` fields are what a person reads at the end of
        # their grievance. This is the path where a truncated reply used to arrive as an empty one
        # and be recorded as `llm_failed`, which nothing retries (D-36/D-40) — so the complainant
        # was told the case was resolved and never received the document. `parse_response` refuses
        # a truncated reply instead of parsing it.
        return call_llm(
            findings_task(is_seah),
            [
                {"role": "system", "content": _RESOLVED_SUMMARY_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            schema=ResolvedCaseSummary,
            schema_name="resolved_case_summary",
            temperature=0.0,
            max_output_tokens=1200,
        ).model_dump()
    except (LLMTruncatedError, LLMParseError, ValidationError) as exc:
        logger.error("generate_resolved_case_summary_llm: unusable reply: %s", exc)
        return None
    except Exception as exc:
        logger.error("generate_resolved_case_summary_llm failed: %s", exc, exc_info=True)
        return None
