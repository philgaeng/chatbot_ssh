# Sprint 3 — PII redaction at every egress (DPG-30…36)

> Branch `dpg/sprint3-pii` · **Depends on Sprint 1** (redaction hooks into the client factory; without a
> single chokepoint the hook has to be pasted into nine call sites and one will be missed).
> **Goal:** no personally identifiable information leaves the agency's control — in model calls, logs, or traces.
>
> **⚠ Two owner decisions on 2026-08-17 changed this sprint's weight and its scope, in opposite directions.**
>
> **It matters more — and it would still matter if T2 were unparked tomorrow.** Three reasons redaction is
> not merely a T1 stopgap: **the logs are the real leak** (Celery payloads in Redis, exception bodies,
> backups shipped offsite — none of which changes with the model endpoint); **defence in depth** against a
> misconfigured endpoint or a developer pasting a trace into a bug report; and **reusability**, since another
> country programme will have stricter transfer rules than Nepal and a DPG that redacts by default is
> adoptable where one that does not needs re-engineering.
>
> [T2 is parked](03-open-models-spec.md#dpg-25) (Q-03 + Q-05): there is no owner for GPU
> run costs, so **T1 — a hosted third-party provider — is the steady state, not a transition.** Grievance text
> leaves the country **indefinitely**, and production is moving to a hosted open-weights provider (Q-04)
> rather than off-provider. Redaction was the control that made a temporary exposure acceptable; it is now
> **the only control on a permanent one.** That is a promotion from prudent to necessary.
>
> **It ships less.** Q-12c: the NER layer becomes **its own initiative** — a reusable Presidio+ML anonymiser
> service for any country where in-country self-hosting is impossible — on a medium-term horizon, not this
> sprint. So **this sprint delivers DPG-30, DPG-31, DPG-33, DPG-34 and DPG-36**, and
> [DPG-32](#dpg-32) + [DPG-35](#dpg-35) move out. DPG-31 was designed to ship without DPG-32; that design is
> now load-bearing. ⚠ **Confirm this split** — see DPG-32.

---

## Required reading

1. [`CLAUDE.md`](../../../CLAUDE.md) — **§Data rules**, all six, and the amendment note. Rule 3 (no complainant PII columns in `ticketing.*`) and rule 5 (PII fetched fresh, never cached) are **pinned by tests**; rule 4's honest caveat about `grievance_summary` is the exact problem this sprint attacks. Also §Service boundaries and §Docker-only
2. [`docs/PROGRESS.md`](../../PROGRESS.md) → [`docs/TODO.md`](../../TODO.md)
3. [`docs/engineering/00_engineering_index.md`](../../engineering/00_engineering_index.md) — **rule 6** (no complainant PII in `ticketing.*`, ever, in any form — column, cache, **or log**)
4. └ [`02_python_services.md`](../../engineering/02_python_services.md) — **binding** for `pii_service.py`
5. └ [`04_testing.md`](../../engineering/04_testing.md) — **binding**; DPG-35 is a measured recall number, not a green tick
6. └ [`06_documentation_lifecycle.md`](../../engineering/06_documentation_lifecycle.md) — honesty markers; **DPG-36 exists because a live spec carries an unbuilt claim**
7. [`docs/deployment/11_llm_pipeline_policy.md`](../../deployment/11_llm_pipeline_policy.md) — **the live spec this sprint makes true.** Its §PII boundary model says `public.grievances.grievance_summary` "MUST be PII-scrubbed before storage". ⚠ **Nothing scrubs it today**
8. [`docs/seah/`](../../seah/) — the canonical parties model and PII vault. SEAH text is the highest-sensitivity content in the system
9. [`docs/deployment/13_security.md`](../../deployment/13_security.md) — DPG-34's log/backup posture lands here
10. [`docs/sprints/archive/2026-08_tier3_structural/03-pii-boundary-spec.md`](../archive/2026-08_tier3_structural/03-pii-boundary-spec.md) — **read this before claiming anything about the PII boundary.** T3-04 already fixed the structured-PII path and left two pinning tests behind
11. [`docs/sprints/README.md`](../README.md) — the standing deferral rule
12. [`00-dpg-context-and-decisions.md`](00-dpg-context-and-decisions.md) §4 — indicators 7, 9, 9a

---

## §0 — What is already solved, and what this sprint is actually about

**Do not re-solve T3-04.** Structured complainant PII is handled: the backend decrypts server-side,
`GET /api/grievance/{id}` returns plaintext over an authenticated + audited endpoint, ticketing holds no
key and has no accessor, and `tests/ticketing/test_pii_boundary.py` + `test_boundary_policy.py` pin it.
Those tests **stay green through this entire sprint**; if one goes red you have broken a locked rule.

This sprint is a **different problem**: free text leaving the agency's control.

> Collecting name and contact in structured fields, separately from the narrative, is good design and it
> eliminates the easy version of the problem. **Two leaks it structurally cannot close:**
>
> **Third-party PII — the sharper exposure.** A road-sector grievance names the site engineer, the
> contractor, the ward official. Those people never consented to anything. Your complainant consented to
> give *their* details; nobody asked the engineer whose conduct is described. Different legal category,
> and asking the complainant separately does nothing about it. For a GRM, complaints naming officials
> are not an edge case — **they are a large share of the useful ones.**
>
> **People self-identify in the free-text box anyway.** *"My name is Ram Bahadur, I am from ward 4, and I
> want to complain about…"* is the most common grievance opening in every system. **The voice channel
> guarantees it** — nobody speaking naturally observes your field boundaries.

---

## Order (BINDING)

```
1. DPG-30  MEASURE      — enumerate every egress of grievance text, in code, against
                          DPG-04's data-flow diagram. Same discipline as DPG-10:
                          you cannot redact a boundary you have not found.

2. DPG-31  DETERMINISTIC — Devanagari digits + Nepali patterns. No ML, no new heavy deps,
                           high value. Ships and is useful on its own — which is now the
                           whole of this sprint's redaction engine, not its first half.

3. DPG-33 ∥ DPG-34      — the two boundaries. Model calls, and logs/Celery/Redis.
                          34 is the one that actually leaks (see below). Do not defer it.

4. DPG-36  RECONCILE    — make 11_llm_pipeline_policy.md's claim true, or mark it.
                          Q-12b settled the decision it was waiting on.

── moved out of this sprint (Q-12c) ──────────────────────────────────────────
   DPG-32  NER          — becomes the standalone anonymiser service initiative.
   DPG-35  MEASURE      — recall on a labelled set: it measures the NER layer,
                          so it travels with DPG-32. ⚠ But see DPG-35: the
                          *deterministic* recall this sprint ships still needs
                          a number, and that part stays.
```

---

## DPG-30 — Measure the egress surface first {#dpg-30}

**No production code.** Output is `docs/dpg/pii-egress-inventory.md`: every path by which grievance free
text leaves the agency's control, found **in the code**, not assumed from the diagram.

### The known starting set (verify and extend — this list is not the answer)

| Egress | Carries | Status today |
|---|---|---|
| 9 LLM call sites behind **2 chokepoints** — `call_llm()` in `backend/services/llm_client.py:80` and `ticketing/clients/llm_client.py:69` (DPG-18). **5 run; 4 are parked** — the voice-notes flow, declared in `PARKED_TASKS` (`backend/task_queue/registered_tasks.py:96`) | Raw narrative, contact strings, officer notes, field reports, audio | **Unredacted.** ⚠ The count is 9 but the *surface* is 2 — see [DPG-33](#dpg-33). Inventory all 9, and mark the 4 parked ones: they carry no production egress until transcription is funded |
| Celery task payloads → **Redis** | `input_data["values"]["grievance_description"]` (`grievance_intake/classification.py`) | **Unredacted.** Check Redis persistence (RDB/AOF) and whether the volume is backed up |
| Application logs (`backend/logger/`) | Varies per call site — audit each | Partially mitigated: `db_debug_log.text_len_for_log` logs **lengths**, not text. Follow that precedent |
| Exception reports carrying request bodies | Full payloads | Audit |
| Database backups (`backups_data` volume) | Everything | **Name the destination and its jurisdiction** |
| XLSX quarterly reports, PDF closure documents | Summaries, resolutions | Audit recipients and transport |
| Messaging API → DOIT gateway (SMS, in Nepal) / SMTP relay | Complainant-facing text | Third-party by design; assess |
| `POST /message` → orchestrator | Officer replies | Internal |
| Observability | — | **None installed** (no Langfuse, no OTel, no Sentry — verified). The source narrative's §3.4 assumes Langfuse; it does not exist here. Write the rule for whatever is added later |

### Steps

1. Grep-and-read every path. For each: what text, to whom, over what transport, retained where, for how long.
2. **Reconcile against DPG-04's data-flow diagram** and report every leg the diagram missed. A diagram
   nobody checked against code is a compliance artefact, not a control.
3. Rank by **actual likelihood of exposure**, not by how much the path worries people:

   > The model call is the leak everyone designs against. **Logs and traces are the leak that actually
   > occurs.** Logs, exception reports carrying request bodies, Celery payloads sitting in Redis,
   > database backups shipped offsite, analytics exports — these get copied, attached to bug reports,
   > pasted into chat, and stored on third-party infrastructure far more casually than any API call.

4. Write the inventory. It is the scope statement for DPG-33/34 and an indicator-7 artefact in its own right.

### Acceptance

- [x] `docs/dpg/pii-egress-inventory.md` written, every egress found in code with a file:line reference
      — **12 egress paths (E1–E12)**, each citation opened and read, none inherited from another document
- [x] Reconciled against DPG-04's diagram; discrepancies listed in both documents — **four (R1–R4)**, in
      §4 of the inventory and in `privacy-assessment.md` §2.2. ⭐ The pattern in all four is the same:
      **the diagram is right about topology and optimistic about content**
- [ ] 🔴 **Redis persistence configuration and backup destination verified in-container, not assumed** —
      **could not be done: Docker is unavailable in this WSL distro.** And this is the acceptance item
      that mattered most, because §2 found that *"no persistence volume"* is an **inference repeated as
      fact in four documents** and never tested. Three commands settle it; none could be run.
      [`followups/redis-persistence-is-inferred-not-verified.md`](followups/redis-persistence-is-inferred-not-verified.md).
      The backup half **is** established from source: `backup_db.sh` supports GPG and an off-box
      `BACKUP_REMOTE`, both **operator-set and optional**, so the destination is unnamed by design
- [x] Ranked by likelihood of real exposure — logs first, model call fourth. ⚠ Deliberately not ranked
      by alarm: the model call is the leak everyone designs against, the logs are the leak that happens
- [x] Anything out of scope for DPG-33/34 logged as a followup + `TODO.md` row — two followups, two rows

---

## DPG-31 — The deterministic layer {#dpg-31}

`backend/services/pii_service.py`. **No ML.** Ships independently, and it contains the single
highest-value line in this sprint.

### 31.1 — Devanagari digits (do this first)

**Devanagari digits will defeat your phone regex.** Nepali users type `९८४१२३४५६७`. An ASCII `\d` pattern
misses it completely — and that is a phone number sitting in plain text heading to a third party.

```python
DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
normalised = text.translate(DEVANAGARI_DIGITS)
```

Normalise before pattern matching, **or** match both character classes. This is exactly the kind of thing
that passes every test written by an English speaker.

⚠ **Normalising for matching must not normalise what you send.** The redacted text keeps its original
digits everywhere a span was not replaced — offsets are computed on the normalised string, applied to the
original. Since `str.translate` on this mapping is length-preserving 1:1, offsets align; **assert that in
a test** rather than relying on it, because it stops being true the moment someone adds a multi-character
mapping.

### 31.2 — Nepali recognisers

Custom Presidio recognisers (or plain regex at this stage) for:

- `+977` international prefix
- Ten-digit mobiles on `97x` / `98x` prefixes
- Landline area codes
- Citizenship certificate numbers
- **Vehicle registration numbers** — named in [`00_compliance_status.md`](../../dpg/00_compliance_status.md) §7
  and missing from this list until 2026-08-17. Not an afterthought in a **road-sector** GRM: *"the contractor's
  tipper ba 2 kha 1234 dumps spoil at night"* identifies a vehicle, its owner, and often its driver. Nepali
  plates carry a zone/province token in Devanagari plus digits, so this recogniser needs the digit
  normalisation of §31.1 more than any other pattern here
- Email (the generic recogniser is fine)

Both digit systems, for every numeric pattern.

### 31.2b — Person names, deterministically (added 2026-08-18)

**Names are not the NER layer's exclusive job, and treating them as such was a scoping error.** A
rule layer gets a real fraction of them without any ML dependency, and in this domain the fraction it
gets is the one that matters most — the named official. Three recognisers, in descending precision:

1. **Honorific and role-title triggers.** The token(s) following a title are almost always a name, and
   this is the *third-party official* case that carries the sharpest legal exposure (§0):
   `श्री` · `श्रीमती` · `सुश्री` · `डा.` · Mr · Mrs · Ms · Dr · **Er.** / Engineer · Sir · Madam, and the
   domain's own role titles — engineer, sub-engineer, junior engineer / JE, overseer, contractor,
   supervisor, ward chairperson, chairperson, secretary. **`Er.` earns its place**: it is the standard
   Nepali honorific for an engineer and this is a road-works GRM.
2. **Family-name (thar) gazetteer.** Nepali surnames are a comparatively closed and distinctive set —
   Shrestha, Tamang, Gurung, Magar, Rai, Limbu, Thapa, Bhattarai, Adhikari, Poudel, Karki, Basnet,
   Chaudhary, Yadav, Sah, Mandal, Bhandari, Dahal, Khadka, Pandey, Sharma, Acharya, Ghimire, Subedi,
   Neupane … A surname hit is high precision *and* lets you take the adjacent token as the given name.
   ⚠ **Surnames carry caste and ethnicity in Nepal.** That is precisely why they must not reach a third
   party — and also why the gazetteer itself is sensitive: it is a list of ethnic markers. Keep it as
   project data with a comment saying so; do not publish it as a "sample dataset".
3. **Self-identification patterns.** *"my name is X"*, *"I am X"*, `मेरो नाम X हो`, `म X हुँ`. High
   precision, and it catches the opening line the voice channel guarantees (§0).

**Given-name matching is deliberately last and weakest.** Many Nepali given names double as common
nouns — *Bahadur* (brave), *Maya* (affection), *Laxmi*, *Kumar* — so a given-name gazetteer alone
over-fires. Use it only to extend a match anchored by (1) or (2), never on its own.

### 31.2c — Addresses, not districts

A bare district name is not identifying and the classifier needs it (§31.3). **A full address is a
different object** and is worth catching: detect settlement-level qualifiers — `गाउँ` / gaun (village),
`टोल` / tole (neighbourhood), ward + number, VDC, `नगरपालिका` / municipality, house/plot numbers — and
redact the address span while leaving the district and province intact. If a complainant writes out a
full address it is usually formulaic, which is what makes this tractable at the rule layer.

### 31.3 — Replacement semantics

Three choices matter, and each has a reason:

- **Placeholders, not deletion.** `<PERSON_1>`, not removal. The sentence keeps its grammatical shape so
  the classifier still parses it. Deleting words degrades classification noticeably; substituting a token
  barely does.
- **Consistent mapping within a document.** Same name → same token: *"`<PERSON_1>` promised to fix it,
  then `<PERSON_1>` refused to return."* Fresh tokens per occurrence destroy exactly the narrative
  structure the classifier uses.
- **Reversible where the officer needs the original.** Keep two representations: the full record for
  officer action, the redacted derivative for model calls and logs.
  **Redact before transmission, never before storage.**

  ✅ **DECIDED (Q-12b, 2026-08-17): redact at transmission.** The officer keeps the original;
  `11_llm_pipeline_policy.md` gets reconciled (DPG-36), not the design. The conflict is resolved in favour
  of the officer's ability to act on a case — a GRM officer needs to know which engineer was named.

  > ⚠ **REVISITED 2026-08-27 — a third option, and it does not lose to this reason.** The owner proposes
  > encrypting the original narrative, working from the redacted derivative everywhere, and revealing the
  > original through the audited path that already exists for contact details. **The option Q-12b rejected
  > was "the original is gone"; this one keeps it.** The officer still learns which engineer was named —
  > they ask, and the asking is logged. Design:
  > [`followups/encrypt-the-original-work-from-the-redacted.md`](followups/encrypt-the-original-work-from-the-redacted.md).
  >
  > **That is a sprint after this one — it needs a redacted derivative to exist first.** Two parts of it
  > constrain Sprint 3 and are written in below, because building the opposite and reversing it costs
  > more than deciding now: **§31.4** (redact the output) and **[DPG-33](#dpg-33) step 2** (which of the
  > summary's three consumers gets names).

  > ### ⚠ This is **pseudonymisation, not anonymisation** — and the distinction is load-bearing
  >
  > **Because we keep the mapping, the text remains personal data** under GDPR-style analysis and under
  > Nepal's Individual Privacy Act. Redaction reduces the risk profile; it does not take the data out of
  > scope. **Nobody should tell the ministry the grievances sent for inference are "anonymised"** — that
  > claim will not survive scrutiny, and an overstatement there discredits every other claim in the
  > assessment.
  >
  > **What can be said, accurately and strongly:** *only pseudonymised text crosses the border, and the
  > re-identification key never leaves Nepal.* Pseudonymisation is an explicitly recognised safeguard.
  >
  > ⚠ **That second clause is a promise about deployment, not about code, and it is easy to void by
  > accident.** Serialise the mapping into the same Celery payload, the same log line, the same cached
  > context blob as the redacted text and the whole argument collapses silently — the key travelled with
  > the ciphertext. **Storage separation and in-country residency are therefore acceptance criteria, not
  > implementation notes.**
  >
  > ### And the mapping is itself PII
  >
  > The owner's answer notes that *"in practice we store both"* — transmission is near-real-time, so the
  > redacted derivative is persisted alongside the original (`TicketContextCache` and friends). That is
  > fine for the *derivative*, which is by definition less sensitive. **It is not fine for the mapping.**
  >
  > `restore()` needs `<PERSON_1> → "Ram Bahadur"`. **A stored mapping is a plaintext PII store** — a
  > compact, high-value one, since it is nothing but identifiers. Three constraints follow, and they are
  > acceptance criteria, not advice:
  > 1. **The mapping never lands in `ticketing.*`.** CLAUDE.md data rule 3 is pinned by
  >    `tests/ticketing/test_boundary_policy.py`; a `<PERSON_n>` table in the ticketing schema would break
  >    it, and rightly.
  > 2. **Prefer not persisting it at all.** If `restore()` only ever runs inside the same request or task
  >    that produced the redaction — which is true of translation output and the classification summary —
  >    the mapping can live in memory for the duration and never be written. **Establish whether any caller
  >    genuinely needs cross-request restore before building a store for it.**
  > 3. **If it must be persisted**, it inherits the original's protection: same encryption boundary, same
  >    access control, same audit trail, same retention clock as the record it dereferences — and it is a
  >    new leg on DPG-04's data-flow diagram.

- **Do not redact LOCATION** if the classifier derives district from the narrative — you will break your
  own pipeline. Either leave `LOC` intact (a district name alone is not identifying) or take district
  from the structured field and redact freely. ⚠ **Check which applies here**: the classification
  system message (`LLM_services.py:322`) injects district and province from structured slots, so
  district may already come from the structured side — verify before choosing. The same injection
  happens on the contact-extraction prompt (`:141`) and the translation prompt (`:563`).

### 31.4 — Redact the output, not only the input (added 2026-08-27)

**The ordering is the control; a prompt instruction is not.** If the summary is generated from
pseudonymised text the model never receives the name, so it cannot emit one. That is structural. Asking a
model in its prompt not to name anybody only acts in the case where redaction *missed* a name — which is
exactly where an instruction is least dependable, because a missed name reads to the model as ordinary
narrative. Keep the instruction as defence in depth; **do not record it as a control.** This spec already
says so about the ticketing prompt ([DPG-33](#dpg-33) step 3) and the same standard applies here.

**The enforceable version, and it is cheap:** run `redact_for_model()` over the model's *output* before it
is persisted. Same function, one more call site, two sentences of input. If a PERSON token survives into a
generated summary, that summary is redacted again or regenerated. It converts *"we asked the model not
to"* into *"a summary carrying a detected name cannot be stored"* — deterministic, and pinnable by a test
the way the boundary rules are.

⚠ **There are two summary-producing prompts, not one, and the second is easy to miss:**

| Where | Produces | Why it gets missed |
|---|---|---|
| `LLM_services.py:333-348` | `grievance_summary`, from the classification call | The obvious one |
| `LLM_services.py:567-574` | `grievance_summary_en`, from the **translation** call | Its prompt says *"if it is not aligned with the details, **create a new summary** from the translated details"* — it reads as a translation step, so a task to "gate the summary prompt" finds the first and misses this. And its output is the English summary, the one most likely to reach a quarterly report or ADB |

An output-redaction pass covers both without anyone having to remember there are two. A prompt gate has to
be applied twice, correctly, and stay applied.

⚠ **Names removed is not identity removed.** A summary keeps ward-level location and circumstance, which
[the privacy assessment §1.2](../../dpg/privacy-assessment.md) notes is often identifying on its own. The
defensible claim is *the summary carries no names*, **not** *the summary is anonymous*.

### API

```python
redact_for_model(text: str) -> tuple[str, Mapping]   # (redacted, reversible mapping)
restore(text: str, mapping: Mapping) -> str
```

Per-document mapping scope. Never a process-global counter (two concurrent grievances must not share
`<PERSON_1>`).

### Acceptance

- [ ] `backend/services/pii_service.py` exists, follows [`02_python_services.md`](../../engineering/02_python_services.md)
- [ ] Devanagari normalisation, with an offset-alignment assertion
- [ ] Nepali mobile / landline / `+977` / citizenship-number / **vehicle-registration** / email recognisers,
      both digit systems
- [ ] **Person-name recognisers (§31.2b)** — honorific/role-title triggers, family-name gazetteer,
      self-identification patterns. Tuned for **recall**, per DPG-32: a missed name is a privacy breach,
      an over-redacted common noun is a small classification cost. The gazetteer is marked as sensitive
      project data, not a publishable sample
- [ ] **Address spans (§31.2c)** redacted via settlement qualifiers, while district and province survive
      for the classifier
- [ ] Consistent, reversible, per-document placeholder mapping
- [ ] **Whether any caller needs cross-request `restore()` is established, and recorded.** If none does, the
      mapping is never persisted and the acceptance says so explicitly
- [ ] **If the mapping is persisted:** not in `ticketing.*` (data rule 3, pinned by test); same encryption,
      access control, audit and retention as the record it dereferences; added to DPG-04's data-flow diagram
- [ ] **The mapping never leaves the country, and never travels with the text it dereferences** — not in a
      Celery payload, a log line, an exception body, a cached context blob or a backup that ships offsite.
      **Pinned by a test**, because this is the clause the "only pseudonymised text crosses the border"
      claim rests on, and it is voided by a single careless `json.dumps`
- [ ] **No document produced by this sprint describes the output as "anonymised".** Pseudonymised, with the
      reason. Pinned by the same grep that checks the egress inventory
- [ ] **`redact_for_model()` runs over model *output* before persistence (§31.4)**, not only over input.
      A prompt instruction may be added beside it, and is **not** counted as a control
- [ ] `redact_for_model` / `restore` round-trip is lossless for non-PII text
- [ ] LOCATION policy decided, with the reason recorded
- [ ] **No new heavy dependency in this ticket** — it must ship without DPG-32

### Tests

[`TESTS.md`](TESTS.md) → **T-31-a … T-31-e**. T-31-a (a Devanagari-digit phone number is detected) is the
single most important test in this sprint.

---

## DPG-32 — The NER layer — ⏸ **moved out of this sprint** {#dpg-32}

> **⚠ SCOPE DECISION 2026-08-17 (Q-12c) — needs one confirmation.**
>
> The owner's answer: *"medium term, I see this as an independent service running on a dedicated Nepali
> instance… a workflow based on Presidio + ML to anonymise grievances or other queries before they are sent
> to LLMs, in order to follow data-privacy laws in countries where in-country self-hosting is not
> possible."* **That is a better idea than this ticket, and a bigger one** — a reusable anonymiser is worth
> more than a Nepal-GRM-internal NER layer, and it is exactly the *"is there ADB appetite to fund it"*
> conversation the compliance briefing opens (Q-07-02).
>
> **The sequencing consequence I have written in, and want confirmed:** Sprint 3 ships **DPG-31 only** as its
> redaction engine — deterministic, no ML, no ~1 GB dependency — and this ticket plus [DPG-35](#dpg-35) leave
> the sprint. DPG-31's *"must ship without DPG-32"* constraint was written for exactly this and now carries
> real weight.
>
> **What that costs — restated 2026-08-18, because the first version overstated it.** This banner used to say
> person names go unredacted entirely. That was a scoping error: **§31.2b covers names at the rule layer** —
> honorific and role-title triggers, a family-name gazetteer, self-identification patterns — which catches the
> named official and the self-introducing complainant, the two cases that dominate a road-works GRM.
>
> **Deferring the ML tier costs recall, not coverage.** A name with no title, no recognisable surname and no
> self-identification frame — *"the man operating the roller swore at my daughter"*, or an unusual surname
> absent from the gazetteer — still passes through. **So the honest claim is "most names are removed, some
> get through", not "names are handled" and not "names are unaddressed".** That residual must be measured
> (DPG-35) and disclosed in `docs/dpg/pii-egress-inventory.md`, DPG-04's assessment and the consultant
> briefing — with the provider's own terms named beside it, because a permanent third-party arrangement is
> what makes the residual matter.
>
> ⭐ **Cheap way to shrink it further, still no ML:** a deny-list of the project's *own* personnel. Officers,
> contractors and ward officials are enumerable from `ticketing.*` and the project documents — poor general
> recall, near-perfect on exactly the people this GRM names most.

**Person-name detection is the hard part**, and it is where a redaction layer fails quietly.

spaCy ships no trained Nepali NER pipeline, so Presidio's defaults find **nothing** in Devanagari. Deny
lists of names are weak here — the Nepali name space is large and many given names double as common
nouns, giving poor recall *and* poor precision.

The working route is Presidio's **transformers NLP engine**, configured per language with
`model_to_presidio_entity_mapping` (`PER → PERSON`, `LOC → LOCATION`, `ORG → ORGANIZATION`). A Nepali
XLM-RoBERTa NER fine-tune exists, reporting **PER F1 0.87**, overall F1 0.79.

### ⚠ Three caveats, all material

1. **Its licence is not stated** on the model card — an indicator-2 *and* indicator-4 problem for a DPG
   submission. You would be swapping one closed dependency for another, **inside the very submission meant
   to remove it.** Resolve it with the author, or fine-tune your own on an openly-licensed corpus.
   **Q-12, blocking this ticket.**
   > **The fallback is also an opportunity, and it is being raised with ADB as one.** A Nepali NER
   > fine-tune released openly would be a genuine DPG *contribution* — permissively-licensed Nepali NLP
   > tooling barely exists. The compliance briefing asks whether the DPGA would credit that and whether
   > there is ADB appetite to fund it
   > ([`00_compliance_status.md`](../../dpg/00_compliance_status.md) Q-07-02). Same shape as DPG-22's
   > SLR54 ASR fine-tune. **Both are out of scope here** — but if funding lands, this ticket's licence
   > blocker becomes the deliverable, so keep the corpus and threshold work reusable rather than one-off.
2. **It is trained on WikiANN** — Wikipedia prose, not colloquial spoken grievances transcribed from
   voice. Expect meaningfully worse than 0.87 on real traffic. **Measure on your own data (DPG-35).**
3. **Dependency weight.** Presidio + transformers + torch adds roughly a gigabyte to the image, in a
   stack that today has **no ML dependency at all** — `requirements.txt` has `openai` and nothing else in
   that family. This changes build times, image size, and the deployment footprint on a single EC2 host
   running ~11 services. **Q-12c: which image carries it?** Options: the backend image (simplest, heaviest);
   a dedicated `pii` service the others call over HTTP (cleanest boundary, one more container); or a
   hosted NER endpoint (lightest, **but it re-introduces the exact third-party egress this sprint exists
   to close — almost certainly wrong**).

### Tune for recall, not precision

**A missed name is a privacy breach; an over-redacted common noun is a small classification quality hit.**
Set the score threshold low and accept false positives. Then measure the classification-quality cost of
that choice (DPG-35) so the trade is known rather than assumed.

### Acceptance

- [ ] NER licence resolved (Q-12) — used, replaced, or self-fine-tuned. **Do not ship an unlicensed model into a DPG submission**
- [ ] Hosting decision made (Q-12c) and its image-size cost measured and recorded
- [ ] Presidio transformers engine wired with the per-language entity mapping
- [ ] Threshold tuned for recall; the chosen threshold and its rationale recorded
- [ ] Dependencies added to the right requirements file per CLAUDE.md, and the image builds **in Docker**
- [ ] Graceful degradation: if the NER model fails to load, DPG-31's deterministic layer still runs and
      the failure is loud (a silent drop to regex-only is a privacy failure that looks like success)

### ✅ Questions — answered

- **Q-12** — ✅ **email the author first; budget the openly-licensed fine-tune as the fallback** and treat it
  as a releasable DPG contribution. No longer blocks Sprint 3, because this ticket left the sprint.
- **Q-12b** — ✅ **redact at transmission** (see [DPG-31](#dpg-31), and the mapping-is-PII constraint it added).
- **Q-12c** — ✅ **a dedicated service, medium term, as its own initiative.** Hence the scope banner above.

---

## DPG-33 — Redaction at the model-call boundary {#dpg-33}

Both surfaces. **This is why Sprint 1 comes first**: after DPG-11/DPG-12 there are two chokepoints
instead of nine call sites.

### Steps

1. Hook `redact_for_model` into the client factory path — as an explicit, opt-**out** step, not an
   opt-in one a new call site can forget.
2. **Restore where the output needs the original.** Classification output is machine-consumed and stays
   redacted. But `grievance_summary` is shown to the complainant and stored, and translation output
   feeds the English record — those need `restore()` applied to the model's output using the same
   mapping. Get this wrong in either direction and you either leak or you ship `<PERSON_1>` to a user.

   > ⚠ **AMENDED 2026-08-27 — "the summary" is three different artefacts, and one field cannot serve all
   > three.** The step above restores names into a single `grievance_summary`, which means restoring them
   > into the copy that is **cached in `ticketing.tickets` by design** (CLAUDE.md data rule 4) and travels
   > from there into the officer queue, officer search and the XLSX quarterly report. Verified consumers:
   >
   > | Consumer | Where | Needs names? |
   > |---|---|---|
   > | **Complainant-facing** — confirmation email, status-check display | `actions/action_outro.py:220`, `actions/services/status_check/display.py:30` | **Yes.** They wrote the name; `<PERSON_1>` back at them is absurd. ⚠ The email leaves over the SMTP relay, and it can carry the *accused's* name too — an egress in DPG-30's table |
   > | **Stored / cached / reported** — `public.grievances`, `ticketing.tickets`, queue, search, XLSX | CLAUDE.md rule 4 | **This is the open question.** Names here are what spreads laterally |
   > | **Model-facing** — the translation call's input | `LLM_services.py:563` | **No**, unconditionally |
   >
   > ⭐ **This is the highest-leverage decision in the sprint.** A stored summary with no names makes the
   > entire officer-side surface clean — queue, search, reports, and the ticketing backup — and it is the
   > mechanism that could retire rule 4's *"the asymmetry is intentional. Do not 'fix' it"* caveat, which
   > exists only because there has never been a way to make the summary safe.
   >
   > **Decide it in this sprint, even if the storage half is built in the next one** (see
   > [`followups/encrypt-the-original-work-from-the-redacted.md`](followups/encrypt-the-original-work-from-the-redacted.md)).
   > Restore-into-storage and redacted-storage are opposite implementations; building one and reversing it
   > is the expensive path.
3. **The ticketing surface has a subtlety.** `generate_case_findings`'s prompt already instructs the model
   *"NEVER include names, phone numbers, email addresses… Replace any that appear in notes with role
   descriptors"* (`ticketing/clients/llm_client.py:189-190`). **A prompt instruction is not a control** — it does nothing
   about what is *sent*, only about what comes back. Keep it (defence in depth) and add real redaction
   on the input.
4. **Audio is not redactable.** `transcribe_audio_file` sends the raw waveform; a voice note carries the
   speaker's name in the speaker's own voice. There is no redaction step available before transcription.
   **State this explicitly in the inventory and the privacy assessment**, and note that it is the
   strongest single argument for T2: for voice, only moving the inference endpoint solves it. Redaction
   applies to the transcript, immediately after.
5. ✅ **`parse_llm_response`'s error path is already clean** — `LLM_services.py:490` logs the response
   **length**, not the body, and has since DPG-13, which delivered that half of T-34-c early. The
   raise carries a length too, not the reply. There is nothing to fix here: check it has not
   regressed, and when adding context to `LLMResponseParseError`, do not put the body back.

### Acceptance

- [ ] Redaction applied at both client chokepoints, opt-out rather than opt-in
- [ ] `restore()` applied where output reaches a human or storage; a test per direction
- [ ] **Which of the summary's three consumers receives names is decided and recorded** (step 2's
      amendment), even if only the complainant-facing half ships this sprint
- [ ] **Output redaction (§31.4) applied to both summary-producing prompts** — the classification call and
      the translation call — with a test that a name surviving generation cannot be persisted
- [ ] Ticketing prompt instruction kept **and** input redaction added
- [ ] Audio's irreducibility documented in the inventory and the privacy assessment
- [ ] `tests/ticketing/test_pii_boundary.py` and `test_boundary_policy.py` still green
- [ ] `docs/deployment/11_llm_pipeline_policy.md` updated (with DPG-36)

---

> ⚠ **Found 2026-08-18 while answering *"how is the phone number sent to the LLM?"* (it is not —
> see [`02` §19.0b](02-llm-agnostic-spec.md#dpg-19)). Two log lines this ticket must cover, and
> neither was in its inventory:**
> `backend/actions/services/contact/phone.py:27` logs the complainant's phone at **INFO** on every
> validation — `logger.info("%s - Validating phone: %s", action_name, slot_value)` — and `:38` logs
> it again on the invalid path. Recorded, not fixed — Sprint 1 does not touch it, and it is still
> there. It now heads DPG-34's step 2 list below, which is where the work is.

## DPG-34 — Redaction at the logging, Celery, and backup boundary {#dpg-34}

**The leak that actually happens.** Do not treat this as the smaller half of the sprint.

### Steps

1. **A logging filter that redacts before anything is written.** Wire it into `backend/logger/logger.py`
   (`TaskLogger`) so it covers every service, rather than at individual call sites — one filter,
   installed once, cannot be forgotten by the next call site.
2. **Fix the known raw-text log sites**, at minimum:
   - `backend/actions/services/contact/phone.py:27` — logs the complainant's phone at **INFO on every
     validation**, and `:38` logs it again on the invalid path. **This is the leak that actually
     happens**: no model, no third party, just the phone number in the container logs of every intake.
     Start here
   - `LLM_services.py:500` — `_grievance_ref()` bounds the translation error messages to the
     `grievance_id` plus **the first three words** (60-char cap), which is what DPG-19.3 left behind.
     Three words is still narrative and can read *"Er. Sharma refused"*: a bounded, deliberate residual
     that this ticket is the one to close. The function's own docstring says so
   - Audit the rest against DPG-30's inventory
   - **Follow the existing precedent**: `db_debug_log.text_len_for_log` already logs lengths, not
     content — `LLM_services.py:616` and `:647` use it on the SEAH path
   - ✅ **Two sites this list used to name are already fixed** and are not work: `parse_llm_response`
     logs the response length (`:490`, DPG-13), and the translation paths no longer interpolate the
     whole `input_data` dict (DPG-19.3 / D-29)
3. **Celery payloads.** `input_data["values"]["grievance_description"]` is serialised into Redis on every
   intake. Decide and implement: pass a grievance ID and let the task read the text from Postgres, or
   redact the payload. **Passing the ID is cleaner** and removes the store entirely rather than
   obscuring it — but it changes the task signature, which touches `backend/task_queue/`, a stable shared
   service. Weigh it; if deferred, log it.
4. **Redis persistence.** Check whether RDB/AOF is on and whether the volume is backed up. An unredacted
   payload in memory for 30 seconds is a different risk from one in a nightly snapshot.
5. **Backups.** Confirm destination and jurisdiction. This is an indicator-7 answer, not a nice-to-have.
6. **Write the rule for future observability.** There is no tracing tool today. When one is added it must
   not capture full prompt bodies. Put that in `docs/deployment/13_security.md` so it is found by the
   person who adds it, not after.

### Acceptance

- [ ] Logging filter installed at `TaskLogger`, covering every service
- [ ] The three known raw-text log sites fixed; the rest audited against DPG-30
- [ ] Celery payload decision made, implemented or logged as a followup with a measured rationale
- [ ] Redis persistence and backup jurisdiction verified **in-container** and documented
- [ ] The future-observability rule written into `docs/deployment/13_security.md`
- [ ] A test proving a grievance narrative passed to a logger does not appear in the emitted record

---

## DPG-35 — Measure recall, and publish the number — **split** {#dpg-35}

> **⚠ SPLIT 2026-08-17.** With [DPG-32](#dpg-32) moved out (Q-12c), most of this ticket's metrics measure a
> layer this sprint no longer ships. But **"we shipped redaction and never measured it" is not an acceptable
> outcome either** — the whole point of this ticket is that an unmeasured control is a compliance artefact.
> So:
>
> | Metric | Where it lands |
> |---|---|
> | **Phone recall, split by digit system** | **Stays in Sprint 3.** It measures DPG-31, and it is the single most important number here — see T-31-a |
> | **Vehicle / citizenship / email recall** | **Stays.** Deterministic patterns, shipped this sprint |
> | **Classification-quality delta, redacted vs raw** | **Stays**, reduced: measures over-redaction from deterministic patterns only |
> | PERSON recall / precision | **Stays, as a rule-layer number.** §31.2b detects names deterministically, so there *is* something to measure — and measuring it turns "some names get through" from a hedge into a disclosed figure |
> | Third-party-name recall | **Stays**, reported separately from complainant self-identification: different legal category, and the title-trigger recogniser behaves very differently on the two |
> | Voice-origin subset | ⏸ **Deferred** — voice is not live (Q-13.2) and there is no ASR budget |
>
> **The honest headline for Sprint 3 is therefore:** *numeric identifiers closed; person names substantially
> but not completely removed, with the residual measured.* Publish the number. A table that omits PERSON reads
> as a control that covers names; one that claims PERSON with no figure reads as a control that works.

A redaction system nobody measured is a compliance artefact, not a control. DPG-20's labelled PII spans
serve this (synthetic in phase 1, Q-15).

### Measure

| Metric | Why |
|---|---|
| **PERSON recall** | The number that matters. A missed name is a breach |
| PERSON precision | The cost side of the recall-first threshold |
| Phone recall, **split by digit system** | ASCII vs Devanagari, reported separately — an aggregate hides the exact failure this sprint exists to prevent |
| Third-party-name recall | Reported separately from complainant self-identification; different legal category, and likely different model performance |
| **Classification-quality delta, redacted vs raw** | The cost of over-redaction. If accuracy falls materially, the threshold is wrong |
| Voice-origin subset, separately | Transcribed speech is the hardest input and the one that guarantees self-identification |

### Acceptance

- [ ] Recall measured on the labelled Nepali test set and **published** at `docs/dpg/pii-redaction-evaluation.md`
- [ ] Phone recall split by digit system
- [ ] Third-party names scored separately
- [ ] Classification-quality delta measured — the over-redaction cost is known, not assumed
- [ ] Voice subset reported separately
- [ ] The number stated plainly, including where it is weak. WikiANN-trained NER on colloquial
      transcribed speech will underperform its published F1; **say so**

---

## DPG-36 — Reconcile the live spec {#dpg-36}

`docs/deployment/11_llm_pipeline_policy.md` §PII boundary model states:

> `public.grievances.grievance_summary` ← **MUST be PII-scrubbed before storage**

**Nothing scrubs it.** There is no scrubber in the codebase today. This is a live spec asserting a
control that does not exist — engineering rule 9, and precisely the failure mode CLAUDE.md's own amended
data-rules section documents at length (*"This line claimed decryption for months before it was true"*).

Also reconcile CLAUDE.md data rule 4's honest caveat — *"`grievance_summary` is free text and can contain
self-disclosed PII… The asymmetry is intentional. Do not 'fix' it"* — with whatever this sprint actually
builds. If redaction now happens at transmission rather than at storage, that caveat still stands and
should say so explicitly, with the new reason.

> ⭐ **Added 2026-08-27 — there may now be a way to retire that caveat rather than restate it.** Rule 4's
> asymmetry exists because there has never been a way to make the summary safe to cache. Generating the
> summary downstream of the pseudonymiser, plus the output pass in [§31.4](#dpg-31), is that way: the model
> never receives the name, and a name that survives generation cannot be persisted. **If [DPG-33](#dpg-33)
> step 2 decides the stored summary carries no names, this ticket amends rule 4 instead of re-explaining
> it** — and moves the reason with the rule, per CLAUDE.md's own instruction. If it decides otherwise,
> restate the caveat with the new reason as originally written.

### Steps

1. ~~Decide (Q-12b)~~ ✅ **Decided: redact at transmission** (2026-08-17). This ticket no longer waits on a
   decision — it is now purely the doc fix, which is what it should have been all along.
2. Rewrite the section to describe what is **built**, with the reason moved alongside the rule
   (engineering rule 7). ⚠ **And what is *not* built:** with DPG-32 out of scope, person names are not
   redacted. The rewritten section must say so with a `⚠ Not built` marker rather than describing redaction
   in general terms that imply name coverage.
3. If any part remains aspirational, mark it `⚠ Not built` — do not leave a second unverified claim.
4. Update the data-flow diagram (DPG-04) to show the redaction boundary where it actually sits.
5. Update CLAUDE.md data rule 4's caveat if this sprint changes what it describes.

### Acceptance

- [ ] `11_llm_pipeline_policy.md` describes built behaviour, with reasons attached
- [ ] Anything unbuilt marked `⚠ Not built`
- [ ] Data-flow diagram shows the redaction boundary
- [ ] CLAUDE.md rule 4's caveat reconciled
- [ ] No new unverified claim introduced anywhere in this sprint's documentation

---

## Sprint 3 acceptance criteria

- [ ] **No unredacted numeric identifier** in any outbound model call — verified by test, at the chokepoint
- [ ] No raw grievance text in logs, traces, or Celery payloads — verified by test
- [ ] **Devanagari-digit phone numbers detected** — explicit test case (T-31-a)
- [ ] **Third-party names in narrative — detected at the rule layer** (§31.2b: titles, surname gazetteer,
      self-identification), with the **known residual measured and disclosed**. Not "handled", not
      "unaddressed" — a number, published, with the provider's terms named beside it
- [ ] Deterministic PERSON recall measured and published **as a rule-layer number**, with the ML tier's
      absence stated as the reason it is not higher
- [ ] Officer dashboard still shows full unredacted text — redaction is at transmission (Q-12b), not at
      storage. ⚠ **Q-12b revisited 2026-08-27** with a third option that keeps the original encrypted
      rather than discarding it ([§31.3](#dpg-31)); the decision this sprint owes is
      [DPG-33](#dpg-33) step 2, not the whole design
- [ ] **Model output is redacted before persistence, not only model input** (§31.4), on **both**
      summary-producing prompts. Any prompt-level instruction is recorded as defence in depth and
      never as a control
- [ ] **The restore mapping is either never persisted, or protected as the PII it is** — not in `ticketing.*`,
      **never serialised alongside the text it dereferences, and never leaving Nepal**
- [ ] **Nothing produced by this sprint calls the result "anonymised".** It is pseudonymisation: we hold the
      key, so the data stays personal data. The defensible claim is *only pseudonymised text crosses the
      border, and the re-identification key never leaves the country*
- [ ] Audio's irreducibility documented. ⚠ It is **no longer a T2 argument** — T2 is parked (Q-03/Q-05), so
      it stands as an accepted, disclosed residual exposure instead
- [ ] Data-flow diagram updated to reflect the redaction boundary
- [ ] `tests/ticketing/test_pii_boundary.py` and `test_boundary_policy.py` green throughout
- [ ] Every deferral logged in `followups/` + `TODO.md`, same commit
