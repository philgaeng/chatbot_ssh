# Follow-up — encrypt the original narrative, work from the redacted one, reveal by case type

> **Raised:** 2026-08-27, by the owner, in the conversation that produced §5.4 of the privacy assessment.
> **Status:** 🔵 **Proposed — a sprint after Sprint 3**, not a Sprint 3 ticket. Parts of it constrain
> Sprint 3's design, and those parts are written into [`04-pii-redaction-spec.md`](../04-pii-redaction-spec.md).
> **Why it cannot be Sprint 3:** it needs a redacted derivative to exist before anything can work from one.
> **Why it should not wait longer than that:** Sprint 3's DPG-33 currently specifies the *opposite*
> behaviour for `grievance_summary` (restore names into storage). Building that and then reversing it costs
> more than deciding now which way it points.

---

## The proposal

1. **Encrypt the original, unedited narrative** — the artefact most likely to carry PII, including PII
   from people who never consented.
2. **Work from the redacted derivative from that point on** — officer queue, ticket cache, search,
   reports, model calls, logs.
3. **Reveal the original through a deliberate, audited action** when a case genuinely needs it.

## What it revisits, and why that is legitimate

**Q-12b (2026-08-17) decided "redact at transmission, never before storage"**, and the reason recorded was
*"the officer's ability to act on a case — a GRM officer needs to know which engineer was named."*

⭐ **The option that lost was "redact before storage" — the original is gone.** This is a third position
Q-12b did not consider: the original is *kept*, encrypted, and reachable on the record. It **answers**
Q-12b's objection rather than overriding it. The officer still learns which engineer was named; they ask,
and the asking is logged.

## The correction that makes it buildable

⚠ **The decryption cannot live in the ticketing app.** Ticketing holds no encryption key and has no
accessor for one — T3-04 removed it deliberately and
[`tests/ticketing/test_pii_boundary.py`](../../../../tests/ticketing/test_pii_boundary.py) pins it. A
`decrypt()` in `ticketing/` breaks a locked rule (CLAUDE.md §Data rules 5, privacy assessment §1.4).

**The shape that works — and it is already built for contact details:**
[`ticketing/api/routers/tickets/pii.py:121`](../../../../ticketing/api/routers/tickets/pii.py) —
`begin_reveal` / `close_reveal` takes a **reason code plus free-text justification**, records the actor,
gates on the sensitive cast, time-boxes the window, and obtains the plaintext by **calling the backend**
rather than decrypting locally. Extending that to the narrative is a smaller piece of work than building
a reveal path from nothing.

**So: decryption in `backend`, audit trail in `ticketing.admin_audit_log`, cast gate as today.**

## ⭐ The reveal is scoped by case type, not rationed by frequency

The first version of this analysis asked *"what fraction of cases need the original?"* and proposed
treating a high number as evidence the control was theatre. **That framing is wrong, and the owner's
correction is the important content of this document:**

> If the grievance accuses an officer — or anybody — of misconduct, the officer handling it obviously
> needs the original. It is not a question of percentage.

For an accusation, **the accused's identity *is* the grievance.** You cannot investigate "a foreman". No
statistic speaks to that; it is categorical. So:

| Case type | The original |
|---|---|
| Misconduct accusation, SEAH | Travels with the case to the assigned officer and cast. Normal path, not an exception |
| Dust, potholes, compensation delay, access | The redacted derivative is sufficient; the original is rarely opened |

**What the control protects, then, is not the assigned officer — it is everyone else.** Today the accused's
name flows into the summary cached in `ticketing.tickets`, the officer queue, officer search, the XLSX
quarterly report, Celery payloads, log lines, the ticketing backup, and across the border on every model
call. **None of those is the assigned officer.** The target is lateral spread.

### And the two decisions must stay separate

The first analysis conflated them; they are independent:

- **To the model provider:** redact *always*. The accused never consented, is not a party to the process,
  and has no idea a foreign company received their name. Nothing about the officer's need touches this.
- **To the officer:** by case type, per the table above.

### A due-process argument, not only a privacy one

Privacy assessment §1.1 row 2 names third parties — *"a named individual accused of misconduct — No.
Never asked"* — as the class this system creates by accepting free text. Containing that name to the cast
handling the case is **the system declining to broadcast an unproven accusation**. That is a fairer thing
to do to the accused, and it tends to land better with an executing agency than a statutory argument.

