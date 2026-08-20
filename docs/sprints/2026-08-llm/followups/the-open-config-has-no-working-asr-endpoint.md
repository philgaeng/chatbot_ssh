# Follow-up — `.env.open`'s ASR endpoint does not exist

> **Raised:** 2026-08-20, probing for [DPG-22](../03-open-models-spec.md#dpg-22).
> **Logged as deviation D-53** in [`../PROGRESS.md`](../PROGRESS.md).
> **Status:** ⬜ **OPEN.** The committed open configuration cannot transcribe. Nothing breaks today
> because voice is switched off, but the file claims a capability it does not have.
> **Size:** S to correct the claim. M–L to make it true.

---

## The finding

[`.env.open`](../../../../.env.open) ships:

```env
ASR_BASE_URL=https://router.huggingface.co/v1
MODEL_ASR=openai/whisper-large-v3
```

**`https://router.huggingface.co/v1/audio/transcriptions` returns HTTP 404.** Verified 2026-08-20
with a valid token and a real 1-second WAV, for `openai/whisper-large-v3`,
`openai/whisper-large-v3-turbo`, and a provider-pinned form.

**It is not an authentication or a billing problem**, and the three controls say so:

| Request | Result | What it tells us |
|---|---|---|
| `GET /v1/models` with the token | **200** | the token is valid |
| `POST /v1/chat/completions` with the token | **200** | the account can spend |
| `POST /v1/audio/transcriptions` **without** a token | **401** | the route exists and authenticates first |
| `POST /v1/audio/transcriptions` **with** the token | **404** | …and then serves nothing for these models |

And the router's own catalogue agrees: `GET /v1/models` returns **132 models, none of them audio** —
it is a chat-completions catalogue. Hugging Face Inference Providers serves ASR, but **not through
the OpenAI-compatible `/v1/audio/*` surface** the code calls.

## Why nothing noticed

Three layers of "switched off" stacked up:

1. **Voice transcription is not live** and never has been — no budget for it
   ([Q-13.2](../DECISIONS.md)). The four voice-flow functions are declared `PARKED`
   (`PARKED_TASKS`, DPG-19b).
2. **`.env.open` is a template.** Nothing in CI or the stack loads it, so its values were never
   resolved against a live endpoint — they were plausible, and plausible was as far as it got.
   The file says so itself: *"⚠ These names are UNMEASURED placeholders."*
3. **[DPG-21's smoke script has an `--audio` probe](../../../../scripts/ops/llm_smoke.py) and it was
   never run**, because there is no audio file in the repository to run it against
   ([followup](no-audio-subset-for-asr-benchmark.md)).

⚠ **Layer 3 is the one worth learning from.** The tool that would have caught this was written the
same day and skipped for want of a one-second WAV. The live test now
(`tests/backend/test_llm_live.py`) **generates** its probe audio rather than depending on a
committed file — one second of silence, from the `wave` module — precisely so this class of check
cannot be blocked by a missing fixture again.

## What it does *not* mean

⚠ **The indicator-4 claim is unaffected for text**, which is nine of the ten call sites and all of
the live ones. What is affected is the sentence *"the open configuration runs the whole system"* —
for **transcription**, on the endpoint currently committed, it does not.

Nothing in production breaks: voice is off. This is a **documentation defect that would have become
a runtime defect** the day voice was switched on with `.env.open` loaded.

## Options

| Option | What it costs | Note |
|---|---|---|
| **Point `ASR_BASE_URL` at a provider that does serve OpenAI-compatible audio** (Fireworks, DeepInfra, Groq, or a Whisper-hosting service) | An account and a key. The registry already keeps ASR's base URL and key **separate** from chat's, precisely so they can live on different providers | ⭐ Cheapest, and the separation DPG-17 built exists for exactly this |
| **Call HF's non-OpenAI inference API for audio** | A second client shape in `llm_client.py` | ⚠ Costs the property that makes this codebase portable: every call today is OpenAI-compatible. Weigh carefully |
| **Self-host Whisper on vLLM** — vLLM *does* expose `/v1/audio/transcriptions` | A GPU and an owner | This is [T2](../../../dpg/vllm-deployment.md), which is parked for exactly that reason. It would make the open ASR claim true |
| **Say plainly that open ASR is unserved** and leave the variables empty | Nothing | The honest floor if none of the above is funded. Better than a config that 404s |

**Recommended: correct `.env.open` now** (option 4 as the interim truth), and take option 1 when
someone can open an account — the registry's separate ASR endpoint fields already make it a
two-line change.

## Definition of done

- [ ] `.env.open` no longer claims a transcription endpoint that 404s — either corrected to a
      working provider or emptied with the reason stated inline
- [ ] `docs/dpg/open-model-configuration.md` says which parts of the system the open configuration
      serves and which it does not — **text yes, audio not yet**
- [ ] `docs/services/03_voice_grievance_service.md` records it, since that is where a reader looking
      for the voice path will arrive
- [ ] The `--audio` probe is run against whatever replaces it, and the result recorded
- [ ] ⚠ **Do not close this by deleting the ASR variables from the registry.** The separation of ASR
      and chat endpoints is load-bearing — it is what makes option 1 a two-line change

## Related

- [`no-audio-subset-for-asr-benchmark.md`](no-audio-subset-for-asr-benchmark.md) — the other half of DPG-22's blockage
- [`../../../dpg/vllm-deployment.md`](../../../dpg/vllm-deployment.md) §1 — T2 would serve this
- [`../../../dpg/open-model-configuration.md`](../../../dpg/open-model-configuration.md)
- [`../../../TODO.md`](../../../TODO.md)
