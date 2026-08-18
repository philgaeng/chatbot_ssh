# Sprint 0 — Licensing & governance (DPG-01…06)

> Branch `dpg/sprint0-licensing` · **Starts immediately, runs in parallel with everything else.**
> Not code. These are harder failures than the API question, and two of them have long external lead times.
> Context: [`00-dpg-context-and-decisions.md`](00-dpg-context-and-decisions.md) §4 (evidence pack), §5 (open decisions).

---

## Required reading

Before the first commit, in this order:

1. [`CLAUDE.md`](../../../CLAUDE.md) — §Git workflow (never `main`), §Conventions
2. [`docs/PROGRESS.md`](../../PROGRESS.md) → [`docs/TODO.md`](../../TODO.md) — what exists, what's queued
3. [`docs/engineering/00_engineering_index.md`](../../engineering/00_engineering_index.md) — the ten rules; **rule 9** (never write an unverified doc claim) is the whole of DPG-02
4. [`docs/engineering/06_documentation_lifecycle.md`](../../engineering/06_documentation_lifecycle.md) — where a new doc lives, and honesty markers
5. [`docs/sprints/README.md`](../README.md) — the standing deferral rule
6. [`docs/deployment/DOCKER.md`](../../deployment/DOCKER.md) — DPG-02 runs `pip-licenses` **in the container**, against the image's resolved tree, not the host's
7. [`docs/deployment/13_security.md`](../../deployment/13_security.md) — DPG-04 extends it
8. [`README.md`](README.md) — this sprint's conventions and ticket map

**`docs/dpg/` already exists** — the compliance audit created it
([`00_compliance_status.md`](../../dpg/00_compliance_status.md), 2026-08-17) and `docs/README.md` already
carries the row (`:22`, `:143-151`). This sprint fills it: `dependency-licenses.md` (DPG-02),
`ip-ownership.md` (DPG-03), `privacy-assessment.md` (DPG-04). **Add each file to the `docs/README.md` table
as it lands** — that index is the discovery path for the whole tree, and a folder row without file rows
sends a reader to a directory listing.

---

## §0 — Corrections to the source narrative

