# Follow-up — a Nepali ASR fine-tune would be a genuine DPG *contribution*, not just a dependency

> **Raised:** 2026-08-20, logged out of [DPG-22](../03-open-models-spec.md#dpg-22) as its acceptance
> criteria require. **Out of scope for Sprint 2** — this is a research task with a GPU bill, not a
> ticket.
> **Status:** ⬜ **OPEN — an opportunity, not a defect.** Nothing is broken because of it.
> **Size:** M–L. A single-GPU fine-tune is days of compute; doing it *properly* — evaluation,
> model card, licence, publication — is a small project.

---

## The opportunity

**OpenSLR SLR54** is roughly **165 hours of openly-licensed Nepali speech**. The 2026 comparative
study cited in DPG-22 fine-tuned six architectures on it and evaluated on OpenSLR, FLEURS and
Common Voice, reaching **14.76% WER** with Whisper-Large-v3-Turbo and **14.89%** with IndicWav2Vec —
statistically tied, under permissive licences.

Two things follow, and the second is the interesting one:

1. **~85% word accuracy on Nepali is achievable under a permissive licence.** That is usable for
   grievance intake *with on-screen confirmation*, and it is above the threshold where correcting a
   transcript is slower than re-entering it.
2. ⭐ **The fine-tune is a single-GPU job, and releasing it openly would be a real contribution to
   the commons** — permissively-licensed Nepali speech tooling barely exists. `ai4bharat/
   indicwav2vec_v1_nepali` has **0 downloads**; that is the state of the field.

## Why this is worth more than a better WER

DPG indicator 4 is about not depending on a proprietary component. This project currently *consumes*
open models. **Publishing a Nepali ASR fine-tune would make it a project that gives something back**
— which is a materially stronger position in a Digital Public Goods submission than compliance
alone, and it is the kind of artefact a reviewer remembers.

⚠ **And it is the honest answer to the harder question**, if it turns out open Nepali ASR is
materially worse than a hosted alternative. The options in that case are: accept documented
degradation on voice while text stays at parity; keep ASR closed and **disclose it as a remaining
proprietary dependency**; or **fund a fine-tune**. Only the third one improves the situation for
anybody other than this project.

## Prerequisites, in order

1. ⚠ **A working ASR endpoint at all.** `.env.open`'s currently returns 404
   ([followup](the-open-config-has-no-working-asr-endpoint.md)). Fine-tuning a model that cannot be
   served is the wrong order.
2. ⚠ **An evaluation set.** SLR54 has its own held-out split, which is enough to *train* against —
   but this project's own voice notes are road noise, code-switching and a self-identification
   preamble, and SLR54 is **read speech**. A fine-tune evaluated only on read speech will report a
   number that does not describe this system
   ([followup](no-audio-subset-for-asr-benchmark.md)).
3. **Someone to own the model card, the licence and the publication.** An unmaintained model on a
   hub is worse than none — it acquires citations and then rots. This is the same failure mode as
   Q-05's unowned GPU, and it deserves the same scepticism.

## What would make it real

- [ ] Baseline WER for the off-the-shelf candidates on **this project's** audio, not only on SLR54
- [ ] A fine-tune on SLR54, evaluated on **both** SLR54's split and this project's audio, reported
      separately — where they disagree, the project's own number is the one that describes reality
- [ ] Licence and provenance for the training data stated on the model card
- [ ] A named maintainer, or an explicit *"released as-is, unmaintained"* — said out loud, not implied
- [ ] The result folded back into [`model-benchmarks.md`](../../../dpg/model-benchmarks.md) and cited
      in the indicator-4 answer

## Related

- [`../03-open-models-spec.md#dpg-22`](../03-open-models-spec.md#dpg-22) — where this was scoped out
- [`no-audio-subset-for-asr-benchmark.md`](no-audio-subset-for-asr-benchmark.md) — prerequisite 2
- [`the-open-config-has-no-working-asr-endpoint.md`](the-open-config-has-no-working-asr-endpoint.md) — prerequisite 1
- [`../../../services/03_voice_grievance_service.md`](../../../services/03_voice_grievance_service.md) — the consumer, and the verified licence table
- [`../../../TODO.md`](../../../TODO.md)
