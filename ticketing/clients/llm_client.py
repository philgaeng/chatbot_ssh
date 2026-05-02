"""
LLM client for the ticketing service.

Uses OpenAI gpt-4 — same provider as the chatbot backend (backend/services/LLM_services.py).
DO NOT import from backend/services/ — keep ticketing independent. Replicate the pattern here.

API key: OPENAI_API_KEY in env.local (already present, used by chatbot).
Init: get_settings().openai_api_key
"""

import json
import logging
import re
from typing import Optional

from openai import OpenAI

from ticketing.config.settings import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level client (lazy-init — avoids import-time errors if key is absent)
# ---------------------------------------------------------------------------
_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    """Return a cached OpenAI client, initialising on first call."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=30.0,
        )
    return _client


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
    Translate *text* to English using gpt-4.

    Returns the translated string, or None on error (caller logs and skips).
    If the text already looks like English, returns it unchanged without an API call.
    """
    if not text or not text.strip():
        return None

    if not _looks_non_english(text):
        logger.debug("translate_to_english: text looks English, skipping API call")
        return text

    client = _get_client()
    try:
        response = client.chat.completions.create(
            model="gpt-4",
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

# Model selection: cost vs. quality tradeoff
# Standard cases: gpt-4o-mini — indistinguishable quality for structured extraction,
#   ~15x cheaper than gpt-4o.
# SEAH cases: gpt-4o — more careful reasoning for sensitive investigations.
_MODEL_STANDARD = "gpt-4o-mini"
_MODEL_SEAH = "gpt-4o"


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

    model = _MODEL_SEAH if is_seah else _MODEL_STANDARD
    # Compact JSON — minimise tokens
    user_content = json.dumps(context, separators=(",", ":"), ensure_ascii=False)

    client = _get_client()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _FINDINGS_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            temperature=0.0,   # deterministic output
            max_tokens=400,
            response_format={"type": "json_object"},
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

        logger.info(
            "generate_case_findings: ok model=%s urgency=%s keys=%d",
            model, findings.get("urgency"), len(findings.get("key_findings", [])),
        )
        return findings

    except json.JSONDecodeError as exc:
        logger.error("generate_case_findings: invalid JSON from LLM: %s", exc)
        return None
    except Exception as exc:
        logger.error("generate_case_findings failed: %s", exc, exc_info=True)
        return None
