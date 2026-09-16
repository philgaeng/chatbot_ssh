# Follow-up — the end-to-end test against a live vLLM endpoint is deferred

> **Raised:** 2026-08-20, with [DPG-25](../03-open-models-spec.md#dpg-25), which requires this
> deferral to be logged explicitly rather than dropped.
> **Status:** ⏸ **DEFERRED — cannot run without an instance.**
> **Size:** S once an instance exists. Unbounded until then, because the instance is the work.

---

## What is deferred

A test that starts vLLM on the chosen open model, points `LLM_BASE_URL` at it, and runs the LLM
suite green. Nothing more exotic than that — and nothing less.

## Why it matters more than it sounds

**It is the step that turns *"documented"* into *"demonstrated"*.**
[`docs/dpg/vllm-deployment.md`](../../../dpg/vllm-deployment.md) asserts that the same code serves T2
with only a base-URL change. That assertion is **well-founded and untested**:

| Evidence we have | Evidence we do not |
|---|---|
| Every model, endpoint and timeout resolves from one registry, pinned by tests | Nobody has pointed this code at a vLLM instance |
| One env change moves **both** LLM surfaces, asserted in a test | vLLM's `/v1/chat/completions` accepts our exact request shape — including `response_format` |
| The open configuration works against a hosted router — measured | vLLM's guided decoding honours DPG-13's schemas as the router does |
| vLLM documents an OpenAI-compatible API and a `/v1/audio/transcriptions` route | ⚠ That route **matters here**, because the hosted router does **not** expose it (D-53) — so T2 is currently the *only* configuration that could serve ASR, and that is precisely the untested claim |

⚠ **Do not upgrade the wording while this is open.** "Documented and costed" is accurate; "supported"
and "verified" are not, and the ladder in three documents now says so deliberately.

## What would close it

- [ ] A vLLM instance on the chosen text model — a spot GPU for an afternoon is enough; this does
      **not** require unparking T2 or funding a running instance
- [ ] `LLM_BASE_URL` pointed at it, `pytest -m live_llm` green against **both** surfaces
- [ ] `response_format` with a `json_schema` verified as **honoured, not merely accepted** — the same
      probe `scripts/ops/llm_smoke.py` already applies (a required field the prompt never mentions)
- [ ] ⭐ `/v1/audio/transcriptions` exercised, since that is the one thing T2 can do that T1 currently
      cannot (D-53)
- [ ] The result recorded in [`vllm-deployment.md`](../../../dpg/vllm-deployment.md), and the ladder's
      status upgraded from *documented* to *demonstrated* — **in every place that describes it**

⚠ **The cheap version is worth doing even while T2 stays parked.** An afternoon on a rented GPU
converts the strongest untested claim in the DPG submission into a measured one, and it costs
nothing like the running instance the parking decision was about. **Parking the deployment is not the
same as parking the proof**, and conflating them is how this stays deferred forever.

## Related

- [`../../../dpg/vllm-deployment.md`](../../../dpg/vllm-deployment.md) — the claim under test
- [`the-open-config-has-no-working-asr-endpoint.md`](the-open-config-has-no-working-asr-endpoint.md) — why the audio route is the interesting half
- [`../../../deployment/13_security.md`](../../../deployment/13_security.md) §8.1 — the posture, `⚠ not deployed`
- [`../../../TODO.md`](../../../TODO.md)
