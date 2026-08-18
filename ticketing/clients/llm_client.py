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
    findings_task,
    llm_endpoint,
    model_for,
    response_format_kwargs,
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

    task = model_for("ticket_translate")
    client = _get_client()
    try:
        response = client.chat.completions.create(
            model=task.model,
            timeout=task.timeout,
            messages=[
                {"role": "system", "content": _TRANSLATE_SYSTEM},
                {"role": "user", "content": text},
            ],
            temperature=0.2,
            max_tokens=1024,
        )
        translated = response.choices[0].message.content or ""
        return translated.strip() or None
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

    task = model_for(findings_task(is_seah))
    model = task.model
    # Compact JSON — minimise tokens
    user_content = json.dumps(context, separators=(",", ":"), ensure_ascii=False)

    client = _get_client()
    try:
        response = client.chat.completions.create(
            model=model,
            timeout=task.timeout,
            messages=[
                {"role": "system", "content": _FINDINGS_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            temperature=0.0,   # deterministic output
            max_tokens=400,
            **response_format_kwargs(
                "case_findings", CaseFindings.model_json_schema(), task.structured_output
            ),
        )
        raw = (response.choices[0].message.content or "").strip()
        if not raw:
            logger.error("generate_case_findings: empty response from LLM (model=%s)", model)
            return None

        findings = json.loads(raw)

        # Validate required keys are present
        required = {"summary_en", "key_findings", "recommended_action", "urgency"}
        missing = required - findings.keys()
        if missing:
            logger.warning(
                "generate_case_findings: LLM response missing keys %s — filling defaults",
                missing,
            )
            findings.setdefault("summary_en", "")
            findings.setdefault("key_findings", [])
            findings.setdefault("recommended_action", "")
            findings.setdefault("urgency", "MEDIUM")
        findings.setdefault("languages_detected", ["en"])

        # DPG-13: the branch above is unreachable on the `json_schema` rung — strict mode requires
        # every declared property — and is kept because the weaker rungs are real configurations,
        # not hypotheticals (`gpt-4` rejects JSON mode outright; measured, not assumed). Validation
        # is what makes a type violation visible: `key_findings` as a string used to travel all the
        # way into `findings_json` and fail wherever something iterated it.
        findings = CaseFindings.model_validate(findings).model_dump()

        logger.info(
            "generate_case_findings: ok model=%s urgency=%s keys=%d",
            model, findings.get("urgency"), len(findings.get("key_findings", [])),
        )
        return findings

    except (json.JSONDecodeError, ValidationError) as exc:
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

    task = model_for(findings_task(is_seah))
    payload = {**bundle, "primary_language": primary_language}
    user_content = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

    client = _get_client()
    try:
        response = client.chat.completions.create(
            model=task.model,
            timeout=task.timeout,
            messages=[
                {"role": "system", "content": _RESOLVED_SUMMARY_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            temperature=0.0,
            max_tokens=1200,
            **response_format_kwargs(
                "resolved_case_summary",
                ResolvedCaseSummary.model_json_schema(),
                task.structured_output,
            ),
        )
        raw = (response.choices[0].message.content or "").strip()
        if not raw:
            return None
        out = json.loads(raw)
        for key in (
            "field_reports_digest_en",
            "other_notes_digest_en",
            "combined_digest_en",
            "resolution_text_public",
            "findings_summary_public",
        ):
            out.setdefault(key, "")
        # Complainant-facing output: the two `*_public` fields are what a person reads at the end
        # of their grievance. Validated for the same reason the officer-facing one is, with more
        # at stake if it is malformed.
        return ResolvedCaseSummary.model_validate(out).model_dump()
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.error("generate_resolved_case_summary_llm: unusable reply: %s", exc)
        return None
    except Exception as exc:
        logger.error("generate_resolved_case_summary_llm failed: %s", exc, exc_info=True)
        return None
