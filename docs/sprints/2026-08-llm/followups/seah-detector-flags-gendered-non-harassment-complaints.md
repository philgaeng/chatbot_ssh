# Follow-up — the SEAH detector flags gendered complaints that are not harassment

> **Raised:** 2026-08-20, by [DPG-23](../03-open-models-spec.md#dpg-23)'s closed-baseline run.
> **Logged as deviation D-52** in [`../PROGRESS.md`](../PROGRESS.md).
> **Status:** ⬜ **OPEN.** ⚠ **Do not fix this without measuring recall** — see §The trap.
> **Size:** S to change the prompt, **M to change it safely**, because the safe version needs the
> owner's held-out positive set.

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

## Why this is a safeguarding-adjacent defect and not a precision complaint

The SEAH route is **access-isolated**. A flagged grievance moves into a channel **most officers
cannot see**. So an unequal-pay complaint, a water-access complaint and a job-discrimination
complaint do not merely get a wrong label — they **leave the queue of the people who would have
fixed them**. [`01_seah_detection_benchmark.md`](../../../models/01_seah_detection_benchmark.md) §1
states the cost exactly:

> *"The grievance moves into a channel most officers cannot see. The dust or compensation problem
> then never reaches the people who would have fixed it — the complaint effectively disappears."*

⚠ And note **which** complaints these are. Every one of the five is a **women's access or
discrimination grievance** on an infrastructure project — precisely the class the GRM exists to
surface. The failure mode routes women's non-harassment complaints into a channel where they are
least likely to be acted on.

## The likely cause, which is in the prompt and is fixable

`LLM_services.py:580`:

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

- [ ] The owner's held-out positive set is available, and **baseline recall is measured before any
      prompt change** — there is currently no recall figure to regress against, which is itself the
      most important item here
- [ ] The prompt distinguishes *harassment* from *gender-related access and discrimination*, and
      says where the latter should go instead
- [ ] Re-measured **paired**: recall and false-alarm together, gold seeds only, scenario counts stated
- [ ] The **system** figure (keyword ∪ LLM ∪ classification-category) reported alongside the
      LLM-only figure
- [ ] ⚠ If recall drops at all, the change does not ship — a false alarm costs an officer reading one
      extra case; a miss is the thing the SEAH route exists to prevent

## Related

- [`../../../dpg/model-benchmarks.md`](../../../dpg/model-benchmarks.md) §3.2 — the measurement
- [`../../../models/01_seah_detection_benchmark.md`](../../../models/01_seah_detection_benchmark.md) — the method, the three signals, and the sample sizes
- [`../../../TODO.md`](../../../TODO.md) — the backlog row