| The guide says | Reality | Effect on this sprint |
|---|---|---|
| "⚠️ **Verify Rasa 3 specifically.** Rasa is architecturally load-bearing here… if a core Rasa dependency is non-OSI, that is a far bigger indicator-2 and indicator-4 problem than anything in this plan. Check this in week one." | **There is no Rasa.** No `rasa_chatbot/` directory (CLAUDE.md's folder listing is stale on this point, and so is the root `README.md` — **DPG-06** now owns both). No Rasa service in `docker-compose.yml` or `docker-compose.grm.yml`. `requirements.txt:2-6` states it outright: *"No Rasa NLU / TensorFlow server – only Rasa SDK actions."* The single dependency is `rasa-sdk==3.6.2` (`requirements.txt:25`), Apache-2.0, supplying the `Tracker` / `CollectingDispatcher` types the hand-rolled FastAPI orchestrator still speaks | The alarm is ~resolved before it is raised. DPG-02 confirms it mechanically. **Do not budget a week.** ⚠ Confirm the licence from the resolved tree rather than from this paragraph — that is the point of DPG-02 |
| `pip-licenses` output → `docs/dependency-licenses.md` | The repo has **three** dependency sets: `requirements.txt` (chatbot), `requirements.grm.txt` (GRM/ops), and `channels/ticketing-ui/package.json` (Next.js 16 portal, npm tree). A Python-only audit misses the entire frontend | DPG-02 audits **all three**, or the submission has a hole a reviewer will find in one `ls` |
| Dependencies are what the manifests declare | **There is a fourth set nobody was auditing: container images.** Four of them — `redis`, `postgres:15`, `nginx:stable`, `quay.io/keycloak/keycloak:26.0.7` — and **the licence drift that actually happened, happened there.** `redis:7` was a floating tag that followed upstream onto the RSALv2/SSPLv1 line (non-OSI) with nobody editing the file. Found while writing [`docs/dpg/00_compliance_status.md`](../../dpg/00_compliance_status.md) §3.1(b), **after this spec was written**; fixed by pinning `redis:8.10` and electing AGPLv3 | DPG-02 audits **four** sets, and adds a **pin-drift check** — a floating tag is a licence you did not choose |

---

## DPG-01 — `LICENSE`, `NOTICE`, SPDX headers {#dpg-01}

**Indicator 2 currently fails outright.** Verified: no `LICENSE`, no `NOTICE`, no `COPYING` at the repo
root. No licence means all-rights-reserved. This is a categorical DPG fail and a five-minute fix.

**Apache-2.0 is the recommendation, and it is no longer a decision.**

> **⚠ MOVED BACKWARDS 2026-08-17 (Q-02): the licence choice is delegated to the DPG consultant.** This spec
> previously read *"Use Apache-2.0 over MIT"* as settled. It is not. The case for Apache-2.0 stands — an
> express patent grant matters when a government adopts the code and other country teams fork it, and MIT
> has none — but **present it as a recommendation awaiting confirmation**, not as the chosen licence.
>
> **This ticket is now blocked on two external answers, not one:** the licence *text* (Q-02, consultant) and
> the copyright *holder* (Q-01/DPG-03, ADB OGC). Since indicator 2 fails outright with **no** licence at all,
> that is worth stating plainly to both parties: **the cheapest categorical fix on the list is waiting on
> other people.** ⭐ If the consultant has no objection to Apache-2.0, say so and land it — do not let a
> five-minute fix wait weeks for a preference nobody actually holds.

⚠ **Sequencing caveat.** DPG-01 is trivial to execute and *may be premature to commit*: you cannot
license code you may not own. See DPG-03. If the OGC read is expected within days, land DPG-01 anyway —
a licence is reversible before publication, and having it in place unblocks everything downstream. If it
is expected in months, land it and note the dependency in `PROGRESS.md`.

### Steps

1. `LICENSE` — the Apache-2.0 text, verbatim, at the repo root.
   ```bash
   curl -sL https://www.apache.org/licenses/LICENSE-2.0.txt -o LICENSE
   ```
2. `NOTICE` — attribution block. Must name the copyright holder decided by **DPG-03 / Q-01**. If DPG-03
   is unresolved, write the placeholder and mark it `⚠ Pending IP determination — DPG-03`.
3. `SPDX-License-Identifier: Apache-2.0` headers on source files.
   - Scope: every tracked `.py` under `backend/`, `ticketing/`, `ops/`, `scripts/`; every tracked
     `.ts`/`.tsx` under `channels/`. **Excluded:** generated files, vendored assets, `docs/`, migrations
     (which already carry a mandated safety header — add SPDX *above* it, do not displace it).
   - Do it with a script committed under `scripts/ops/`, not by hand — it must be re-runnable when files
     are added, and a reviewer will ask how coverage is maintained.
4. `README.md` (repo root) — a Licence section pointing at `LICENSE`, and the copyright line.

### Acceptance

- [x] `LICENSE` present at repo root, byte-identical to the canonical Apache-2.0 text — `md5sum` is
      `3b83ef96387f14655fc854ddc3c6bd57`, the canonical value. ⚠ **Landed provisionally**: Q-02 is still with the
      consultant, and the licence is adopted so work can proceed. `NOTICE` says so rather than implying a settled choice
- [x] `NOTICE` present, **explicitly marked pending DPG-03** — it carries the unfilled Apache-2.0 template line and a
      paragraph saying the holder is not determined and must not be filled in from inference
- [x] If either external answer is still outstanding when the sprint closes, **the blocker is named in
      `PROGRESS.md` with the date it was raised** — done: [`PROGRESS.md` §Sprint 0's two external blockers](PROGRESS.md),
      a table with both questions, who can answer each, and **blank date fields to fill in**. The date fields are blank
      because the letters have not gone; that is the honest state, and the row makes the gap visible instead of silent
- [x] SPDX header present on every in-scope source file; the adding script committed and re-runnable —
      `scripts/ops/add_spdx_headers.py --check` reports **585/585**, and `tests/repo/test_spdx_headers.py` fails the
      build if a file drifts out of coverage
- [x] Repo `README.md` has a Licence section — coordinated with **DPG-06**, which rewrote the same file on 2026-08-18;
      the section survived the rewrite and gained the link to the generated dependency inventory
- [x] `docs/README.md` — a **file** row now exists for each of the four artefacts (`00_compliance_status.md`,
      `dependency-licenses.md`, `privacy-assessment.md`, `01_consultant_briefing.md`), plus a pointer to the
      root-level hygiene files that indicator 8 needs but that do not live under `docs/`

### Tests

See [`TESTS.md`](TESTS.md) → **T-01**. One test, and it earns its place: a `pytest` check that walks the
in-scope tree and asserts every file carries the SPDX header. Without it, coverage decays the first week
someone adds a module, and the indicator-2 evidence silently rots.

---

## DPG-02 — Dependency licence audit {#dpg-02}

You need this for the submission regardless, and it is the mechanical resolution of the Rasa question.

### Steps

1. **Python, both sets, in-container** (per CLAUDE.md §Docker-only — the host conda env is not what ships):
   ```bash
   docker compose --env-file env.local -f docker-compose.yml -f docker-compose.grm.yml \
     exec backend sh -c "pip install pip-licenses && pip-licenses --format=markdown --with-urls --with-license-file"
   ```
   Run it against **both** images — the chatbot image (`requirements.txt`) and the ticketing/ops image
   (`requirements.grm.txt`) — and label which is which in the output. They are not the same tree.
   > ✅ **DECIDED (Q-06): schedule it.** The licence scan joins `ops/security.py`'s existing scheduled run,
   > beside `pip-audit` — a different check on the same tree. A one-off audit is stale the next time
   > anyone adds a dependency, and **indicator 2 is a claim that has to stay true**, not a snapshot.
   > This is no longer optional and no longer deferrable to a followup.
2. **npm, the portal:**
   ```bash
   docker compose --env-file env.local -f docker-compose.yml -f docker-compose.grm.yml \
     exec grm_ui npx license-checker --production --summary
   ```
3. **Container images — the fourth set, and the one that drifted.** Four images across the two compose
   files. For each: the resolved digest, the upstream licence *at that version*, and whether the tag is
   floating.
   ```bash
   grep -rn "image:" docker-compose.yml docker-compose.grm.yml
   docker image inspect <image> --format '{{index .RepoDigests 0}}'
   ```
   Two findings are already established and must be **carried in, not re-derived** —
   [`00_compliance_status.md`](../../dpg/00_compliance_status.md) §3.1(b):
   - ✅ **`redis:8.10`, elected AGPLv3** (Redis 8 is tri-licensed RSALv2 / SSPLv1 / AGPLv3; only AGPLv3 is
     OSI-approved). Already changed in `docker-compose.yml` and the CI service block. Record the election
     explicitly — a reviewer who remembers the 2024 relicensing will see "Redis 8" and assume otherwise.
     The AGPL question is open with the consultant (its Q7a); Valkey is the costed fallback.
   - ⚠ **`psycopg2-binary` is LGPL-3.0-with-exceptions** — library-level copyleft with a linking
     exception, standard across the Python ecosystem. Give it a row and a stated disposition rather than
     letting a reviewer find it first (consultant Q7b).
   > **Add the pin-drift check.** The shape of the Redis finding was *a floating tag*, not Redis. Assert
   > every image is pinned to at least two segments — cheap, and it is the check that would have caught it.
4. **Triage.** For every dependency, record: name, version, licence, OSI-approved (Y/N), and — for any
   `N` or unknown — the replacement or the justification. Non-OSI in a *production* path is an
   indicator-2 blocker; non-OSI in a dev-only tool is not, but say which is which.
5. **Resolve the Rasa question explicitly**, in one row, with the version and the licence as resolved in
   the image, so nobody has to re-litigate it from the source narrative's alarm.
6. Write `docs/dpg/dependency-licenses.md`. Head it with the date, the images audited, and the commit SHA.
   It **supersedes `00_compliance_status.md` Appendix A**, which is a hand-written inventory marked
   `⚠ pending the generated report`. Say so in both places when it lands.

### Acceptance

- [x] `docs/dpg/dependency-licenses.md` covers all **four** dependency sets, each labelled — ⚠ **but split by
      *manifest*, not by image.** The spec's "both images" premise is wrong: one `Dockerfile` installs both
      `requirements.txt` and `requirements.grm.txt` into a single image (D-04). The report therefore splits
      **35 declared / 98 transitive** Python, plus **16 npm production**, plus **4 container images** = 153
- [x] Every image pinned to ≥2 segments, with the pin-drift check committed — `tests/repo/test_image_pins.py`,
      which also asserts Compose and CI declare the **same** image so CI cannot test a different Redis than production.
      ⚠ **Two explicit, justified exceptions**, in the test's `ACCEPTED_LOOSE_PINS` and repeated in the report:
      `postgres:15` and `nginx:stable`, each with a written claim that the licence is stable across the range the tag
      spans. It is a contract, not a suppression list — an entry without a stated reason is not allowed.
      The `redis:8.10` AGPLv3 election and the `psycopg2-binary` LGPL-with-exception disposition are both recorded
- [x] Every non-OSI or unknown-licence entry has a named disposition — **there are none.** Zero unknown, zero
      unparseable, zero non-OSI across 153 packages. Every entry carrying conditions beyond attribution has a written
      disposition anyway, including the two transitive LGPL packages nobody knew were in the tree
      (`jwcrypto`, `@img/sharp-libvips-*` — D-06)
- [x] `rasa-sdk` row present with its resolved licence, closing open decision #3 — **3.6.2, Apache-2.0**, the only
      Rasa-family package installed, with the "no server, no NLU, no TensorFlow" claim stated in the same row
- [x] **The scan runs on `ops/security.py`'s schedule** (Q-06) — `licence_scan()` at 01:50 nightly
      (`ops/scheduler.py:76`), writing to `ops.dependency_findings` beside `pip-audit`. Anything unrecognised surfaces
      as **high**, not as a pass. ⚠ **One honest caveat carried in the report:** `pip-licenses>=5.0` is declared in
      `requirements.grm.txt` but was installed ad-hoc for *this* scan, so the nightly job starts working on the next
      image rebuild
- [x] Doc header records date, images, commit SHA — `Generated 2026-08-18 · commit 8470df63`
- [x] Linked from `docs/README.md` and from the evidence pack table (row 2)

### Tests

None. This is a document. (Its freshness mechanism is the DPG-02 step-1 note, not a unit test.)

### ✅ Questions — answered

- **Q-06** — ✅ **scheduled**, in `ops/security.py` beside `pip-audit`.

---

## DPG-03 — IP ownership determination (ADB OGC) {#dpg-03}

**Indicator 3 requires documented ownership.** Who owns this code — you, ADB, or the Nepal implementing
agency? If any of it was written under an ADB contract, the IP may not be yours to donate.

**This is the longest lead time on the list and the only item nobody working on this repo can resolve.**
Open it with ADB's Office of the General Counsel **now**, in writing.

### Steps

1. Written request to ADB OGC. Include: repo URL, the contract(s) under which work was performed, the
   date range, the contributors, and the specific ask — *may this be released under Apache-2.0, and who
   holds copyright.*
2. Record the date sent in `PROGRESS.md`. This is a clock, and it should be visible.
3. On response: write `docs/dpg/ip-ownership.md` with the determination, the responder, and the date.
   Update `NOTICE` (DPG-01 step 2) to match.

### Acceptance

- [ ] Request sent, date recorded in `PROGRESS.md`
- [ ] `docs/dpg/ip-ownership.md` written on response
- [ ] `NOTICE` and repo `README.md` copyright line reconciled with the determination

### 🔶 Questions — **still blocking**

- **Q-01** — 🔶 **in flight, and check it is the right channel.** The owner is writing to the **DPG
  consultant** to initiate the discussion. ⚠ **That is not the same channel as ADB's Office of the General
  Counsel** — a consultant can advise on the DPG process but cannot issue an IP determination. If the
  consultant is the route *to* OGC, record it that way and record the date. **Nothing is decided until OGC
  responds in writing**, and DPG-01's `NOTICE` cannot name a holder until it does.

---

## DPG-04 — Privacy assessment + data-flow diagram {#dpg-04}

Indicators 7, 9, 9a. **This is a deliverable in its own right** — the DPGA asks for it, and Sprint 3 is
scoped by it.

> **Three answers reshaped this ticket on 2026-08-17.**
>
> **1. Q-08 — the benchmark is Nepal's Individual Privacy Act 2018, and there is nothing else.** No existing
> DOR or ADB data-sharing agreement to conform to. So this is **the first assessment**, which is the larger
> of the two shapes the question anticipated — write it as a baseline others will inherit, not a checklist.
>
> **2. Q-07 — an agent drafts it; the DPG consultant advises. ⚠ No lawyer reviews it, and the document must
> say so.** The recommendation split this deliberately: engineering delivers the diagram and inventory,
> *legal* delivers the Act assessment. What is actually planned is a technical inventory plus a legal opinion
> **nobody qualified has given** — the DPG consultant is not the agency's counsel. That is a reasonable first
> pass and a real limitation. `privacy-assessment.md` **carries an honesty marker naming who wrote it and who
> has not reviewed it** (engineering rule 9). Without that marker the document reads as legal clearance,
> which is the one thing it is not.
>
> **3. T2 is parked (Q-03/Q-05), and this makes the assessment *harder*, not easier.** The old framing had
> cross-border transfer as a **transitional** exposure ending at T2. It does not end: **T1 — a hosted
> third-party provider — is now the steady state.** So the cross-border position has to be argued for an
> indefinite arrangement, and the third-party-PII question (step 3) becomes the load-bearing one. **The
> jurisdiction question (Q-03) is moot until T2 is unparked** — do not spend the assessment on it.

### Steps

1. **Data-flow diagram.** What data, collected where, transmitted to whom, stored where, retained how
   long, deleted when. It must cover, at minimum, every leg this system actually has:

   | Leg | Carries |
   |---|---|
   | Complainant → webchat (`channels/REST_webchat`) | Free-text narrative, voice notes, attachments, contact fields |
   | Webchat → orchestrator → `public.grievances` / `public.complainants` | Same, contact fields encrypted at rest (pgcrypto, `ENCRYPTED_FIELDS`) |
   | Orchestrator → Celery → **Redis** | Task payloads containing `grievance_description` — **see DPG-30/34, this is an unredacted store today** |
   | Celery → **the model provider** (6 call sites) | Raw narrative, contact strings, audio files. ⚠ **Indefinite, not transitional** — T2 is parked (Q-03/Q-05) and production moves to a *hosted open-weights* provider (Q-04), so this leg is permanent and the provider changes rather than disappears |
   | Ticketing Celery → **OpenAI** (3 call sites) | Ticket summary, officer notes, field reports |
   | Chatbot → ticketing webhook | `POST /api/v1/tickets` |
   | Ticketing → `GET /api/grievance/{id}` | Plaintext PII, server-side decrypted (T3-04), authenticated + audited (T3-06) |
   | Ticketing → orchestrator `POST /message` | Officer replies to complainant |
   | Ticketing → Messaging API | SMS via AWS SNS (international), email via SMTP relay |
   | Reports | XLSX export, PDF closure documents |
   | Backups | Destination and jurisdiction — **name them; DPG-30 verifies** |
   | Auth | Keycloak realm, officer identities |

2. **Assess against Nepal's Individual Privacy Act 2018** — the sole benchmark (Q-08; there are no agency
   data-sharing terms to measure against). Produce, explicitly: lawful basis, cross-border transfer
   position **for an indefinite third-party arrangement, not a transitional one**, retention schedule,
   deletion procedure, breach procedure, data-subject rights handling.

   > ⚠ **Get the trigger right, because it is easy to assess the wrong event.** The transfer question is
   > **not** "does the provider train on it" or "does the provider keep it". **Transmitting personal data
   > to a third party is itself a disclosure and a cross-border transfer**, and needs a lawful basis
   > whether the recipient stores it for a month or discards it in a microsecond. The provider's
   > no-retention commitment is a **mitigation to be cited**, not an answer to be relied on.
   >
   > **And openness is a licensing property, not a privacy one.** Running open weights answers indicator 4
   > and changes nothing here: an open model served by a third party has the same data flow as a
   > commercial one.
   >
   > **Legs the diagram must carry that are easy to miss** — the provider's own retention (commonly ~30
   > days for abuse monitoring and billing, some reserving service-improvement use absent an opt-out); the
   > **jurisdiction of execution**, which is not controlled even with a pinned provider; **prompt
   > caching**, which several providers use and which parks content somewhere briefly; and the
   > **re-identification mapping**, which is personal data in its own right and whose in-country residency
   > is what the "only pseudonymised text crosses the border" claim rests on
   > ([`04` DPG-31](04-pii-redaction-spec.md#dpg-31)).
   >
   > ⚠ **Terminology.** The output is **pseudonymised, not anonymised** — we hold the key, so it remains
   > personal data. Do not let the assessment or any briefing to the ministry say "anonymised".
3. **The third-party PII question must be answered here, not deferred to Sprint 3.** A road-sector
   grievance names the site engineer, the contractor, the ward official. Those people never consented.
   The complainant consented to give *their* details; nobody asked the engineer whose conduct is
   described. This is a different legal category from complainant PII, and it is what makes Sprint 3
   mandatory rather than nice-to-have. State the position.
4. Write `docs/dpg/privacy-assessment.md`. Cross-link from `docs/deployment/13_security.md`.

### Acceptance

- [x] `docs/dpg/privacy-assessment.md` written, covering every leg in the table above — **13 legs, each verified
      at a file and line on 2026-08-18**, plus three the spec's table did not list (§2.3: application logs, the Celery
      result backend, the staging environment)
- [x] **An honesty marker at the top naming the author (an AI agent), the reviewer (the DPG consultant), and
      the fact that no qualified legal review has been performed** (Q-07). Non-negotiable — see rule 9 → §0.1, which also
      marks every statutory section reference `[§ unverified]` rather than implying the numbering was checked
- [x] Individual Privacy Act 2018 position stated, including cross-border transfer **as an indefinite
      arrangement** (T1 is the steady state; T2 is parked) → §3.7
- [x] Third-party PII position stated explicitly — with T2 parked this is the **load-bearing** section → §4.
      ⚠ **Corrected 2026-08-18 after the owner flagged it:** the first draft said person names go unredacted until the
      ML layer lands. **That repeats sprint deviation D-08's error** — §31.2b ships three deterministic person-name
      recognisers (title triggers, thar gazetteer, self-identification), and in this domain they catch the case that
      matters most, the named official. The honest claim is *most names removed, residual measured and published*
- [x] The transfer analysis is framed on **transmission**, not on provider retention or training use, with
      the provider's commitments cited as mitigation → **§3.7.1**, which also states the two corollaries a reader
      reaches for and should not (openness is a licensing property; a no-retention commitment does not un-make a
      transfer), and carries the four easy-to-miss legs: provider retention, **jurisdiction of execution**, prompt
      caching, and the **re-identification mapping**. The first three are recorded as `⚠ Unverified` findings
      (**F-16**, **F-17**) rather than asserted
- [x] The word **"anonymised" appears nowhere** describing model-bound text; pseudonymisation, with the
      reason, and the key's residency stated as the safeguard it is → **§3.7.2**, which states the reason (*we hold
      the key*), the consequence (*it remains personal data; every §3 obligation still applies*), and disambiguates
      the separate, correct use of "anonymous" for a complainant withholding their identity at intake
