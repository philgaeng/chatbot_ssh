"""
Real round-trips against the configured provider — DPG-24's `live_llm` suite.

**What this suite is for, and what it is not.** It is the strongest indicator-4 evidence available:
the product's own call path, green against the **open** configuration, on every commit. It is not a
quality benchmark — accuracy lives in `scripts/ops/llm_benchmark.py` and produces numbers, not a
pass/fail. ⚠ A benchmark asserted as a threshold becomes a flaky test the first time a provider
changes a model behind a tag, which is why `docs/engineering/04_testing.md` keeps them apart.

**Every test here skips cleanly when no key is configured.** Fork PRs get no secrets, and a red X on
every external contribution is precisely the wrong signal for a public-good repository.

⚠ **These cost money.** They are deselected by `backend-tests` and selected by
`dpg-platform-independence`. See `pytest.ini` for why that split is a dependency and not a
quarantine, and the job header in `.github/workflows/ci.yml` for why the job is never a required
status check.

Spec: docs/sprints/2026-08-llm/03-open-models-spec.md#dpg-24
"""
from __future__ import annotations

import io
import struct
import wave

import pytest

from backend.config.llm_config import get_llm_settings, llm_endpoint, model_for
from tests.llm_live_helpers import live_call

pytestmark = pytest.mark.live_llm


@pytest.fixture(autouse=True)
def _requires_a_key():
    """
    Skip, never fail, when there is no credential.

    ⚠ This is also the line between *"the provider refused"* and *"nobody configured a key"*, which
    D-50 showed is worth being explicit about: an unconfigured run that fails looks identical to a
    broken provider, and the second one is worth waking up for.
    """
    if not llm_endpoint().api_key:
        pytest.skip("no LLM_API_KEY / OPENAI_API_KEY configured — fork PRs get no secrets")


class _Reply(pytest.importorskip("pydantic").BaseModel):
    """Deliberately small. This asserts the transport and the shaping, not the model's judgement."""

    category: str
    urgent: bool


# ── T-24-a — the chat surface, end to end ───────────────────────────────────


def test_a_real_structured_round_trip_against_the_configured_endpoint():
    """
    ⭐ The whole indicator-4 claim in one assertion: the chatbot's own entry point, its own registry,
    its own request shaping, against whatever `LLM_BASE_URL` names — and a parsed object comes back.

    It asserts the **shape**, not the answer. `category` being a non-empty string proves the model
    was reached, the rung was accepted, and the reply parsed. Asserting *which* category would make
    this a benchmark, and a flaky one.
    """
    from backend.services.llm_client import call_llm

    reply = live_call(lambda: call_llm(
        "classify",
        schema=_Reply,
        schema_name="live_probe",
        messages=[
            {"role": "system", "content": "You classify road-project grievances. Reply as JSON."},
            {"role": "user", "content":
                "Construction dust from the road works is entering our house and the children are ill."},
        ],
    ))

    assert isinstance(reply.category, str) and reply.category.strip(), "empty content from a live call"
    assert isinstance(reply.urgent, bool)


def test_the_endpoint_the_test_reached_is_the_one_the_registry_names():
    """
    Guards against the most embarrassing possible false green: this job passing against OpenAI while
    reporting that the open configuration works. The job sets `LLM_BASE_URL`; this asserts the
    product actually read it.
    """
    endpoint = llm_endpoint()
    task = model_for("classify")

    assert task.endpoint.host == endpoint.host
    assert task.model, "no model resolved for `classify`"


# ── T-24-b — the transcription surface ──────────────────────────────────────


def _one_second_of_silence() -> io.BytesIO:
    """
    A valid 16-bit mono WAV, generated rather than committed.

    ⚠ It measures **nothing about accuracy** — there is no audio benchmark set
    (`followups/no-audio-subset-for-asr-benchmark.md`). What it proves is that the ASR endpoint, the
    model id and the **SDK keyword** all work, and that last one is not hypothetical: DPG-14.3 found
    every transcription raising `TypeError` because the code passed `language_code` where the SDK
    takes `language`, on a path nothing in production exercised. This test is the thing that would
    have caught it.
    """
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(struct.pack("<16000h", *([0] * 16000)))
    buffer.seek(0)
    buffer.name = "probe.wav"
    return buffer


@pytest.mark.xfail(
    strict=True,
    reason=(
        "D-53 — the configured open ASR endpoint has no transcription route. "
        "https://router.huggingface.co/v1/audio/transcriptions returns 404 for every whisper id "
        "tried, while /v1/models and /v1/chat/completions return 200 on the same token, and the "
        "router's catalogue holds 132 models and no audio. "
        "⚠ strict=True ON PURPOSE: the day someone points ASR at a provider that DOES serve audio, "
        "this xpasses and the job goes red — which is the signal to DELETE THIS MARKER and record "
        "that open transcription now works. A non-strict xfail would sit here forever after being "
        "fixed, which is the marker-nobody-reads pattern. "
        "Tracked: docs/sprints/2026-08-llm/followups/the-open-config-has-no-working-asr-endpoint.md"
    ),
)
def test_a_real_transcription_round_trip():
    from backend.services.llm_client import get_asr_client

    client = get_asr_client()
    result = live_call(lambda: client.audio.transcriptions.create(
        model=get_llm_settings().model_asr,
        file=_one_second_of_silence(),
        language="ne",
    ))

    # Silence transcribes to "" or to noise; both are fine. What must hold is that the call
    # completed and returned the documented shape.
    assert hasattr(result, "text"), f"no `text` on the transcription reply: {result!r}"
    assert isinstance(result.text, str)


# ── The degradation ladder, live ────────────────────────────────────────────


def test_the_structured_rung_the_registry_picked_is_one_the_provider_accepts():
    """
    DPG-13's ladder degrades from `json_schema` to `json_object` to `prompt`, and `_PROFILES` decides
    where a given model starts. A wrong profile entry is a 400 on every call in production and a
    green unit suite, because the unit suite mocks the provider — so the rung is only ever really
    tested here.
    """
    from backend.services.llm_client import call_llm

    task = model_for("classify")
    assert task.structured_output in ("json_schema", "json_object", "prompt")

    reply = live_call(lambda: call_llm(
        "classify", schema=_Reply, schema_name="live_rung",
        messages=[{"role": "user", "content": "A truck damaged our paddy field. Reply as JSON."}],
    ))
    assert reply.category.strip(), (
        f"the {task.structured_output!r} rung was accepted but produced nothing usable on "
        f"{task.model!r} — check its _PROFILES entry"
    )
