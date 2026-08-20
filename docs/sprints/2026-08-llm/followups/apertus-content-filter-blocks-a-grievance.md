# Follow-up — Apertus refused a grievance about children falling ill

> **Raised:** 2026-08-20, by [DPG-21](../03-open-models-spec.md#dpg-21)'s capability probe.
> **Logged as deviation D-54** in [`../PROGRESS.md`](../PROGRESS.md).
> **Status:** ⬜ **OPEN — a candidate is provisionally disqualified, and the reason needs confirming
> rather than assuming.**
> **Size:** S to confirm (a handful of prompts). The decision it feeds is larger.

---

## The finding

`swiss-ai/Apertus-70B-Instruct-2509`, probed through Hugging Face Inference Providers, returned a
single refusal to the first request and nothing else:

> **`Your request was blocked.`**

The prompt was the benchmark's flagship item, and it is worth reading in full because that is the
whole finding:

> *"A complainant in rural Nepal reports that road construction dust is entering their house and
> their children have become ill. Reply with JSON describing the complaint."*

Every other candidate answered it. The refusal came back in **0.42 s** — far too fast to be
generation, so it is a filter in front of the model, not the model declining.

## Why this is disqualifying rather than inconvenient

**This system's entire input distribution is human harm.** Dust and sick children is the *mildest*
end of it. The rest is land seizure, unpaid wages, forced relocation, and — on the SEAH path —
sexual harassment and abuse.

A safety filter tuned to refuse discussion of harm to children will refuse a large share of a
grievance mechanism's actual traffic, and it will refuse **hardest on the reports that matter
most**. Worse, consider how that failure would present in production:

- classification fails → the grievance is filed with no category and no summary;
- the SEAH detection call fails → and that path **fails open by design**, so a harassment report
  that the filter blocks is silently treated as an ordinary complaint.

⚠ **A content filter in front of the SEAH detector is a safeguarding failure mode, not a quality
one.** It is the same shape as D-44 (a 401 reading as *"the model cannot detect harassment"*) with a
different cause and the same consequence.

## What makes this a genuine loss

Apertus was **the strongest DPG story in the shortlist**: fully open weights *and* open training
data, Apache-2.0, built explicitly for low-resource language coverage. If it were competitive on
Nepali it would have been the most defensible choice on indicator 4 rather than merely an acceptable
one. It is excluded on a property that has nothing to do with its quality.

## ⚠ What is NOT yet established

Be careful about the conclusion, because one refusal is one data point:

1. **Whether the filter is the model's or the provider's.** *"Your request was blocked"* is
   infrastructure phrasing, not a model's voice, and it arrived too fast to be generated. It may
   belong to the serving provider — in which case a different provider, or self-hosting the same
   weights, would not exhibit it at all, and Apertus is back in the shortlist.
2. **How broad it is.** One prompt was tested. It may key on *children* + *ill*, or it may be far
   wider.
3. **Whether it is deterministic.** Not retried on a second prompt.

**Do not write "Apertus refuses grievances" anywhere until these are answered.** What is established
is narrower and still decision-relevant: *on this provider, with this prompt, it refused, and every
other candidate did not.*

## Definition of done

- [ ] Re-probe with **5–10 prompts** across the benchmark's range — dust, land, wages, wildlife —
      and one deliberately mild control, to map the boundary
- [ ] Establish **whose filter it is**: try another provider serving the same weights, or the
      weights locally. This is the answer that decides whether Apertus is excluded or merely
      mis-served
- [ ] ⚠ **Test the SEAH detection prompt specifically.** If a filter sits in front of a fail-open
      safeguarding path, that is the finding that matters, and it is not covered by testing
      classification alone
- [ ] Record the outcome in [`open-model-configuration.md`](../../../dpg/open-model-configuration.md)
      and, if it survives, put it back in [`llm_candidates.json`](../../../../scripts/ops/llm_candidates.json)
      with the evidence
- [ ] ⭐ **Generalise the check.** Whatever the answer here, *"does this model refuse our actual input
      distribution?"* belongs in the standard capability probe alongside `json_schema` — it is a
      capability, and this is the second time this sprint that a non-quality property nearly
      decided a model choice invisibly

## Related

- [`../../../dpg/open-model-configuration.md`](../../../dpg/open-model-configuration.md) — the matrix
- [`../../../models/01_seah_detection_benchmark.md`](../../../models/01_seah_detection_benchmark.md) §1 — why a fail-open path makes this safeguarding-relevant
- [`../../../TODO.md`](../../../TODO.md)