- [x] Retention, deletion, and breach procedures written (or marked `⚠ Not built` where they are not) → §5.
      **All three are gaps.** Archiving is implemented and is **not** deletion; no code path deletes personal data anywhere
- [x] Q-03 (jurisdiction) explicitly marked **moot while T2 is parked**, with the analysis kept for unparking → §0.4
- [x] `docs/deployment/13_security.md` cross-links it → §15, with a callout naming the findings it does not cover

### ⚠ Three findings the ticket did not anticipate

Reading the code to build the diagram surfaced three privacy defects **no spec had**, all logged as
deviation **D-19** and registered in the assessment's §6:

| | Finding | Where |
|---|---|---|
| **F-2** | **Encryption at rest fails open** — `_encrypt_field` returns the plaintext value unchanged when `DB_ENCRYPTION_KEY` is unset *and* when the pgcrypto call raises. The error is logged; the write proceeds | `base_manager.py:243-252` |
| **F-3** | **Unsalted SHA-256** of phone/email/name/address stored as search tokens. Nepal's mobile number space is enumerable, so the phone hash is reversible — these are personal data, not pseudonyms | `base_manager.py:502-511` |
| **F-4** | **Backups unencrypted by default** — `pg_dump` + uploads tar; GPG/passphrase only if an env var is set. Contact columns stay ciphertext; the narrative, officer notes, voice notes and photos do not | `backup_db.sh:45-60` |

