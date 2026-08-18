# SPDX-License-Identifier: Apache-2.0

"""
Response schemas for the chatbot surface's structured LLM calls — DPG-13.

**Why a schema instead of "return strict JSON" in the prompt.** Two of this surface's call sites
asked for JSON in words and hoped: `classify_and_summarize_grievance` — the product's primary AI
path — and `translate_grievance_to_english_LLM`. A malformed reply from either was absorbed by
`parse_llm_response`'s `except JSONDecodeError → return {}`, which is **indistinguishable from a
successful empty classification**. Nobody could see the difference, including the tests.
An explicit schema constrains generation to the grammar, so the output is *guaranteed* parseable
rather than probably parseable — and where the provider cannot honour that, the ladder in
`backend/config/llm_config.py` degrades and says which rung it used.

⚠ **Categories are deliberately `list[str]`, not an enum.** They come from `CLASSIFICATION_DATA` /
`LIST_OF_CATEGORIES` and are resynced into `public.grievance_classification_taxonomy`; the
taxonomy is admin-configurable. Freezing a `Literal[...]` of today's categories into a schema
would mean a code change every time an administrator adds one, and would break the resync path.
Membership is checked *after* parsing, against the live catalogue, and a value outside it is
logged rather than rejected — the model choosing an unlisted category is a prompt problem, not a
reason to throw away a complainant's classification.

These models are written to be **wrapped, not edited**, by DPG-33: Sprint 3 hooks redaction at
the model-call boundary, and it needs one place per call site to reach.

Spec: docs/sprints/2026-08-llm/02-llm-agnostic-spec.md §DPG-13
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, create_model, field_validator


class GrievanceClassification(BaseModel):
    """`classify_and_summarize_grievance` — the primary AI path."""

    grievance_summary: str = ""
    grievance_categories: list[str] = Field(default_factory=list)
    grievance_categories_alternative: list[str] = Field(default_factory=list)
    follow_up_question: str = ""


class ContactExtractionAll(BaseModel):
    """`extract_all_contact_info` — six fields, all optional in practice."""

    complainant_phone: str = ""
    complainant_full_name: str = ""
    complainant_district: str = ""
    complainant_municipality: str = ""
    complainant_village: str = ""
    complainant_address: str = ""


class GrievanceTranslation(BaseModel):
    """`translate_grievance_to_english_LLM` — the English record of a grievance."""

    grievance_description_en: str = ""
    grievance_summary_en: str = ""
    # The model is asked for "a number between 0 and 1" and returns it as a string about as often
    # as not. Accepting both is honest about the provider's behaviour; coercing it here would
    # invent precision the response does not carry.
    confidence_score: str | float = ""


class SensitiveContentDetection(BaseModel):
    """
    `detect_sensitive_content_llm` — the SEAH path.

    ⚠ **The clamps normalise; they must not reject.** This is the harassment-detection path, and
    the difference matters: a model that answers `level: "critical"` has still told us it detected
    something. Rejecting the whole reply would fail open to `detected: False` — turning an
    out-of-range *label* into a missed report. So the validators below run **before** the type
    check and coerce, which is what "the clamp becomes structural" (DPG-13) has to mean here.

    The `Literal` stays so `model_json_schema()` still sends the enum to the provider — constrain
    the generation, forgive the reply.
    """

    detected: bool = False
    level: Literal["high", "medium", "low"] = "low"
    message: str = ""

    @field_validator("level", mode="before")
    @classmethod
    def _clamp_level(cls, value: object) -> str:
        return value if value in ("high", "medium", "low") else "low"

    @field_validator("message", mode="before")
    @classmethod
    def _coerce_message(cls, value: object) -> str:
        if value is None:
            return ""
        return value if isinstance(value, str) else str(value)[:200]


def single_field_contact_schema(field_name: str) -> type[BaseModel]:
    """
    `extract_contact_info` builds its schema per call: the key is computed at runtime from
    `USER_FIELDS`, so there is no static model to write. Constructed rather than special-cased
    away — a call site that cannot use the schema layer is a call site that quietly stays on the
    weakest rung.
    """
    return create_model(  # type: ignore[call-overload]
        "ContactExtraction",
        **{field_name: (str, "")},
    )
