# Decision record — DPG sprint

> **The archive of answered questions.** Every question the project owner has answered, with **the owner's
> answer verbatim**, the original framing that produced it, the decision taken, and a pointer to the spec the
> decision landed in.
>
> **Why this file exists separately.** [`QUESTIONS.md`](QUESTIONS.md) is the live list — the register plus
> whatever is still open — and it stays short enough to read in one pass. This is where the detail goes, so
> *"expand the decision if more detail is needed"* remains possible instead of being a re-derivation. **The
> primary source is the owner's answer text; it is quoted, never paraphrased**, because a decision remembered
> through its summary drifts.
>
> **Order:** as decided, then by ticket. All dated **2026-08-17** unless noted.
> **Live questions:** [`QUESTIONS.md`](QUESTIONS.md) · **Status mirror:** [`PROGRESS.md`](PROGRESS.md)

## Index

| Q | Subject | Decision | Landed in |
|---|---|---|---|
| [Q-18](#q-18) | Shared LLM config module | `backend/config/llm_config.py`, pydantic-settings | [`02` DPG-17](02-llm-agnostic-spec.md#dpg-17) |
| [Q-03](#q-03) | T2 jurisdiction | **T2 parked** — moot until unparked | [`03` DPG-25](03-open-models-spec.md#dpg-25) |
| [Q-05](#q-05) | T2 operator + payer | **T2 parked** — no run-cost owner | [`03` DPG-25](03-open-models-spec.md#dpg-25) |
| [Q-04](#q-04) | Which config production runs | **The open one**, on cost | [`03` DPG-23](03-open-models-spec.md#dpg-23) |
| [Q-10](#q-10) | Open config as repo default | Yes, flipped in Sprint 2 | [`02` DPG-17](02-llm-agnostic-spec.md#dpg-17) |
| [Q-11](#q-11) | One model or per-task | One text model first, then downsize | [`02` DPG-14](02-llm-agnostic-spec.md#dpg-14) |
| [Q-12b](#q-12b) | Redact when | **At transmission** — the mapping is PII | [`04` DPG-31](04-pii-redaction-spec.md#dpg-31) |
| [Q-12c](#q-12c) | Where the ML dependency lives | Dedicated service, own initiative | [`04` DPG-32](04-pii-redaction-spec.md#dpg-32) |
| [Q-12d](#q-12d) | Names: privacy-first, and the rule layer does them | **Recall over precision for names**; deterministic name detection ships in Sprint 3 | [`04` §31.2b](04-pii-redaction-spec.md#dpg-31) |
| [Q-12e](#q-12e) | Provider terms, transfer trigger, pseudonymisation | Pin the provider in prod, route freely in CI; **transmission is the trigger**; never say "anonymised" | [`00` §4.3a](../../dpg/00_compliance_status.md), [`04` DPG-31](04-pii-redaction-spec.md#dpg-31) |
| [Q-12](#q-12) | Nepali NER licence | Email the author; fine-tune as fallback | [`04` DPG-32](04-pii-redaction-spec.md#dpg-32) |
| [Q-13](#q-13) | `gpt-5-nano` · voice live? | Deliberate cost choice · **voice not live** | [`02` DPG-14](02-llm-agnostic-spec.md#dpg-14) |
| [Q-14](#q-14) | SEAH fail open/closed | **Fail-open stays** — pre-filter verified | [`02` DPG-15](02-llm-agnostic-spec.md#dpg-15) |
| [Q-15](#q-15) | Benchmark provenance | Synthetic phase 1 | [`03` DPG-20](03-open-models-spec.md#dpg-20) |
| [Q-16](#q-16) | Benchmark size + labellers | **No labeller budget** | [`03` DPG-20](03-open-models-spec.md#dpg-20) |
| [Q-06](#q-06) | Licence scan scheduled? | Scheduled in `ops/security.py` | [`01` DPG-02](01-licensing-and-governance-spec.md#dpg-02) |
| [Q-07](#q-07) | Privacy-assessment author | Agent drafts — **no legal review** | [`01` DPG-04](01-licensing-and-governance-spec.md#dpg-04) |
| [Q-08](#q-08) | Assess against what | Nepal Individual Privacy Act 2018 | [`01` DPG-04](01-licensing-and-governance-spec.md#dpg-04) |
| [Q-09](#q-09) | Translation: specialist? | LLM first | [`03` DPG-23](03-open-models-spec.md#dpg-23) |
| [Q-17](#q-17) | Provider outage blocks merges? | Every commit, never required | [`03` DPG-24](03-open-models-spec.md#dpg-24) |

---

## Q-18 — Confirm where the one shared LLM config module lives {#q-18}


**Owns:** DPG-17 · **Spec:** [`02` §DPG-17](02-llm-agnostic-spec.md#dpg-17) ·
⏱ was: needed early — DPG-17 is the third commit of Sprint 1

Sprint 1 builds **two** client factories (the service boundary is real) but must have **one** config: one
place declaring every model name, endpoint, timeout and capability flag. Otherwise indicator 4 is a claim
in two files with two default sets, and they drift — that drift has *already happened* three times inside
`ticketing/` alone, and one of the copies is written into a persisted provenance field (P-15).

⭐ **Recommendation: `backend/config/llm_config.py`**, on the existing precedent —
`backend/config/smtp_config.py` is a frozen-dataclass env resolver already imported by
`ticketing/auth/keycloak_smtp.py:8` and reached from the live officer-invite path
(`ticketing/services/officer_admin.py:226`, `:618`). Same shape: one external provider, two surfaces, one
config. The independence rule in `ticketing/clients/llm_client.py:5` names `backend/**services**/` — the
service layer — not `backend/config/`. Packaging cost is zero: one `Dockerfile`, `COPY . /app`, and every
Python service runs the same image.

**The alternative** is a new neutral top-level package (`llm_config/`). Cleaner on paper — no surface owns
it by name — but it adds a top-level package to a folder structure CLAUDE.md locks, with no precedent to
follow. Worth choosing only if extracting `ticketing/` to its own repository is a live plan.

Either way DPG-17 constrains the module to import nothing from `backend.*`, `ticketing.*` or `ops.*`
(stdlib + `pydantic-settings` only, pinned by T-17-b), so it stays copy-portable and the choice is
reversible with a `git mv`.

**Answer (2026-08-17, owner):** both recommendations taken.

1. **Location: `backend/config/llm_config.py`** — the `smtp_config.py` precedent. No new top-level package.
   Extracting `ticketing/` is not a live plan; if it becomes one, the no-imports constraint (T-17-b) makes
   the move a `git mv` plus one import line per surface.
2. **Pattern: `pydantic-settings`**, and **`pydantic-settings>=2.0` moves from `requirements.grm.txt` to
   `requirements.txt`** as part of DPG-17. It stops being a GRM-only dependency the moment shared config
   uses it. The `os.getenv` fallback and its constraint-waiver are **not** taken — DPG-11's settings-pattern
   constraint stands unwaived.

Both are recorded in [`02` §DPG-17](02-llm-agnostic-spec.md#dpg-17); nothing about them is open.

---

---

---

## Q-03 — T2 hosting jurisdiction: AWS Mumbai, Singapore, or an Indian provider? {#q-03}

**→ T2 is parked**

> **DECIDED 2026-08-17 — T2 is parked.** Jurisdiction is moot until it is unparked, and it is not the owner's call alone: it depends on ADB financing instance management (see Q-05). **Consequence: T1 — a hosted open-weights provider — is the operative tier, not a stepping stone.** That makes Sprint 3's redaction load-bearing rather than defensive: third-party egress is now the steady state. Propagated to [`03` DPG-25](03-open-models-spec.md#dpg-25), [`00` §2 ladder](00-dpg-context-and-decisions.md#2-deployment-ladder--the-code-is-identical-at-every-tier), and the indicator-4 answer.

**Owns:** DPG-25 · **Gated on:** DPG-04 (privacy assessment) · **Spec:** [`00`](00-dpg-context-and-decisions.md#2-deployment-ladder--the-code-is-identical-at-every-tier)

AWS Mumbai (`ap-south-1`) is the obvious latency choice, but it is still a cross-border transfer from
Nepal, and Nepal–India data flows carry a political sensitivity that Singapore (`ap-southeast-1`) would
not. Singapore's latency to Kathmandu is worse but tolerable for this workload — these are async Celery
calls, not interactive chat turns.

⭐ **Recommendation:** do not decide before DPG-04. Evaluate both, and let the legal read pick. If the read
is ambiguous, Singapore costs you latency you can afford and removes a political question you cannot
easily manage.

**Answer:** not my call, it is linked to Q05 below, best case scenario is ADB finance the management of intances by subcontractor which are then leased to Member Countries as part of TA with ministry of finance or else - we are better park T2

---

---

---

## Q-05 — Who operates the T2 instance, and who pays for it after the pilot? {#q-05}

**→ T2 is parked**

> **DECIDED 2026-08-17 — T2 is parked**, same decision as Q-03. The best case remains ADB financing subcontractor-managed instances leased to member countries under a TA with the Ministry of Finance; absent that, there is no run-cost owner and therefore no T2. **This is the Babyl failure mode being avoided by not starting, which is the right call.** DPG-25 becomes *documented and costed, not deployed*.

**Owns:** DPG-25 · **Spec:** [`00`](00-dpg-context-and-decisions.md#two-decisions-to-resolve-before-committing-to-t2)

Roughly $700–900/month on demand, less with a commitment. A managed GPU instance is a much smaller ops
burden than a datacenter, but it is not zero: patching, monitoring, restarts, cost control.

This is the failure mode that killed Rwanda's Babyl — excellent system, no owner of the running costs.

⭐ **Recommendation:** ADB or a vendor runs it initially with a documented handover path, and **a named
budget line for run costs becomes a gate condition** before the pilot converts to production — not an
aspiration recorded in a slide.

**Answer:** linked to Q3 - I cannot respond on that - we are better park T2 

---

---

---

## Q-04 — After the benchmarks: does production run the open configuration, or the closed one? {#q-04}

**→ production runs the open configuration**

> **DECIDED 2026-08-17 — production runs the open configuration**, driven by cost, with a closed-model benchmark held in reserve if government users report quality problems. **This is a stronger DPG position than the Standard requires** — indicator 4 asks you to demonstrate replaceability; you will be *running* the open path. Say so plainly in the submission. It also settles Q-10 in the same direction. Propagated to [`03` DPG-23](03-open-models-spec.md#dpg-23), [`00` §4 evidence pack](00-dpg-context-and-decisions.md#4-dpg-evidence-pack).

**Owns:** DPG-23

**These are separate questions and the DPG claim does not depend on the answer.** Indicator 4 is satisfied
by *demonstrated replaceability* — a configurable endpoint, an open default, and CI proving both pass.
Which configuration Nepal actually runs is a cost/quality decision that stays open after this sprint.

⭐ **Recommendation:** decide with DPG-23's numbers in hand, not before. If the open configuration is
within a few points on classification, the jurisdictional data-control argument for T2 likely outweighs
the gap — and T2 is only reachable on open weights.

**Answer:** I will switch to open configuration for cost control. if government users complain about the quality, we will benchmark with closed, if not we can keep using the open configuration

---

---

---

## Q-10 — Confirm: the open configuration becomes the repository default? {#q-10}

**→ open by default, flipped in Sprint 2**

> **DECIDED 2026-08-17 — follow the recommendation:** the open configuration becomes the repository default, flipped in Sprint 2 once DPG-23 names models the open endpoint can serve. Consistent with Q-04. Already reflected in [`02` DPG-17](02-llm-agnostic-spec.md#dpg-17) §Correction.

**Owns:** DPG-17 (was DPG-11) · **Spec:** [`02` §DPG-17](02-llm-agnostic-spec.md#dpg-17)

A reviewer who clones the repo and runs it should land on the open path without configuring anything.
That is materially stronger indicator-4 evidence than a proprietary default with an open option
documented elsewhere.

**The consequence:** a fresh clone with no `LLM_BASE_URL` talks to the HF router, not OpenAI. Anyone
relying on today's defaults sees a behaviour change. `env.local` pins the real deployment either way, so
the practical impact is on new developer setups and CI.

⚠ **Amended during planning — the *timing* changed, not the answer.** Flipping the base URL in Sprint 1
while the model names are still `gpt-3.5-turbo`, `gpt-4o` and `whisper-1` ships a default configuration
that answers **no** request: an open endpoint asked for model IDs only OpenAI serves. A reviewer who
clones and runs gets a 404, which is *worse* evidence than an honest proprietary default. It also turns
DPG-10's tests red in the one commit where red is supposed to mean *stop*.

⭐ **Recommendation: yes, and flip it in Sprint 2** — after DPG-23 names the open models, as one commit
against DPG-17's single registry file (one line per task). It remains the cheapest piece of indicator-4
evidence available; it is only cheap once there is a model name that the open endpoint can actually serve.

**Answer:** follow reco

---

---

---

## Q-20 — Where does the classification review step sit in the flow? {#q-20}

**→ after submission. The wait is already in the right place; the budget is the only thing to change.**

> **ANSWERED 2026-08-18.** *"After the grievance_form completes, the user needs to complete the
> form_contact and the form_otp, and it is after completing all of them that he finally submits …
> and after this initial submission, the user is requested to review the results of the
> classification only when they are available. I have allocated enough time during the submission
> flow for the classification to happen in the background while the user fills more forms, so that
> he can review the results of the classification by himself."*

**Confirmed in the state machine, not taken on description** — `state_machine.py:392`
`_start_grievance_review_after_submit`, whose own docstring reads *"Run review after submit"*, is
invoked immediately after `action_submit_grievance` (`:1802-1815`). The full verified sequence is in
[DPG-15b §15b.0](02-llm-agnostic-spec.md#dpg-15b).

**What it settles:** the concern that prompted the question — that moving the wait to submission
would leave the complainant confirming a summary that does not exist — cannot arise, because the
review already happens after submission. The classification has two forms and an SMS round-trip to
finish in, against a measured 14–20.5 s. **D-30 was framed as "the deadline is too short"; it is
better described as "a backstop that is rarely reached"**, and its followup has been corrected.

**Two things the tracing added that the question did not ask for:**

1. ⚠ **The no-contact path is short.** `complainant_consent is False` makes `form_otp` return **no
   required slots at all** — the SMS round-trip disappears and `form_contact` shrinks with it. So the
   gap can collapse to seconds, and the case where the poll actually bites is the **anonymous or
   contact-refusing complainant**. The fast path through the flow is the privacy-conscious one.
2. ✅ **The late-update half already works, and further than credited.** `grievance_sync` runs every
   two minutes and back-fills summary, **categories**, location and location_code — so a late
   classification *and* the complainant's review corrections both reach the officer automatically.
   It is undocumented; DPG-15b writes it down rather than rebuilding it.

⚠ **And the coupling that matters:** raising the budget to 90 s makes **D-34 worse** until it is
fixed. A failed classification leaves the row at `pending`, which is not terminal, so the poll runs
its full length — turning a 20-second pause into a ninety-second stall. The raised budget and the
reachable `LLM_failed` ship together or not at all.

## Q-21 — Which single text model? {#q-21}

**→ two models total: Whisper for transcription, `gpt-5-nano` for everything else**

> **DECIDED 2026-08-18.** *"Given the nature of the tasks, we just need two models: one for
> transcription (so far whisper) and then nano 5 for all the other tasks. That will be aligned with
> what we discussed as well for the open weights model where we agreed to just have two."*

**Why it is a clean answer rather than a compromise:** the registry's eight task keys stay — they are
the seam that lets a task be moved later, and Q-11's *"one text model first, then downsize"* depends
on that seam existing. What collapses is the **defaults**: eight keys, two values.

It also aligns the two configurations. Sprint 2 evaluates exactly two things — an ASR model (DPG-22)
and a text model (DPG-23) — so `.env.open` and `.env.openai` differ in two model choices, not eight.
That is a materially easier thing to benchmark on no budget (Q-19), and a materially easier thing for
a reviewer to check.

> ⚠ **Re-confirmed 2026-08-20, and the re-confirmation caught a drift.** `.env.open` shipped **three**
> models for two days after this decision — a 120b for translation and SEAH findings, alongside a 20b for
> everything else — because DPG-16 wrote the template from the candidate list rather than from the
> decision. Nothing was wrong with the record; the artefact simply never got the message, and it would
> have reached DPG-23 as an unexamined premise. The template is now collapsed to eight keys, two values.
>
> **The selection rule that follows, which this record did not previously spell out:** with one model
> doing every text task, you **rank candidates by their worst per-task score, not their mean**. The
> binding tasks are SEAH recall — a miss is a safeguarding failure, not a quality complaint — and the
> complainant-facing resolved summary, the only generated text that reaches the public.

---

## Q-19 — What is the LLM budget for benchmarking and for CI? {#q-19}

**→ A few hundred USD, owner-funded, covering the pilot. Then a costed proposal to the Nepal Government.**

> **ANSWERED 2026-08-20.** *"I can pay for all the inferences during first months of demo in 2 districts —
> I will eventually expense it, so long as it is a few 100 USD. Then we will submit to Nepal Gvt the
> choices they need to make moving forward with realistic budget."*

**Sprint 2 is unblocked.** DPG-22, DPG-23 and DPG-24 were gated on this and are not any more. The
recommendation in [`QUESTIONS.md`](QUESTIONS.md#q-19) — cap CI first, price DPG-23 before building it —
still stands, but as ordinary discipline rather than as a way of working round an absence.

**⚠ Three things this answer changes, and none of them is "the money question is closed":**

1. **The envelope is shared with production, not dedicated to benchmarking.** It covers *"all the
   inferences during first months of demo in 2 districts"* — the pilot's own grievance classification
   comes out of the same few hundred dollars as the model sweep. **A benchmark that eats the pilot's
   runway has not saved money, it has moved the failure.** Price DPG-23 against what is left after an
   estimate of pilot traffic, not against the whole figure.
2. **It is time-boxed to the demo months, and DPG-24 is not.** The CI job is the only cost that recurs
   indefinitely — which is exactly why the spec already said to cap it first, and now there is a number to
   cap against. **Set the hard token cap on the Hugging Face account before the job's first run**, not
   after the first surprising invoice, and record the measured monthly spend in the job header so the
   government proposal can quote a real figure rather than an estimate.
3. **It creates a deliverable that did not exist: the proposal to the Nepal Government.** *"The choices
   they need to make moving forward with realistic budget"* is a document, and Sprint 2 is what generates
   its numbers — DPG-23's cost-per-1,000-grievances row and DPG-25's costed T2 proposal are its two
   halves. See [DPG-25](03-open-models-spec.md#dpg-25): that ticket now has a named audience and a real
   use, instead of being a costing nobody had asked for.

**The scale anchor this finally supplies.** DPG-25 previously said *"pull real volumes from the grievance
table"* — which contains no genuine grievances. **Two districts over the first months of the demo** is a
concrete volume to size against, and it is the honest basis for extrapolating to national scale in the
government proposal. State the extrapolation as an extrapolation.

---

## Q-23 — Is the 30 s classification budget a hard limit? {#q-23}

**→ No. It is a knob: measure, and raise it to 45 s or 60 s if a better model needs it.**

> **DECIDED 2026-08-20.** *"We will measure and adjust the number to 45 s or 60 s if needed."*

**Why this is the right shape of answer.** DPG-15b *lowered* the wait to 30 s deliberately — but the
reasoning was about a configuration where `gpt-5-nano` answers in 14–20.5 s, not about a bound that must
hold for every future model. Freezing it would have let a latency number veto a quality decision by
default, which is backwards: the number exists to serve the flow, not the other way round.

**⚠ What raising it actually spends, since this is easy to get wrong in both directions.** Classification
is triggered when the grievance form completes and runs while the complainant fills contact and OTP; the
poll happens **after they submit** and only ever catches the slow tail. If it times out, nothing breaks
operationally — the ticket is filed and the officer receives the classification through the two-minute
ticketing sync. What is lost is **the complainant's chance to see and correct how their own grievance was
understood**, which is the accountability half of the feature.

So the trade is *seconds of spinner for the slow tail* against *the review step for those same users*, and
the ceiling is not technical — it is how long someone watches a spinner on a rural mobile connection after
they have already submitted. **Report the fraction of complainants affected alongside any proposed number.**

⚠ `CLASSIFICATION_WAIT_SECONDS` and `TIMEOUT_CLASSIFY_INTERACTIVE` move together — the poll deadline and
the first-attempt timeout are one decision, pinned by DPG-15b's coherence tests.

---

## Q-24 — How many open models does "benchmark many" mean? {#q-24}

**→ A shortlist, not a sweep.**

> **DECIDED 2026-08-20.** *"Many means a shortlist — anyway not so many are decent candidates."*

The selection filter already does most of the narrowing before anything is spent: permissive licence,
genuine multilingual coverage including Nepali, reliable guided decoding, fits one 24 GB GPU at 4-bit. On
a low-resource language that leaves a handful, not a field.

**What this obliges the benchmark to record**, because a shortlist is only credible if its edges are
visible: **name every candidate considered and why each one made or missed the list** — especially the
ones the *licence* limb excluded. That limb is provisional (Q-04-02 asks whether restricted-use open
weights satisfy indicator 4), and if the answer loosens, re-running DPG-23 should be a candidate-list edit
rather than a re-design.

It also makes [Q-19](QUESTIONS.md#q-19) tractable rather than solved: a shortlist is affordable in a way a
sweep is not — but *affordable* is a number, and nobody has produced it yet.

✅ **Confirmed the same day, for the ticketing surface too:** *"Move to nano as well. Nano is very
strong for classification especially when we just need to fill json."* The standard/SEAH split keeps
**two keys** pointing at one model, so it survives as configuration and DPG-23 can re-open it with
measurements rather than by assumption.

⚠ **And measuring the migration found the trap — D-40, now [DPG-18 §18.3](02-llm-agnostic-spec.md#dpg-18).**
It is not a defaults edit. All three ticketing calls send `temperature` and two send `max_tokens`;
`gpt-5-nano` rejects both with a 400, and once the parameter is renamed, a cap of 400 **or 2000**
returns `finish_reason: length` with **empty content** — the reasoning eats the budget. The resolved
summary needs **4,287 completion tokens (3,904 reasoning)** against a cap of 1,200 today. Empty
content there means the complainant never receives their closure document, silently. Hence the model
profile: capability, temperature support and the cap parameter's *name* all follow the model, exactly
as structured-output support does (D-31).

## Q-22 — What happens to the four unreachable LLM paths? {#q-22}

**→ none of them is legacy: they are the voice-notes flow, parked for budget. Keep, label, do not delete.**

> **DECIDED 2026-08-18.** *"`transcribe_audio_file`, `extract_contact_info`, `extract_all_contact_info`
> and `translate_grievance_to_english_LLM` are functions part of the voice notes flow, which I have
> not updated in the newest versions as we have no budget for the transcription part."*

**Corroborated in the code**, and the corroboration is exact —
`backend/task_queue/test_tasks.py` still contains the chains:

```
transcribe_audio_file_task (grievance audio) → classify_and_summarize_grievance_task
transcribe_audio_file_task (contact audio)   → extract_contact_info_task
```

Contact extraction consumes a **transcription** of spoken contact details; it was never meant to run
on typed input, which is why the typed path validates phone numbers deterministically instead. And
`registered_tasks.py:157` records the switch-off in the code itself: *"CB-01 proto: store audio only;
transcription/classification deferred to officers."*

**So my recommendation to delete three of them was wrong**, and it was wrong in an interesting way:
reachability analysis found four paths nothing calls, and I read "unreachable" as "legacy". They are
one coherent, deliberately parked feature. Deleting them would have destroyed a designed-for
capability and left the next person to rebuild it from the voice spec.

**What replaces deletion** ([DPG-19b](02-llm-agnostic-spec.md#dpg-19b)): declare them parked, in one
place, with the reason — and make the reachability pin enforce *that* rather than enqueue-or-die.
A path that is parked and says so is documentation; a path that is unreachable and silent is the
thing that put four phantoms into a compliance document.

## Q-11 — One model for all text tasks, or a model per task? {#q-11}

**→ one text model first, then downsize per task**

> **DECIDED 2026-08-17 — start with one text model** (the recommendation), then move individual tasks to smaller models where the benchmark allows. With T2 parked (Q-03/Q-05), **the sizing driver is Hugging Face pricing, not GPU count** — a materially different optimisation, and it makes per-task downsizing more attractive, not less.
>
> ⚠ **Two things in the answer need correcting or checking before they enter a spec:**
> 1. *"I run the translation and classification in one call"* — **the code does not.** `classify_and_summarize_grievance` (`:204-231`) does three steps in one call — categorise, summarise *in the grievance's own language*, and draft a follow-up question — and emits English category names. Translation to English is a **separate `gpt-4` call** (`translate_grievance_to_english_LLM`, `:322`). The true and useful version of the point: **there is no translate-then-classify pipeline** — the model consumes Nepali directly. That is worth preserving; the merged-call claim is not.
>
>    ⚠⚠ **This correction was itself incomplete, and the owner was closer to right than it allowed — established 2026-08-18 (D-38).** The separate `gpt-4` translation call **is never enqueued**: `translate_grievance_to_english_task` exists, is registered, and nothing in the repository triggers it. So **no translation of the narrative happens at all** on the chatbot surface, and the owner's mental model — one call, no separate translation step — describes what runs. The English text officers read is produced on the **ticketing** side by `generate_case_findings`.
>
>    The reason the correction missed it: it checked *what the code contains*, not *what the code reaches*. Same error as the privacy assessment's leg L4 (six egress paths, two real) and as this sprint's own first draft of DPG-18 §18.0. **Three documents, three weeks, one habit** — which is why T-19b-b (every LLM task must have a production enqueue site, or be declared parked) is the durable fix rather than the deletions.
> 2. *"I'm maxing out openAI nano"* — plausible (the prompt injects the full category list plus `result_dict_str`) but **unverified**, and it sits in tension with Q-13's *"it works well as a classifier"*. [`02` DPG-14.1](02-llm-agnostic-spec.md#dpg-14) now checks specifically for **length/truncation** failures, not just exceptions.

**Owns:** DPG-17 (was DPG-11)

The registry supports both. The default matters for cost and for T2 sizing: **each additional model is a
second vLLM process or a second GPU.**

⭐ **Recommendation:** one text model across classify/extract/translate/detect, plus one ASR model. Guided
decoding does the work on extraction, not model size. Revisit per task only if DPG-23 shows a specific
task falling short — and keep the registry per-task so that revisit is a config change.

**Answer:** since i dont see T2 happening soon, we need to look into huggingface pricing. My instinct is that we start with the reco and then potentially use lower size models for some of the tasks. currently I run the translation and classification in one call and I'm maxing out openAI nano

---

---

---

## Q-12b — Redact at transmission, or before storage? {#q-12b}

**→ redact at transmission**

> **DECIDED 2026-08-17 — redact at transmission.** The officer keeps the full record; the redacted derivative goes to models and logs. ⚠ **The answer adds a design fact the spec did not have:** *"in practice we store both."* If the redacted derivative is persisted, then **the restore mapping is persisted too — and a mapping from `<PERSON_1>` to a real name is PII by construction.** It needs the same protection as the original record, and it must not land in `ticketing.*` (CLAUDE.md data rule 3). Propagated to [`04` DPG-31](04-pii-redaction-spec.md#dpg-31) as a named constraint; [`04` DPG-36](04-pii-redaction-spec.md#dpg-36) step 1 collapses from a decision to a doc fix.

**Owns:** DPG-31, DPG-36 · **Spec:** [`04`](04-pii-redaction-spec.md#313--replacement-semantics)

Two documents currently disagree. `docs/deployment/11_llm_pipeline_policy.md` says
`grievance_summary` "MUST be PII-scrubbed **before storage**". The redaction design says
"redact **before transmission**, never before storage."

The difference is operational, not academic: redact-before-storage means the officer handling the case
can no longer see which engineer was named — and for a GRM, complaints naming officials are a large share
of the useful ones.

⭐ **Recommendation:** **redact at transmission.** Keep the full record for officer action, the redacted
derivative for model calls and logs. Then fix `11_llm_pipeline_policy.md` (DPG-36) rather than the
design. But it is a product/legal call — if the agency's position is that PII must not be *stored* in
free text at all, that is a much larger change than this sprint and should be scoped separately.

**Answer:** we need to keep the original for the officer and edit redact at transmission - anyway transmission happens almost real time so in practice we store both

---

---

---

## Q-12c — Where does the ~1 GB ML dependency live? {#q-12c}

**→ dedicated service, and it leaves this sprint**

> **DECIDED 2026-08-17 — a dedicated service, medium term, as its own initiative** (a reusable Presidio+ML anonymiser for any country where in-country self-hosting is impossible). **That is bigger than Sprint 3 and better than Sprint 3.** ⚠ **Sequencing consequence, and it needs one confirmation:** Sprint 3 therefore ships **DPG-31 only** — the deterministic layer, no ML dependency, which the spec was already designed to allow — and **DPG-32/35 move out** to the new initiative. Propagated as a proposal marked ⚠ in [`04` DPG-32](04-pii-redaction-spec.md#dpg-32); confirm or correct the split.

**Owns:** DPG-32 · **Spec:** [`04`](04-pii-redaction-spec.md#dpg-32)

Presidio + transformers + torch adds roughly a gigabyte to an image, in a stack that today has **no ML
dependency at all** — `requirements.txt` has `openai` and nothing else in that family. The deployment is
a single EC2 host running ~11 services.

| Option | Trade |
|---|---|
| **Backend image** | Simplest. Heaviest — slower builds, bigger pulls, and the Celery workers inherit it |
| **Dedicated `pii` service** ⭐ | Clean boundary, matches how `ops/` was carved out, independently scalable. One more container to run |
| Hosted NER endpoint | Lightest — **but it re-introduces the exact third-party egress this sprint exists to close.** Almost certainly wrong |

⭐ **Recommendation:** dedicated service, following the `ops/` precedent. But this depends on host capacity
— **do you know the staging/production instance's headroom?** If it is tight, that changes the answer and
possibly the instance.

**Answer:** medium term, I see this as an independent service running on a dedicated Nepali instance - it can definitely be a project under my new AI tech lead job, create a workflow basd on presidio + ML to anonymise grievances or other queries before they are sent to LLMs in order to follow Data Privacy Laws in countries where in country self hosting is not possible

---

---

---

## Q-12 — The Nepali NER model's licence is not stated. Resolve it, or fine-tune a replacement? {#q-12}

**→ resolve with the author first, budget the fine-tune**

> **DECIDED 2026-08-17 — follow the recommendation:** email the author first; budget the openly-licensed fine-tune as the fallback and treat it as a releasable DPG contribution. See also Q-12c — the NER layer is now a separate initiative, so this question stops blocking Sprint 3.

**Owns:** DPG-32 · **Spec:** [`04`](04-pii-redaction-spec.md#dpg-32)

The XLM-RoBERTa Nepali NER fine-tune (PER F1 0.87) has no licence on its model card. Shipping it would
swap one closed dependency for another — an indicator-2 *and* indicator-4 problem in the very submission
this sprint exists to support.

Options: (a) contact the author and get it in writing; (b) fine-tune your own on an openly-licensed
corpus; (c) use a permissively-licensed multilingual NER model with weaker Nepali coverage and accept
lower recall.

⭐ **Recommendation:** try (a) first — it costs an email and a fortnight. Budget for (b) as the fallback;
it is a single-GPU job on an openly-licensed corpus, and **releasing that fine-tune openly would itself
be a genuine DPG contribution**, since permissively-licensed Nepali NLP tooling barely exists. That turns
a compliance obstacle into a submission asset.

**Answer:** follow reco

---

---

---

## Q-13 — Was `gpt-5-nano` on the classification path deliberate, and is voice transcription known to work in production today? {#q-13}

**→ deliberate cost choice; voice is not live**

> **DECIDED / ANSWERED 2026-08-17.** (1) `gpt-5-nano` on classification is a **deliberate cost decision** that the owner reports works well — documented, no longer drift. (2) **Voice transcription is not live at all**, for lack of LLM budget.
>
> ⚠ **(2) changes two tickets.** There is no field evidence either way on the `language_code` bug, so [`02` DPG-14.3](02-llm-agnostic-spec.md#dpg-14)'s in-container SDK check is now the *only* way to resolve it — and [`03` DPG-22](03-open-models-spec.md#dpg-22) has **no incumbent baseline to compare against**, so its honest framing is *"we shipped a working ASR path where there was none"*, not *"we matched the incumbent"*. The spec anticipated this; it is now the live case, not the caveat.

**Owns:** DPG-14

Two facts only you have:

1. `gpt-5-nano` (`LLM_services.py:244`) is the model on grievance classification — the product's most
   quality-sensitive AI path. A nano-class model there is a real decision with real consequences, and it
   is undocumented. Deliberate cost choice, or drift? 
2. `transcribe_audio_file` passes `language_code=` where the SDK takes `language=` (`:46`). If the SDK
   rejects it, **transcription has never worked on this path** and the failure is absorbed by the task
   layer. DPG-14.3 verifies this in-container — but **do you know from the field whether voice notes
   currently produce transcripts?** That answer takes ten seconds and saves an afternoon.

**Answer:** 1. It is my decision to manage cost and it works well as a classifier
2. Transcription is not live at the moment because we have no LLM budget, I can shoulder a few calls per day to nano, not transcription

---

---

---

## Q-14 — Should sensitive-content detection fail open or fail closed? {#q-14}

**→ fail-open stays — and the justification is verified**

> **DECIDED 2026-08-17 — fail-open stays, and the reason is sound.** The recommendation (a third `unknown` state) is **declined**, correctly, because the premise behind it was incomplete: the answer names a deterministic pre-filter as the backup, and **it exists.**
>
> ✅ **Verified in code — there are two independent detection paths, not one:**
> - **Deterministic, synchronous, no LLM:** `backend/shared_functions/keyword_detector.py:259` `detect_sensitive_content()` with confidence scoring at `:343`, reached through `helpers_repo.py:58` → `actions/services/seah/sensitive_detection.py:25` → `base_mixins.py:170`, running as **slot validation inside the conversation**.
> - **LLM, asynchronous:** `trigger_detect_sensitive_content_task` (`forms/form_grievance.py:200`) → Celery → `detect_sensitive_content_llm`, which is the leg that fails open.
>
> So an LLM outage degrades a **second** pass; it does not remove detection. **This strengthens indicator 9b**, which the compliance briefing currently credits to the LLM path alone — corrected there. Propagated to [`02` DPG-15](02-llm-agnostic-spec.md#dpg-15), which now records the mitigation instead of surfacing an open risk.

**Owns:** DPG-15 · **Spec:** [`02`](02-llm-agnostic-spec.md#dpg-15)

`detect_sensitive_content_llm` currently **fails open** (`:403-404`): if the LLM is unreachable, it
returns `detected: False`. On the SEAH path, that means a harassment report is not flagged when the model
is down.

The alternative — fail closed, routing to SEAH review on LLM failure — means an outage floods the SEAH
queue with ordinary road complaints, which has its own cost: SEAH officers are few, and their queue is
the most sensitive one in the system.

**This is a safeguarding decision, not an engineering one.** DPG-15 surfaces it and changes nothing.

⭐ **Recommendation:** a third option — fail into an explicit `unknown` state that is neither silently
cleared nor auto-routed, and is visible to a supervisor. More work, but it is the only option that does
not quietly choose between two bad outcomes.

**Answer:** We have first a hard coded filter that scores if a content is likely to be SEAH - if LLM is down that is our backup. I dont want anything else as the chatbot is meant for road construction grievances and we have a dedicated SEAH route

---

---

---

## Q-15 — Benchmark data provenance: synthetic, consented-real, or hybrid? {#q-15}

**→ synthetic first, hybrid later**

> **DECIDED 2026-08-17 — Phase 1 is synthetic**, committed, with a hybrid pass once the live project generates real data. Read with Q-16 (no labeller budget) this makes DPG-20 a small authored set, not a labelling programme. Propagated to [`03` DPG-20](03-open-models-spec.md#dpg-20).

**Owns:** DPG-20 · **Spec:** [`03`](03-open-models-spec.md#dpg-20)

The benchmark set is **committed test data**, so it cannot be production PII. Synthetic data risks
measuring a cleaner problem than production; real data needs consent and is circular to redact (Sprint 3
is what redacts).

⭐ **Recommendation: hybrid.** A synthetic set committed to the repo makes CI and the DPG evidence
reproducible; a held-out real set kept **outside the repo** keeps the reported accuracy honest. Whichever
you pick, every published number must state which set produced it.

**Answer:** Phase 1 - synthetic data - as we build data with the project we can have a new pass with hybrid

---

## 🟡 Non-blocking — needed before the ticket completes

---

---

## Q-16 — How many benchmark grievances, and is there staff time for Nepali-speaking labellers? {#q-16}

**→ no labeller budget; the set grows with the project**

> **ANSWERED 2026-08-17 — no staff time or budget for labellers**; the set is built as the project goes live. With Q-15 (synthetic first) this reshapes DPG-20 from a labelling programme into a small authored set that grows. ⚠ It also means **the 300-text/50-voice target is aspirational** — the spec now says so rather than implying a resourced plan. Propagated to [`03` DPG-20](03-open-models-spec.md#dpg-20).

**Owns:** DPG-20

"A few hundred" is the working figure. Labelling needs Nepali speakers who understand the category
taxonomy, and for the voice subset, verbatim transcription — which is slow.

⭐ **Recommendation:** 300 text + 50 voice as a target, labelled once for **both** classification and PII
spans (DPG-35 needs the same data — labelling it twice is the avoidable cost here).

**Answer:** currently none, we will build them as the project is live. 

---

---

---

## Q-06 — Should the licence scan join `ops/security.py`'s scheduled run, or stay a manual artefact? {#q-06}

**→ schedule the licence scan**

> **DECIDED 2026-08-17 — follow the recommendation:** the licence scan joins `ops/security.py`'s scheduled run beside `pip-audit`. Propagated to [`01` DPG-02](01-licensing-and-governance-spec.md#dpg-02) as acceptance, not a note.

**Owns:** DPG-02

`ops/security.py` already runs `pip-audit` on a schedule for CVEs. A licence scan is a different check on
the same tree.

⭐ **Recommendation:** schedule it. A one-off audit is stale the next time someone adds a dependency, and
indicator 2 is a claim that has to stay true. Small addition to existing machinery.

**Answer:** follow reco

---

---

---

## Q-07 — Who authors the privacy assessment? {#q-07}

**→ agent drafts, consultant advises — and no lawyer reviews it**

> **DECIDED 2026-08-17 — an agent drafts it and the DPG consultant advises on next steps.** ⚠ **This diverges from the recommendation and the divergence must be written into the document itself:** the recommendation split it so that *legal* delivered the Individual Privacy Act assessment. An assessment drafted by an AI agent and reviewed by a DPG consultant — who is not the agency's counsel — is a **technical inventory plus a legal opinion nobody qualified has given.** That is fine as a first pass and it is a real limitation. `privacy-assessment.md` must carry an honesty marker saying who wrote it and who has not reviewed it. Propagated to [`01` DPG-04](01-licensing-and-governance-spec.md#dpg-04).

**Owns:** DPG-04

It needs legal input, not only engineering. An agent can produce the data-flow diagram and the technical
inventory; the Individual Privacy Act 2018 assessment and the third-party-PII position need a lawyer or
a privacy specialist.

⭐ **Recommendation:** split it — engineering delivers the diagram and inventory (DPG-30 verifies them
against code), legal delivers the assessment on top.

**Answer:** we will prepare it with an Agent and discuss with the DPG consultant what are the next steps

---

---

---

## Q-08 — Is there an existing agency privacy or data-sharing agreement to assess against? {#q-08}

**→ Nepal's Individual Privacy Act 2018 is the benchmark**

> **DECIDED 2026-08-17 — no existing agency agreement; the Act is the benchmark.** So DPG-04 is the first assessment rather than a conformance check, which is the larger of the two shapes the question anticipated. Propagated to [`01` DPG-04](01-licensing-and-governance-spec.md#dpg-04).

**Owns:** DPG-04

If DOR or ADB already has data terms covering this system, the assessment measures against them. If not,
this is the first, and it is a bigger piece of work.

**Answer:** Nepal Data Privacy law will be the benchmark

---

---

---

## Q-09 — Translation: a specialist seq2seq service, or the same chat LLM? {#q-09}

**→ the LLM first; a specialist service only if it wins**

> **DECIDED 2026-08-17 — start on the chat LLM, benchmark the specialist, and stand up a dedicated translation service only if it is materially better** — in which case it becomes a government-wide asset, the same reasoning as Q-12c's anonymiser. Propagated to [`03` DPG-23](03-open-models-spec.md#dpg-23).

**Owns:** DPG-23

A specialist (IndicTrans2 class, MIT) will likely beat a general LLM on Nepali. But it is seq2seq — it
needs its own service, not a chat endpoint. That is a real deployment cost on top of T2, and it is a
second model to host.

⭐ **Recommendation:** benchmark both in DPG-23 and let the number decide. If the general LLM is close,
take the operational simplicity — one model on T2 rather than two.

**Answer:** We can benchmark them - at the beginning we will use the LLM. similarly to the pseudomizer, there is a real use case for having a dedicated service if this model is really more performant so the government can use for any translation case. 

---

---

---

## Q-17 — Should a third-party provider outage block merges? {#q-17}

**→ run every commit, never a required check**

> **DECIDED 2026-08-17 — follow the recommendation:** run on every commit, keep it out of required status checks, and write the reason in the job header. ⚠ **But see Q-19** — with no LLM budget, *how often* it runs is now a cost question, not only a flakiness question.

**Owns:** DPG-24

The platform-independence CI job calls a live third-party API on every commit, which makes it flaky by
construction — provider downtime will redden the build.

⭐ **Recommendation:** run it on every commit (that is the evidence), but **keep it out of required
status checks**. A provider outage should not stop the team from merging a UI fix. Write the reason in
the job header so nobody "fixes" it later by making it required.

**Answer:** follow reco

---

---

---

---

## ✅ Q-12d — Do person names wait for the ML layer, and which way does the privacy/accuracy trade go? {#q-12d}
**Owns:** DPG-31, DPG-32, DPG-35 · **Raised by the owner, 2026-08-18**

> **DECIDED — names are privacy-first, and the pseudonymiser handles them without waiting for the ML tier.**
>
> Two things were wrong in the specs and the DPG documents, both flagged by the owner:
>
> 1. **Scope.** DPG-31's recogniser list covered only numeric identifiers and email, so both consultant-facing
>    documents said person names would reach the provider unaddressed. **Names are substantially tractable at
>    the rule layer** — honorific and role-title triggers (`Er.`, Engineer, overseer, contractor, ward
>    chairperson, `श्री`), a Nepali family-name gazetteer, and self-identification patterns. That is now
>    §31.2b, with §31.2c covering full address spans while leaving the bare district the classifier needs.
> 2. **Direction of the trade.** For **names** the trade goes to **privacy**: tune for recall, accept
>    over-redaction. This confirms what DPG-32 already said and removes the ambiguity with §31.3's
>    classification-first rule — which stands, but applies to **location**, where a bare district is not
>    identifying and the classifier depends on it. *"Location is less important as we don't expect a full
>    address, and if we get one it should be easy to find using common words like village."*
>
> **The honest claim is now "most names are removed, some get through, here is the measured number"** —
> neither "names are handled" nor "names are unaddressed". Both DPG documents were corrected, and the
> residual is disclosed alongside the provider's own terms (Q-07-03), because with self-hosting
> parked that residual reaches a third party indefinitely.
>
> **Restore after translation** — the owner's second point — was already the design (DPG-33 step 2):
> redact, translate, put the names back. *"Even if not 100% correct that should do the trick."*

**Answer (2026-08-18, owner):** *"I thought that our pseudomiser will look as well for common first names and
last names and titles + prepositions use before names in order to be more efficient … for names, it is privacy
first. What we need to do is not to change the spec but change the statement that only emails and numeric will
be done and that names will reach the provider — we need to say what we will do to prevent it while
disclaiming that there may be a few names that still reach it. There we should reference to the privacy
clauses of huggingface. For translation, we can replace the pseudomyzed items after translation — even if not
100% correct that should do the trick."*

---

---

## ✅ Q-12e — What do the provider's terms actually say, and what does redaction let us claim? {#q-12e}
**Owns:** DPG-04, DPG-17, DPG-24, DPG-31 · **Reconciled from a parallel analysis, 2026-08-18**

> **Four corrections, three of which changed a claim we were about to send to the consultant.**
>
> **1. Hugging Face's commitments are stronger than this repo said — I read the wrong page.** The general
> privacy policy has no inference-specific clause, and an earlier draft concluded from that there were none.
> They live at
> [Inference Providers → Security & Compliance](https://huggingface.co/docs/inference-providers/en/security):
> *"Hugging Face does not store any user data for training purposes. We do not store the request body or
> response when routing requests through Hugging Face. Logs are kept for debugging purposes for up to 30
> days, but no user data or tokens are stored."* Plus TLS in transit and SOC 2 Type 2 on the Hub. **Citable,
> and we understated them in the pessimistic direction — which is still an error.**
>
> **2. But the sentence that matters is theirs too:** *"External providers are responsible for their own
> security measures."* The no-storage promise covers the **router**, not the company running the model. With
> default routing the processor changes per request — *"we cannot name which company processed this
> citizen's grievance" is a finding, not a footnote.* **Fix: pin `model:provider` in production; keep
> automatic routing in CI, which sends only synthetic data.** The multi-provider evidence survives where it
> is safe, and the privacy position is fixed where it is not.
>
> **3. Openness is a licensing property, not a privacy property — and the legal trigger was never
> training.** Open weights answered indicator 4 and did nothing for indicator 7. Under the Individual
> Privacy Act and GDPR-style regimes, **transmitting personal data to a third party is itself a disclosure
> and a cross-border transfer**, whether or not the recipient retains it. Non-retention is a mitigation to
> cite, not an answer. DPG-04 now says so explicitly, because assessing the wrong event is an easy and
> expensive mistake.
>
> **4. ⚠ Pseudonymisation is not anonymisation, and the difference is a credibility risk.** We keep the
> mapping, so the text remains personal data. **Nobody may tell the ministry the grievances are
> "anonymised"** — the claim will not survive scrutiny and it would taint everything else in the
> assessment. What *is* defensible, and strong: **only pseudonymised text crosses the border, and the
> re-identification key never leaves Nepal.** That second clause is a deployment promise, easily voided by
> serialising the mapping into the same Celery payload or log line as the text — so **storage separation
> and in-country residency are now Sprint 3 acceptance criteria with a test**, not implementation notes.
>
> **Also folded in:** redaction stays valuable even if T2 is unparked — the logs are the real leak, it is
> defence in depth against a stray debug flag, and a DPG that redacts by default is adoptable by country
> programmes with stricter transfer rules. And the residual T1 risks that belong in the data-flow diagram:
> downstream retention (~30 days typical, some reserving service-improvement use absent opt-out),
> jurisdiction of execution, and prompt caching.

**Source:** a parallel analysis the owner ran on the same question, reconciled here rather than left in two
places disagreeing. Consultant-facing wording is in
[`00_compliance_status.md`](../../dpg/00_compliance_status.md) §7 and
[`01_consultant_briefing.md`](../../dpg/01_consultant_briefing.md).

---