The ticket's framing anticipated the *known* exposure (model-provider egress). These are ordinary
engineering defects in the storage layer, and they are the reason the diagram had to be built from the
code rather than from the existing privacy specs.

**One correction to the ticket's own leg table:** it lists *"Ticketing → Messaging API | SMS via AWS SNS
(international)"*. **Production Nepal does not use SNS** — `backend/config/sms_config.py:48` selects the
**DOIT government gateway** (`sms.doit.gov.np`), in-country. SNS (`ap-southeast-1`, Singapore) is the
dev/international fallback. That makes the leg *better* than the spec assumed on the production path and
adds a cross-border fallback nobody had inventoried (**F-12**).

### Tests

None directly. But DPG-30 (Sprint 3) **verifies this diagram against the code** and reports every leg
the diagram missed. A data-flow diagram nobody checked against reality is a compliance artefact, not a
control.

### ✅ Questions — answered

- **Q-03** — ✅ **moot for now: T2 is parked.** Keep the Mumbai/Singapore analysis for unparking; do not
  spend this assessment resolving it.
- **Q-07** — ✅ **agent drafts, consultant advises, no legal review** — and the document must disclose that.
- **Q-08** — ✅ **Nepal's Individual Privacy Act 2018 is the benchmark**; no existing agreement exists.

