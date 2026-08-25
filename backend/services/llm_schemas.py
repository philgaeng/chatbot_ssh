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

⚠ **Categories carry an enum on the wire and stay `list[str]` in Python** (changed 2026-08-25,
D-51). The enum is **built per call from the live catalogue** by `grievance_classification_schema`,
so nothing is frozen: an administrator adding a category still needs no code change, and the
resync path is untouched. That was the whole objection to the `Literal[...]` this replaces, and it
is answered by building the schema instead of writing it.

The Python type stays `list[str]` on purpose — *constrain the generation, forgive the reply*, the
same trade `SensitiveContentDetection` makes below. A model that ignores the enum must not cost
the complainant their summary as well, so membership is still settled after parsing, by
`backend/services/category_resolution.py`. What changed is the verdict: an off-catalogue value is
**repaired onto the catalogue or dropped**, never stored. It was stored for months — logged, and
then written to `grievance_categories` anyway, where it matched no filter, no report and no
`high_priority` lookup (`docs/dpg/model-benchmarks.md` §3.1).

These models are written to be **wrapped, not edited**, by DPG-33: Sprint 3 hooks redaction at
the model-call boundary, and it needs one place per call site to reach.

Spec: docs/sprints/2026-08-llm/02-llm-agnostic-spec.md §DPG-13
"""
from __future__ import annotations

from typing import Literal, Sequence

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


def grievance_classification_schema(catalogue: Sequence[str]) -> type[BaseModel]:
    """
    `GrievanceClassification` with this call's catalogue as an enum on both category fields.

    Built rather than written because the catalogue is admin-configurable and read at call time.
    The enum is the cheap half of the D-51 fix: on a provider that honours `json_schema` the model
    *cannot* emit a category that does not exist, so the repair path below it never runs.

    ⚠ **It is not a guarantee, and must not be treated as one.** `Qwen3.5-9B` accepts a
    `json_schema` and does not honour it (`backend/config/llm_config.py`), the ladder degrades to
    `json_object` or to words on models that cannot do better, and `interactive` retries change
    nothing about that. `resolve_categories` is what actually holds the boundary; this only makes
    it rare that it has to.

    Falls back to the plain model when the catalogue is empty — an empty enum is not a valid JSON
    Schema, and a taxonomy that failed to load is not a reason to fail the classification.
    """
    if not catalogue:
        return GrievanceClassification
    items = {"type": "string", "enum": list(catalogue)}
    return create_model(  # type: ignore[call-overload]
        "GrievanceClassificationEnumerated",
        __base__=GrievanceClassification,
        grievance_categories=(
            list[str],
            Field(default_factory=list, json_schema_extra={"items": items}),
        ),
        grievance_categories_alternative=(
            list[str],
            Field(default_factory=list, json_schema_extra={"items": items}),
        ),
    )


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