## The summary is the highest-leverage piece, and it is a Sprint 3 decision

**Generate the summary downstream of the pseudonymiser.** If the model never receives the name it cannot
put one in the summary — a structural guarantee rather than a behavioural one. This matters more than it
sounds because **the summary is the artefact that escapes into the officer system**: cached into
`ticketing.tickets` by design (CLAUDE.md data rule 4), and from there into the queue, officer search and
the quarterly XLSX.

A clean summary makes that whole surface clean, and it is the mechanism that could finally retire rule 4's
standing *"the asymmetry is intentional. Do not 'fix' it"* caveat — which exists only because there was no
way to make the summary safe.

⚠ **This collides with Sprint 3 as written.** [DPG-33](../04-pii-redaction-spec.md#dpg-33) step 2
currently says `grievance_summary` needs `restore()` applied to the model's output. That puts the names
back into the stored, cached, reported artefact. See the amendment in the spec: the summary has **three
consumers with different needs**, and one field cannot serve all three.

### A prompt gate is worth adding and worth not counting

The owner also proposed instructing the model not to name anybody. Worth doing as defence in depth —
**and it must not be recorded as a control.** It only acts in the case where redaction *missed* a name,
which is exactly where a prompt instruction is least dependable: a missed name looks to the model like
ordinary narrative. The spec already makes this point about the ticketing prompt
([DPG-33](../04-pii-redaction-spec.md#dpg-33) step 3: *"A prompt instruction is not a control"*), and the
same standard applies here.

**The enforceable version is cheap:** run `redact_for_model()` over the generated summary before it is
persisted. Same function, one more call site, two sentences of input, deterministic and pinnable by a
test. It converts *"we asked the model not to"* into *"a summary carrying a detected name cannot be
stored"* — and it covers **both** summary-producing prompts without anyone having to remember there are two.

## Three things this sprint must cover or explicitly exclude

- [ ] **Voice recordings and photographs.** The audio *is* the original and cannot be redacted — a voice
      identifies its speaker. Plaintext on disk today
      ([privacy assessment §1.2](../../../dpg/privacy-assessment.md)). Encrypt the transcript while the
      recording sits beside it in the clear and the design has a hole where the most identifying material is
- [ ] **Officer notes.** Free text in `ticketing.*`, outside redaction entirely. Officers will type the
      names straight back in — *"spoke to Ram Bahadur, he denies it."* In scope, or explicitly not
- [ ] **The re-identification mapping.** [DPG-31 §31.3](../04-pii-redaction-spec.md#dpg-31) requires that
      if persisted it inherits *"the same encryption boundary, same access control, same audit trail,
      same retention clock"* as the record it dereferences — and today no such home exists. ⭐ **This
      design creates one.** The encrypted original is exactly where the mapping belongs

## Definition of done

- [ ] Q-12b reopened and re-decided with the third option on the table, reason recorded alongside
- [ ] The narrative's encryption boundary defined — same key as `ENCRYPTED_FIELDS` or its own, and BU1's
      custody question answered for whichever it is ([privacy assessment §5.4](../../../dpg/privacy-assessment.md))
- [ ] Reveal extended from contact details to the narrative, reusing `begin_reveal` / `close_reveal`;
      **decryption stays in `backend`**, and `test_pii_boundary.py` stays green
- [ ] Case-type routing decided: which streams carry the original to the assigned officer by default
- [ ] Voice, officer notes and the mapping each in scope or explicitly excluded, with the reason
- [ ] CLAUDE.md data rule 4's caveat retired or restated, per DPG-36

## Related

- [`../04-pii-redaction-spec.md`](../04-pii-redaction-spec.md) — DPG-31 §31.3 (Q-12b), §31.4 (output
  redaction), DPG-33 step 2 (the summary conflict), DPG-36 (rule 4)
- [`../../../dpg/privacy-assessment.md`](../../../dpg/privacy-assessment.md) — §1.4 (why ticketing cannot
  decrypt), §4 (third-party PII), §5.4 BU1 (key custody)
- [`../../../TODO.md`](../../../TODO.md) 🔵 TECH DEBT