---

## DPG-05 — Open-source project hygiene (indicator 8) {#dpg-05}

**Added 2026-08-17 after the compliance audit** ([`00_compliance_status.md`](../../dpg/00_compliance_status.md) §3.4).
No ticket covered this. Verified absent at the repo root: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
`SECURITY.md`, `.github/ISSUE_TEMPLATE/`. (`LICENSE` / `NOTICE` are DPG-01's, not this ticket's.)

Indicator 8 is otherwise **🟢 mostly compliant** — OpenAPI on both surfaces, OIDC/PKCE, Alembic-migrated
schema, architectural invariants pinned by tests. These files are the whole remaining gap, and they are
all cheap.

### ⚠ One of them is not boilerplate

`SECURITY.md` matters more here than in a typical repo: this system holds **SEAH disclosures**. A
vulnerability-disclosure route that tells a finder to open a public GitHub issue is the wrong answer for a
platform where the worst-case bug exposes harassment reports. It needs a **private** channel, a named
recipient, and a stated response window — and it should say what is in scope (the platform) and what is
not (the grievances themselves; a researcher must not go fishing in production data).

### Steps

1. `SECURITY.md` — private disclosure channel, named recipient, response window, in/out of scope. Write
   this one first and do not template it.
2. `CONTRIBUTING.md` — how to build (point at [`DOCKER.md`](../../deployment/DOCKER.md), do not restate
   it), the branch rule (never `main` — CLAUDE.md §Git workflow), the engineering rules
   ([`00_engineering_index.md`](../../engineering/00_engineering_index.md)), and the tests-in-the-same-commit
   expectation. A contributing guide that contradicts CLAUDE.md is worse than none.
