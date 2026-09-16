"""
The smoke probe's job is to tell three things apart, and only one of them is a model result.

  * the model **answered** — a measurement;
  * the model **refused a parameter** — also a measurement, and the one DPG-13's ladder consumes;
  * the **account** refused the request — 402, 401, 429 — which measures billing and nothing else.

⚠ **The third is why this file exists.** On 2026-08-20 the first run of `llm_smoke.py` rendered
`⚠ depleted your monthly included credits` as ❌ against `temperature` and `max_tokens`, which reads
exactly like *"this model does not support them"* — and it would have been pasted into `_PROFILES`
as a permanent conservative pin derived from an empty wallet. That is the D-44 shape: a
configuration error wearing the clothes of a quality finding, which
`docs/models/01_seah_detection_benchmark.md` §6.1 makes a standing requirement to guard against
because the SEAH path fails open and a 401 there reads as *"the model cannot detect harassment"*.

Spec: docs/sprints/2026-08-llm/03-open-models-spec.md#dpg-21
"""
from __future__ import annotations

import json

import pytest

from scripts.ops import llm_smoke


def _probe(name: str, outcome: str) -> llm_smoke.Probe:
    return llm_smoke.Probe(name=name, ok=(outcome == "pass"), outcome=outcome)


def _report(model: str, outcomes: dict[str, str]) -> llm_smoke.ModelReport:
    return llm_smoke.ModelReport(model=model, probes=[_probe(n, o) for n, o in outcomes.items()])


# ── The distinction ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "message",
    [
        "Error code: 402 - {'error': 'You have depleted your monthly included credits.'}",
        "Error code: 401 - {'error': 'Invalid credentials'}",
        "Error code: 429 - {'error': 'rate limit exceeded'}",
        "Error code: 503 - Service Unavailable",
        "Connection error.",
        "Request timed out.",
    ],
)
def test_an_account_or_transport_failure_is_blocked_not_refused(message, monkeypatch):
    """Each of these says nothing whatever about what the model can be told."""
    def boom():
        raise RuntimeError(message)

    # retries=0: the classification is what is under test, not the backoff. Rule 4.7 — a test that
    # sleeps is a test nobody runs, and this one would sleep 155 s per parametrisation.
    probe = llm_smoke._run("json_schema", boom, retries=0)

    assert probe.outcome == "blocked", f"{message!r} was classified as a model refusal"
    assert probe.ok is False


@pytest.mark.parametrize(
    "message",
    [
        "Error code: 400 - {'error': \"'response_format.type' must be 'text' or 'json_object'\"}",
        "Error code: 400 - {'error': 'Only the default (1) value is supported for temperature'}",
        "Error code: 400 - Unsupported parameter: max_tokens",
    ],
)
def test_a_400_on_a_parameter_is_a_refusal_and_therefore_a_measurement(message):
    """
    These are the rows DPG-13's ladder is built from — `gpt-3.5-turbo` 400s on `json_schema`,
    `gpt-4` 400s on `json_object` too. Misfiling one as `blocked` loses a real capability finding.
    """
    def boom():
        raise RuntimeError(message)

    assert llm_smoke._run("json_schema", boom, retries=0).outcome == "refused"


# ── The consequence: a blocked run may not produce a profile ─────────────────


def test_a_blocked_probe_stops_the_model_profile_being_emitted():
    """
    ⭐ The pin that matters. `_PROFILES` decides the strictest rung a model is *ever* asked for, in
    the code path that runs. A row derived from a 402 would pin permanent pessimism on evidence
    that measured nothing — and, worse, it would look exactly like a row that had been measured.
    """
    report = _report("openai/gpt-oss-120b", {
        "chat": "pass", "json_object": "pass", "json_schema": "pass",
        "temperature": "blocked", "max_tokens": "blocked",
    })

    assert report.any_blocked
    assert "NOT emitted" in report.profile_tuple
    assert "ModelProfile" not in report.profile_tuple


def test_a_clean_run_does_emit_a_pasteable_profile():
    report = _report("openai/gpt-oss-20b", {
        "chat": "pass", "json_object": "pass", "json_schema": "pass",
        "temperature": "pass", "max_tokens": "pass", "max_completion_tokens": "refused",
    })

    tuple_text = report.profile_tuple
    assert tuple_text.startswith('("gpt-oss-20b", ModelProfile("json_schema", True, "max_tokens"')
    assert "NOT emitted" not in tuple_text


def test_the_rung_degrades_rather_than_guessing_upward():
    """`json_schema` refused but `json_object` accepted must yield `json_object`, never the stronger."""
    assert _report("m", {"chat": "pass", "json_object": "pass", "json_schema": "refused"}).structured_output == "json_object"
    assert _report("m", {"chat": "pass", "json_object": "refused", "json_schema": "refused"}).structured_output == "prompt"


def test_the_cell_renderer_shows_three_states_not_two():
    report = _report("m", {"chat": "pass", "json_object": "refused", "json_schema": "blocked"})

    assert report.cell("chat") == "✅"
    assert report.cell("json_object") == "❌"
    assert report.cell("json_schema") == "⚠ blocked", (
        "a blocked cell rendered as ❌ is the whole defect this module guards — it reads as a "
        "model limitation and it is a billing state"
    )


