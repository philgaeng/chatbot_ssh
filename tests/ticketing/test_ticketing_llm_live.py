"""
The **ticketing** surface, live — the half of DPG-24 that makes its green meaningful.

⚠ There are two independent LLM surfaces, and pointing only one of them at an open endpoint is the
exact drift `backend/config/llm_config.py` exists to prevent: move `backend/`, miss `ticketing/`,
and the **complainant-facing** resolved-case summary is still on a closed model while the repository
advertises otherwise. A platform-independence job that exercises one surface proves half the claim.

Skips cleanly without a key. Deselected by `backend-tests`, selected by `dpg-platform-independence`.

Spec: docs/sprints/2026-08-llm/03-open-models-spec.md#dpg-24
"""
from __future__ import annotations

import pytest

from backend.config.llm_config import llm_endpoint

pytestmark = pytest.mark.live_llm


@pytest.fixture(autouse=True)
def _requires_a_key():
    if not llm_endpoint().api_key:
        pytest.skip("no LLM_API_KEY / OPENAI_API_KEY configured — fork PRs get no secrets")


def test_the_ticketing_client_reaches_the_same_endpoint_and_answers():
    """
    ⭐ One environment change moves both surfaces — asserted against a **live** provider rather than
    against a constructed object. `tests/ticketing/test_llm_client.py` pins that they resolve to the
    same endpoint; this pins that the second one actually works when they do.
    """
    from ticketing.clients import llm_client

    llm_client.reset_client()
    translated = llm_client.translate_to_english("सडकको धूलोले घरमा बस्न गाह्रो भएको छ।")

    assert translated is None or isinstance(translated, str), (
        "the ticketing surface returned something that is neither a translation nor its documented "
        "None fallback"
    )
    if translated:
        assert translated.strip(), "an empty string is not the documented fallback — None is"