3. `CODE_OF_CONDUCT.md` — Contributor Covenant 2.1 with a real enforcement contact.
4. `.github/ISSUE_TEMPLATE/` + PR template — bug / feature / security-redirect. The security template must
   route to `SECURITY.md`, not collect a report in public.
5. A public roadmap — the DPG sprint plan is already written; link it rather than authoring a second one.

### ❓ Scope gate — do not over-build

Which of these the DPGA **requires** versus merely likes is a live question with the consultant (its Q10),
along with release tags, versioning and a governance model. ⭐ **Recommendation: ship 1–4 now regardless** —
they are hours of work, they are uncontroversial, and `SECURITY.md` is worth having for its own sake.
**Defer the governance model and a release/versioning policy** until the answer lands; those carry real
process commitments. Log the deferral per the standing rule.

### Acceptance

- [x] `SECURITY.md` with a **private** channel (`contact@grm-chatbot-nepal.org`), named recipient, response window
      (3 working days to acknowledge, 10 to assess, 90-day coordinated disclosure), and scope boundaries — including an
      explicit **out of scope: real grievance data, in any environment**, and a *known and accepted* list so a researcher
      does not re-report the model-egress gap we have already published
- [x] `CONTRIBUTING.md` consistent with CLAUDE.md and `docs/engineering/` — no contradictions, no restated build steps.
      It says so outright: *"This file points at the rules; it does not restate them"*