# ── Silent degradation: accepted and ignored is not a pass ───────────────────


class _FakeChoice:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]
        self.usage = None


class _FakeCompletions:
    def __init__(self, schema_reply):
        self._schema_reply = schema_reply

    def create(self, **kwargs):
        if (kwargs.get("response_format") or {}).get("type") == "json_schema":
            return _FakeResponse(self._schema_reply)
        return _FakeResponse('{"category": "dust", "district": "Jhapa", "urgent": true}')


class _FakeClient:
    def __init__(self, schema_reply):
        self.chat = type("C", (), {"completions": _FakeCompletions(schema_reply)})()


def test_a_schema_request_that_was_accepted_but_ignored_is_not_a_pass():
    """
    ⚠ The failure this probe is shaped around. A provider that drops `response_format` returns 200
    with plausible JSON, so parsing it and calling that a pass proves nothing. The probe schema
    requires `district`, which the prompt never mentions — a reply without it was not constrained.
    """
    report = llm_smoke.probe_model(_FakeClient('{"category": "dust"}'), "fake/model")

    schema_probe = report.find("json_schema")
    assert schema_probe is not None and schema_probe.ok is False
    assert "NOT honoured" in schema_probe.detail
    assert report.structured_output == "json_object", "must fall to the rung that was honoured"


def test_a_schema_request_that_was_honoured_is_a_pass():
    honoured = json.dumps({"category": "dust", "district": "Jhapa", "urgent": True})
    report = llm_smoke.probe_model(_FakeClient(honoured), "fake/model")

    assert report.passed("json_schema")
    assert report.structured_output == "json_schema"


# ── The candidate list is data, and it has to stay loadable ─────────────────


def test_the_candidate_shortlist_loads_and_records_why_each_model_is_in_or_out():
    """
    The licence limb of the filter is provisional (Q-04-02), so widening the field must be an
    edit to this file rather than a redesign. That only holds if every row carries its reason.
    """
    data = json.loads(llm_smoke.CANDIDATES_FILE.read_text(encoding="utf-8"))

    assert data["shortlist"], "an empty shortlist would make DPG-23 unrunnable"
    for entry in data["shortlist"]:
        assert entry["why"].strip(), f"{entry['id']} is shortlisted with no stated reason"
    for entry in data["excluded"]:
        assert entry["reason"].strip(), f"{entry['id']} is excluded with no stated reason"
        assert entry["licence"], f"{entry['id']} is excluded without naming a licence"

    excluded_ids = {e["id"] for e in data["excluded"]}
    shortlist_ids = {e["id"] for e in data["shortlist"]}
    assert not (excluded_ids & shortlist_ids), "a model cannot be both shortlisted and excluded"


# ── The backoff, with the clock injected ────────────────────────────────────


def test_a_blocked_probe_is_retried_before_it_is_believed(monkeypatch):
    """
    ⚠ The provider reports a short-window **rate limit** with the words *"You have depleted your
    monthly included credits"*. Measured 2026-08-20: probing seven candidates in one run blocked
    after the first model's six calls, and probing the same models one at a time seconds later
    passed every one. A harness that believes the message publishes *unmeasurable* for a model that
    works — which is the same class of error as believing a 402 is a capability limit, one level up.
    """
    slept: list[float] = []
    monkeypatch.setattr(llm_smoke.time, "sleep", slept.append)
    attempts = {"n": 0}

    def blocked_then_fine():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("Error code: 402 - depleted your monthly included credits")
        return _FakeResponse('{"ok": true}')

    probe = llm_smoke._run("chat", blocked_then_fine)

    assert probe.outcome == "pass", "gave up on a rate limit that would have cleared"
    assert attempts["n"] == 3
    assert len(slept) == 2 and slept == list(llm_smoke.BLOCKED_BACKOFF_S[:2])


def test_a_model_refusal_is_never_retried(monkeypatch):
    """A 400 on `json_schema` is the answer, not an obstacle. Retrying it wastes money and time."""
    slept: list[float] = []
    monkeypatch.setattr(llm_smoke.time, "sleep", slept.append)
    attempts = {"n": 0}

    def always_400():
        attempts["n"] += 1
        raise RuntimeError("Error code: 400 - response_format.type must be text or json_object")

    assert llm_smoke._run("json_schema", always_400).outcome == "refused"
    assert attempts["n"] == 1, "a model refusal was retried"
    assert not slept


def test_a_persistent_block_says_how_hard_it_tried(monkeypatch):
    monkeypatch.setattr(llm_smoke.time, "sleep", lambda _s: None)

    def always_402():
        raise RuntimeError("Error code: 402 - depleted your monthly included credits")

    probe = llm_smoke._run("chat", always_402, retries=2)

    assert probe.outcome == "blocked"
    assert "still blocked after 2 retries" in probe.detail, (
        "a persistent block must record that it was retried, or the next reader repeats the work"
    )
