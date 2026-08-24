# Questions for the DPG consultant

> ⚠ **Generated file — do not edit.** These questions live under the indicator they belong to
> in [`00_compliance_status.md`](00_compliance_status.md), next to the evidence behind them.
> This file is extracted from it by `scripts/ops/gen_dpg_questions.py`, and
> `tests/repo/test_dpg_questions_generated.py` fails the build if the two disagree.
> **To change a question, edit `00_compliance_status.md` and regenerate.**
>
> **23 questions**, of which **5 are marked 🔴** — we cannot finish the
> work without those.
>
> **Numbers are derived from structure**: `Q-04-02` is the second question about indicator 4,
> and `Q-00-xx` are process questions belonging to no indicator. Inserting a question therefore
> never renumbers another one.
>
> **These are deliberately short and open.** The evidence behind each sits in the section it was
> extracted from. The judgement is yours — a question that arrived pre-argued would be asking you
> to check our reasoning rather than to give us yours.

---

## Indicator 2 — Open licensing

- **Q-02-01 — Do you have any objection to Apache-2.0?**
  It is applied repository-wide and every file is stamped, so a change is mechanical but not free. We
  would rather change it now than after a submission.

- **Q-02-02 — Do any of these licences cause a problem for the assessment, or in ADB/DOR procurement?**
  AGPLv3 (Redis, elected from its three), LGPL-with-linking-exception (`psycopg2-binary`), and two
  transitive LGPL libraries. All OSI-approved, all weak copyleft, none modified by us.

## Indicator 3 — Ownership

- **Q-03-01 🔴 — How is IP ownership determined for software developed under a loan-financed
  engagement, and who signs that determination?**
  We cannot name a copyright holder or submit without it.

- **Q-03-02 🔴 — What is the correct channel to open that request?**
  We do not know whether the consultant is the right door.

## Indicator 4 — Platform independence

- **Q-04-01 🔴 — How does the DPGA assess platform independence for an AI system?**
  Specifically, what weight sits on a configurable and tested open alternative versus on what
  production actually runs. Our answer today is the first of those.

- **Q-04-02 — How does the DPGA treat open-weight models whose licences are not OSI-approved?**
  We filter for Apache-2.0 and MIT, which excludes several of the strongest multilingual models for
  Nepali — including one purpose-built for low-resource languages.

- **Q-04-03 — How does the DPGA treat a partial open alternative?**
  Ours serves every model call the system makes; the one path it cannot serve is switched off on cost
  grounds and is not expected to be funded.

- **Q-04-04 — What does the *data* limb of the AI questionnaire expect from a system that does no
  training and no fine-tuning?**
  Every call is zero-shot prompting, so there is no training-data licence question. We have published a
  105-item labelled evaluation set under CC0-1.0; we do not know whether the prompt templates are also
  expected.

- **Q-04-05 — How much benchmark evidence does a submission need to substantiate an open-alternative
  claim?**
  Each measurement costs owner-funded inference, so we would rather know the bar than guess at it.

## Indicator 7 — Privacy & applicable laws

- **Q-07-01 — What posture do the DPGA or ADB safeguards policy expect on personal data held in free
  text?**
  We redact at transmission rather than before storage, a deliberate choice with consequences either
  way.

- **Q-07-02 — Would an openly-released Nepali anonymiser model count as a DPG contribution, and is
  there ADB appetite to fund one?**
  The most accurate existing Nepali NER model states no licence at all, so the gap is real and the
  contribution would be reusable well beyond this project.

- **Q-07-03 🔴 — Does ADB or the DPGA expect a signed data-processing agreement with the inference
  provider?**
  Unless a provider is pinned, the router selects a different third-party processor per request, and
  its terms reference no DPA.

- **Q-07-04 — Does the DPGA expect a legally-reviewed privacy assessment, or is a documented
  engineering one sufficient?**
  Ours is written and thorough; no lawyer has read it, and we would need to resource that.

- **Q-07-05 — Does the DPGA have a position on cross-border processing for a national-government DPG?**
  There is no authority in Nepal to seek an adequacy finding from.

- **Q-07-06 — Does the DPGA expect a data subject to be able to erase their record, in a system whose
  integrity depends on them not being able to?**
  We would rather have your view than discover at assessment that a delete button was expected.

- **Q-07-07 🔴 — What does the DPGA accept as evidence of privacy compliance where there is no
  operational data protection authority, and does ADB impose data-protection requirements on an
  executing agency?**
  Without an answer we build to our own reading of an untested statute.

## Indicator 8 — Standards & best practices

- **Q-08-01 — Which project-hygiene artefacts does the DPGA require?**
  We have `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` and issue/PR templates. We have no
  governance model and no versioning policy, and would rather write what is required than guess.

## Indicator 9 — Do no harm

- **Q-09-01 — Is a recall-first safeguarding classifier with human review the posture the DPGA or ADB
  safeguards policy expects, and what evidence does it expect for it?**
  We can measure and publish the false-alarm rate and the return latency; we do not know whether a
  threshold is expected on either, or whether the expectation runs the other way.

## Process questions

- **Q-00-01 — Has ADB nominated software as a DPG before, and what should we take from how it was
  handled?**

- **Q-00-02 — What is the submission route?**
  Whether ADB nominates or we self-submit with endorsement, and whether the implementing agency needs
  to be a party.

- **Q-00-03 — When in the engineering should the assessment start, and how long does it usually take?**
  We started it late enough that some of it became remediation.

- **Q-00-04 — Does the assessment consider who funds and operates the system after the pilot?**
  Our inference budget is time-boxed and personally funded, and the CI job producing the indicator-4
  evidence has no owner beyond that.

- **Q-00-05 — What are we missing?**
  Anything in the current Standard revision, or the AI-systems guidance, that we would not find by
  reading the published documents.