- [x] `CODE_OF_CONDUCT.md` with a real enforcement contact — Contributor Covenant 2.1, plus one project-specific clause:
      disclosing the contents or subjects of a real grievance in any public channel is a serious violation, independent of intent
- [x] Issue + PR templates present; the security path does **not** land in a public issue — `blank_issues_enabled: false`
      plus a `contact_links` **redirect** to `SECURITY.md`, so there is no route by which a security report becomes public
- [x] Roadmap links the existing sprint plan (root `README.md` §Contributing, `CONTRIBUTING.md` §Roadmap) — no second roadmap authored
- [x] Governance / versioning explicitly deferred with the consultant question referenced → deviation **D-08**,
      [`followups/governance-and-versioning-policy.md`](followups/governance-and-versioning-policy.md), `TODO.md` row

> ⚠ **The contact address is a placeholder** chosen by the project owner. `SECURITY.md` and `CODE_OF_CONDUCT.md` both
> say so in the file rather than publishing a silently dead address. **The mailbox must be live before the repository
> is published** — that is the one open item in this ticket.

### Tests

None (documents). The SPDX walker (T-01) does not apply — these are root markdown files.

---

## DPG-06 — The repo front door contradicts the submission {#dpg-06}

**Added 2026-08-17 after the compliance audit** ([`00_compliance_status.md`](../../dpg/00_compliance_status.md) §3.3,
which understates it). This is small, and it is **the first thing a DPG reviewer reads.**

The root `README.md` describes a system that does not exist, and the specific fiction it describes is the
one the submission's central indicator-2 argument denies:

| `README.md` | Reality | Why it matters |
|---|---|---|
| `:6` — intake is "**Rasa + FastAPI**" | Hand-rolled FastAPI state machine; `rasa-sdk` survives as a type shim | §2.2 of the compliance doc argues *"There is no Rasa server and no TensorFlow"* as a licence-risk answer |
| `:46-47` — a service table row **"Rasa \| Rasa 3 \| 5005 \| NLU + dialogue"**, plus an "Action Server" on 5055 | No such service in `docker-compose.yml` or `docker-compose.grm.yml` | A reviewer reading a **port number** does not treat it as a stale adjective. It reads as a deployed component |
| `:60`, `:76`, `:116` — `rasa_chatbot/` in the folder tree, "Rasa custom actions" | No `rasa_chatbot/` directory | Same stale listing CLAUDE.md carries (§0 above) |
| `:10` — "**Active branch:** `feature/grm-ticketing`" | `integration/stage` | Tells a stranger to check out a branch that is not current |

