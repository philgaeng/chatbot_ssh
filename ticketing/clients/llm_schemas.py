# SPDX-License-Identifier: Apache-2.0

"""
Response schemas for the ticketing surface's structured LLM calls — DPG-13.

Two schemas, two audiences: `CaseFindings` is read by officers, `ResolvedCaseSummary` contains
the text a **complainant** receives at the end of their grievance. Both were `json_object` calls
whose "missing keys → fill defaults" branches existed precisely because the provider was free to
omit anything.

⚠ **Separate from the chatbot surface's schemas by design.** The service-layer boundary stands:
ticketing does not import `backend/services/`. What the two surfaces share is *configuration* —
`backend/config/llm_config.py`, which builds the `response_format` and owns the degradation
ladder, so both surfaces cannot ask the same provider for different things (DPG-17).

Spec: docs/sprints/2026-08-llm/02-llm-agnostic-spec.md §DPG-13
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CaseFindings(BaseModel):
    """`generate_case_findings` → `Ticket.ai_summary_en` + `TicketContextCache.findings_json`."""

    summary_en: str = ""
    key_findings: list[str] = Field(default_factory=list)
    recommended_action: str = ""
    urgency: Literal["HIGH", "MEDIUM", "LOW"] = "MEDIUM"
    languages_detected: list[str] = Field(default_factory=lambda: ["en"])


class ResolvedCaseSummary(BaseModel):
    """
    `generate_resolved_case_summary_llm` — the closure document.

    `resolution_text_public` and `findings_summary_public` are **complainant-facing**: they are
    what a person in a road-works village reads to learn what happened to their complaint. The
    remaining digests are the officer-facing investigation narrative.
    """

    field_reports_digest_en: str = ""
    other_notes_digest_en: str = ""
    combined_digest_en: str = ""
    resolution_text_public: str = ""
    findings_summary_public: str = ""
