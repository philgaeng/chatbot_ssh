# Follow-up — the benchmark set has no audio, so DPG-22 cannot measure WER

> **Raised:** 2026-08-20, building [DPG-20](../03-open-models-spec.md#dpg-20).
> **Status:** ⬜ **OPEN — blocking [DPG-22](../03-open-models-spec.md#dpg-22)'s central number.**
> **Size:** S to produce (a phone, a quiet room, six people), M to do properly (script mix, noise
> conditions, consent for the voices).

---

## The finding

DPG-20's acceptance says *"Voice subset has verbatim transcripts"*, and DPG-22 computes **word error
rate** against them. WER needs **audio**: a recording, and the words that were actually said.

`tests/data/benchmark/` contains **six voice-origin items and no audio at all**. They are
transcript-*shaped* text — no field boundaries, self-identification in the opening sentence, fillers,
one long run-on — which is genuinely different from typed intake and is what the **classification**
and **extraction** tasks consume. It is not what a **transcription** task consumes.

**Nothing in this repository can author a recording.** Synthesising audio with TTS would not close
the gap either, and the reason is the same one the set exists for: TTS output is cleaner than a
person on a rural mobile connection, so a WER measured on it would flatter every candidate and
measure a problem the system does not have.

## What this costs, precisely

DPG-22's other acceptance items are still reachable — licence verification per candidate, p95
latency, cost per 1,000 minutes, and the honest empty baseline column (voice has never been live —
[Q-13.2](../DECISIONS.md)). **What is not reachable is the number the ticket is named after.**

⚠ And note what it does *not* cost: nothing in production. Voice transcription is switched off and
its four flow functions are declared `PARKED` (`PARKED_TASKS` in `backend/task_queue/registered_tasks.py`,
DPG-19b). This blocks a **measurement**, not a feature.

## What would close it

Six to twenty recordings, each with a verbatim transcript, covering:

| Dimension | Why it must vary |
|---|---|
| **Script of the transcript** | Devanagari and Romanised Nepali are different transcription targets, not one |
| **Speaker** | WER on one voice is a sample of size one |
| **Recording condition** | A quiet room and a roadside are different problems; the second is the real one |
| **Length** | Latency is measured *at realistic audio lengths* — a 12-second note and a 90-second one are different rows |
| **Code-switching** | Speakers switch mid-sentence; ASR models vary wildly on this |

**The same rule as the rest of the set applies: no real grievance may be recorded for this.** These
are read from authored scripts — the six `voice_origin` items already in
`general_classification.jsonl` are the obvious starting scripts, since their transcripts are already
written and already labelled for classification. That also buys something: the same clip can then be
scored end-to-end — transcription **and** the classification of what came out of it — which is closer
to what a complainant actually experiences than either number alone.

## An alternative worth pricing before recording anything

**OpenSLR SLR54** (~165 hours of openly-licensed Nepali speech) is the corpus the 2026 comparative
study fine-tuned and evaluated on, and it is the source of the 14.76% WER figure quoted in DPG-22.
Evaluating candidates on a held-out slice of SLR54 gives a **comparable, citable, reproducible**
number for nothing but compute.

⚠ **It is not a substitute, it is a complement.** SLR54 is read speech, not grievances on a phone:
no road noise, no code-switching, no self-identification preamble. It answers *"how good is this
model at Nepali"*; it does not answer *"how good is this model at our voice notes"*. Report both, and
say which is which — the same rule as gold-seed versus expanded in the SEAH method doc.

## Related

- [`../03-open-models-spec.md#dpg-22`](../03-open-models-spec.md#dpg-22) — the ticket
- `tests/data/benchmark/README.md` §7 — where the absence is stated in the set's own documentation
- [`../../../services/03_voice_grievance_service.md`](../../../services/03_voice_grievance_service.md) — the consumer
- [`../../../TODO.md`](../../../TODO.md) — the backlog row