**The failure mode is precise:** the submission says "no Rasa"; the repo's front page says "Rasa 3, port
5005, NLU + dialogue". A reviewer who spots that stops trusting the licence section — which is the section
this sprint exists to make true. It is engineering rule 9 (never write an unverified doc claim) on the most
visible file in the repository.

### Steps

1. Rewrite the stack table from the **compose files**, not from memory. Eleven services; name them as they
   are. `rasa-sdk`'s real role — `Tracker` / `CollectingDispatcher` types for the hand-rolled orchestrator —
   stated in one accurate line.
2. Drop `rasa_chatbot/` from the folder tree; reconcile the tree with what is on disk.
3. `integration/stage` as the current branch, with the `main` rule (CLAUDE.md §Git workflow).
4. Fix the same stale `rasa_chatbot/` row in **CLAUDE.md** §Folder structure — spec §0 flags it and no
   ticket owns it either.
5. Land DPG-01's Licence section and DPG-24's CI badge in the same file; coordinate so they do not conflict.

### Acceptance

- [x] No claim in `README.md` that a `grep` of the compose files contradicts — **checked, not assumed.** The service
      table was generated from `docker compose config --services` and the port map cross-checked against `DOCKER.md`
- [x] The Rasa service and Action Server rows gone; `rasa-sdk`'s type-shim role stated accurately — it supplies
      `Tracker` / `CollectingDispatcher` / `DomainDict` and the `SlotSet` / `FollowupAction` event helpers to **49 files**
      under `backend/actions/`, invoked **in-process** at `backend/orchestrator/action_registry.py:285`, not over a webhook
- [x] Folder tree matches disk; `rasa_chatbot/` removed from `README.md` **and** CLAUDE.md (§Service boundaries — closes **P-13**).
      Verified: `grep -rn rasa CLAUDE.md` returns nothing
- [x] Current branch correct — `integration/stage`, with the `main`-is-integration-only rule
- [x] Consistent with `00_compliance_status.md` §2.2 — both now say there is no Rasa server, and the README explains
      *why the row is gone* rather than silently deleting it, so a reader who remembers the old table is not left guessing

### ⚠ Two corrections to this ticket's own text

1. **"Eleven services" is wrong.** `docker compose config --services` returns **13**, plus 2 profile-gated
   (`db_init` under `init`, `keycloak` under `auth`) = **15 defined**. The README says 13 + 2 and shows both.
2. **The four-row table above missed a fifth fiction: the Environments table.** All three URLs it listed
   (`chatbot.facets-ai.com`, `grm.facets-ai.com`, `grm.stage.facets-ai.com`) appear **nowhere else in the repository**
   and are not a `server_name` in any nginx config. The real hosts are `nepal-gms-chatbot.facets-ai.com` (AWS staging)
   and `grm-chatbot.dor.gov.np` (DOR production). **A reviewer clicking a dead production URL on the front page is the
   same failure as the Rasa row, one click earlier.** Logged as deviation **D-17**.

### Tests

`docs-links` (existing CI gate) covers link rot only. The claim-versus-code check here is manual —
**do it before the consultant meeting**, not after.

---

## Definition of done — Sprint 0

**Closed 2026-08-18 with one box unticked, and it is the one nobody here can tick.** Per-item evidence
is in [`PROGRESS.md`](PROGRESS.md#sprint-0--definition-of-done).

- [x] DPG-01, DPG-02, **DPG-05, DPG-06** landed and green in CI
- [ ] DPG-03 request **sent** — ⏸ **not sent to ADB OGC.** Named as a blocker with its clock in
      [`PROGRESS.md`](PROGRESS.md), per DPG-01's acceptance rule that an outstanding external answer is
      *named with the date it was raised*, not left as an unticked box. It is left unticked as well,
      because it is genuinely not done
- [x] DPG-04 written, or explicitly re-scoped with a named author and date in `PROGRESS.md`
- [x] `README.md` and CLAUDE.md make the **same** claim about Rasa as the compliance briefing (DPG-06)
- [x] `docs/dpg/` exists and is indexed from `docs/README.md` — four files, each with its own row
- [x] Evidence-pack rows 2, 3, 7, 9a in
      [`00-dpg-context-and-decisions.md`](00-dpg-context-and-decisions.md#4-dpg-evidence-pack) point at real files
      — 2, 7 and 9a do (rows 5 and 8 were updated too). **Row 3 still has no file and cannot have one until ADB OGC
      responds**; it names the blocker instead of a placeholder
- [x] Every deferral logged in `followups/` + `TODO.md`, same commit — two followups created. ⚠ One stated
      exception: D-19's three new privacy findings live in the assessment's findings register with owners, not in
      `followups/` — they are findings awaiting a ticket, not deferrals of scoped work
