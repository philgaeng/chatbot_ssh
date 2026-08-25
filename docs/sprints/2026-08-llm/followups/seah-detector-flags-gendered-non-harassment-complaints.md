# Follow-up — the SEAH detector flags gendered complaints that are not harassment

> **Raised:** 2026-08-20, by [DPG-23](../03-open-models-spec.md#dpg-23)'s closed-baseline run.
> **Logged as deviation D-52** in [`../PROGRESS.md`](../PROGRESS.md).
> **Status:** 🔄 **REFRAMED 2026-08-24 by the project owner, and the conclusion is now the opposite of
> this document's title.** The over-flagging is **intentional**: the detector is tuned recall-first
> because a missed harassment report is unrecoverable while a false alarm costs a trained SEAH officer
> a review and carries **no risk to the complainant**. See §What this actually is.
> ⛔ **The prompt change this document originally proposed is no longer the recommendation.** What is
> genuinely missing is the **explicit return path** for a case a SEAH officer clears —
> [`seah-officers-cannot-explicitly-return-a-cleared-case.md`](seah-officers-cannot-explicitly-return-a-cleared-case.md).
> ⚠ **Do not touch this prompt without measuring recall** — see §The trap, which was right and stands.
> **Size:** the measurement is M and needs the owner's held-out positive set.

---

## The finding

Over 105 committed benchmark items — **none of which is a harassment report** — the LLM detection
call flagged **7** as sensitive. Overall false-alarm rate **6.7%**.

That number understates it. The set contains **8 items authored specifically as the hard case**:
gendered, and emphatically not harassment. **Five of those eight were flagged.**

| Item | What it says | Flagged |
|---|---|---|
| `gen-0034` | No separate toilet for women workers at the site | ❌ |
| `gen-0035` | Unlit diversion route; a parent afraid for daughters walking home from school | ❌ |
| `gen-0101` | Women paid less than men for the same work | ❌ |
| `gen-0102` | One drinking-water tap for the whole labour camp; women queue longest | ❌ |
| `gen-0103` | Refused work by the contractor on the grounds of being a woman | ❌ |
| `gen-0073` | Crop destroyed by a tractor; the contractor then shouted at the complainant | ❌ |
| `gen-0093` | Resettlement scattered a community | ❌ |

## ⭐ What this actually is — a priced trade, corrected 2026-08-24

**This document originally read the 5-of-8 as a defect. It is not.** The owner's design intent, and
the reason the prompt says *"be extra sensitive"*, is that the two errors are **deliberately
asymmetric**:

| Error | Cost | Recoverable? |
|---|---|---|
| **Miss** — harassment not flagged | The report sits in the ordinary queue and nobody downstream knows to look for it. This is the failure the SEAH route exists to prevent | ❌ **No** |
| **False alarm** — ordinary complaint flagged | A SEAH officer reads it, clears it, and returns it to the standard queue. Costs review time and delay. **A SEAH officer reading a dust complaint discloses nothing to anyone** | ✅ **Yes** |

**So the system prefers false positives on purpose**, and the measured rate is the price of that
preference rather than evidence against it.

⚠ **What the asymmetry obligates is the return path**, and that is where the real work is. Over-flagging
is only cheap while a cleared case can actually go back. Today the capability exists — correcting a
ticket's classification re-resolves the workflow and clears the SEAH flag — but **only as a side effect
of a category edit**: there is no explicit action, no de-flag audit event, and no test pinning the
behaviour. Raised separately as
[`seah-officers-cannot-explicitly-return-a-cleared-case.md`](seah-officers-cannot-explicitly-return-a-cleared-case.md).

**The residual concern that survives the reframe, and it is small but real.** Every one of the five is
a **women's access or discrimination grievance** — exactly the class the GRM exists to surface. They
are not lost, but they are **delayed** by a round trip whose latency nobody currently measures. That
is a service-quality question about the return path, not a safeguarding failure of the detector.

## The likely cause, which is in the prompt and is fixable

`LLM_services.py:625`:

> *"be extra sensitive as awareness around the issue is low and people may be reluctant to report
> and evasive when reporting, so anything that may imply sexual or gender harassment should be
> flagged, even things like being looked at or smiled at or followed or touched. Do NOT flag land
> issues, property disputes, or physical violence—only sexual assault or gender/sexual harassment."*

The recall-first instruction is **deliberate and correct** — under-reporting is the real-world
problem this system was built around. But the exclusion list names *land, property, violence* and
says nothing about the actual confusable class: **gender-related grievances that are not
harassment**. The phrase *"gender/sexual harassment"* is also ambiguous enough to read as *"gender
discrimination"*, which is exactly what `gen-0101` and `gen-0103` are.

## ⚠ The trap — do not tighten this without measuring recall

**The committed benchmark cannot tell you whether a fix breaks detection**, because it contains no
positives (that is [§0.2](../03-open-models-spec.md) of the sprint spec, and the owner's decision of
2026-08-19). A prompt change that removes these five false alarms could equally remove real
detections, and **nothing in this repository would notice**.

This is the exact shape of a well-intentioned fix causing a safeguarding miss:

1. someone reads *"5 of 8 confusables flagged"*;
2. adds *"do not flag gender discrimination or access issues"* to the prompt;
3. the false-alarm rate drops, the committed benchmark goes green;
4. an oblique harassment report — *"he keeps asking me to come to the office alone"* — now reads as
   a workplace-access issue and is no longer flagged;
5. nobody finds out.

**Therefore: any change to this prompt is gated on a paired re-run against the owner's held-out
positive set, reporting recall AND false-alarm together.** The harness supports it:
`--seah-set /path/outside/the/repo.jsonl`.

## The third signal, which makes the real number worse

Detection is not one call. `01_seah_detection_benchmark.md` §2 lists three signals, and the
**classification** call over-routes too: `Gender - Gender Discrimination And Harrassment` appeared as
a false positive **3 times** in the same run, and the review step keeps any category containing
`"gender"`. **What a complainant experiences is the union**, so the system false-alarm rate is higher
than the 6.7% measured on the LLM detection call alone. Report both numbers, as §2 requires.

## Definition of done

⚠ **Re-ordered 2026-08-24.** The prompt change dropped from first to optional; the measurement and the
return path came up.

- [ ] The **return path is a first-class action** with its own audit event and a test —
      [tracked separately](seah-officers-cannot-explicitly-return-a-cleared-case.md). **This is the
      item that makes the current false-alarm rate acceptable**, and it does not need the held-out set
- [ ] The owner's held-out positive set is available, and **baseline recall is measured** — there is
      currently no recall figure to regress against, which is the most important measurement here
- [ ] ⏸ *Optional, and only if recall is measured first:* the prompt distinguishes *harassment* from
      *gender-related access and discrimination*. ⛔ **Not a goal in its own right** — a lower
      false-alarm rate is not an improvement if it costs recall
- [ ] Re-measured **paired**: recall and false-alarm together, gold seeds only, scenario counts stated
- [ ] The **system** figure (keyword ∪ LLM ∪ classification-category) reported alongside the
      LLM-only figure
- [ ] ⚠ If recall drops at all, the change does not ship — a false alarm costs an officer reading one
      extra case; a miss is the thing the SEAH route exists to prevent

## Related

- [`../../../dpg/model-benchmarks.md`](../../../dpg/model-benchmarks.md) §3.2 — the measurement
- [`../../../models/01_seah_detection_benchmark.md`](../../../models/01_seah_detection_benchmark.md) — the method, the three signals, and the sample sizes
- [`../../../TODO.md`](../../../TODO.md) — the backlog row
