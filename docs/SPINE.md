# The register — what is next

**Status:** authoritative (2026-09-04). **The single answer to "what is next."** If another document
appears to answer it too, that document is wrong — say so and fix it.
**Last updated:** 2026-09-04 — created (OM-02). Seeded from `sprints/README.md`, the four live sprint
trackers, and the open rows of `TODO.md`, which is now retired behind a forwarding note.
**Audience:** internal — excluded from the public repository (lifecycle §10.4).
**Governed by:** [`engineering/07_work_items.md`](engineering/07_work_items.md) — kinds, the four-question
triage test, the nine gates, the six profiles, definition of ready, and the two state fields.

---

## How to read this

**Four sections, and they mean different things.**

| Section | Holds | Rule |
|---|---|---|
| **Current** | The one item in flight per lane | [07](engineering/07_work_items.md) §7.3 — one `current` **per lane**, not per project |
| **Register** | Items that are **ready**: someone could start today | §6.1 — every row is actionable, or it does not belong here |
| **Backlog** | Proposed items. Not ready, not forgotten | The interim inbox until a tracker is wired (OM-07) |
| **Done** | Closed this quarter, then archived | Q-06 |

**Two state fields, never one** (§7.1). `state` says where it is in the queue
(`proposed → ready → current → merged → done`, plus `blocked` / `dropped`). `verification` says how
true it is (`planned → implemented → tested → applied locally → deployed → verified in production`).
An item is `done` only when its verification level meets what its profile requires (§7.2).

**IDs.** New items take the next `GRM-###` — **the file is the allocator** (Q-07): take the next
number, and let git surface a double-claim as a merge conflict, which is the behaviour we want.
**Historical prefixes are never renumbered** (§8.2): `OM-`, `QA-`, `HR-`, `DPG-`, `T3-`, `H2-`, `SH-`,
`TP-`, `CL-` keep their identity and are cited across the tree.

⚠ **`GRM-067` is the next free id.** (`GRM-065` and `GRM-066` were opened 2026-09-04.)

---

## Open security findings

⭐ **This section exists because a `+SENSITIVE` row buried in a backlog reads as less urgent than it
is.** Severity is a field here, not a marker inside prose, so *"how many open high-severity findings"*
is answerable without a grep — a question ADB and a DPG assessor both ask.
Full list, including the low-severity ones: § *Backlog → Carrying `+SENSITIVE`*.

| Id | Severity | Item | State | Note |
|---|---|---|---|---|
| `GRM-065` | 🔴 **high** | **The orchestrator's port is published on every deployed host, and the only control left is a firewall nobody has checked** | `ready` | ⚠ **Neither `GRM-013` nor `GRM-014` says this alone — it is their product.** Verified 2026-09-04: [`docker-compose.grm.yml:120-122`](../docker-compose.grm.yml) publishes `"8000:8000"` with **no `127.0.0.1:` bind prefix**, its own comment saying *"expose 8000 for local testing"*; and **every deploy stack includes `grm.yml`** — `COMPOSE_AWS` and the prod path both use `-f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml`, with neither overlay overriding `ports`. **First action is a measurement, not a fix:** `curl` `:8000` from outside the DOR host |
| `GRM-014` | 🔴 **high** | Orchestrator `:8000` has no auth | `ready` | `backend/orchestrator/main.py:102`. The half of `GRM-065` that a firewall cannot fix |
| `GRM-013` | 🔴 **high** | DOR prod firewall for `:5001` is **unverified** | `ready` | Minutes to check, and it is the other half of `GRM-065` |
| `GRM-001` | 🔴 **high** | `next@16.2.6` ships nine advisories in the officer portal | `ready` | Middleware/proxy bypass in App Router · SSRF in Server Actions · SSRF in rewrites · unauthenticated disclosure of internal Server Function endpoints. **Ships.** ⭐ Chore-shaped, `+SENSITIVE` by blast radius (§4.2) |
| `GRM-008` | 🔴 high | A routine `make aws-deploy` took staging off the network for ~40 min | `ready` | **Owned by [QA-01](sprints/2026-09_qa_automation/01-QA-01-deploy-safety.md)** — not loose |
| `GRM-006` `GRM-007` `GRM-009` `GRM-010` | 🟠 med ×4 | ops selfcheck on deploy · `AWS_DEPLOY_SERVICES` omits the orchestrator · `ops` password fallback should be fatal · Keycloak event storage on DOR prod | `proposed` | Backlog |
| `GRM-002` `GRM-003` `GRM-004` `GRM-011` | 🟡🔵 low ×4 | See the backlog table | `proposed` | Backlog |

⚠ **Four `🔴 high` findings are `ready` and unassigned.** Three of them (`GRM-065`, `GRM-014`,
`GRM-013`) are one connected question about the production host, and the first action on all three is
**a measurement, not a fix.**

---

## Current

| Lane | Item | Kind | Profile | State | Verification |
|---|---|---|---|---|---|
| operating-model | **OM-02** — the register | feature | backend-feature −DATA/CONTRACT | `current` | `implemented` |
| *(all others)* | — | | | | *no lane has a second `current`* |

---

## Register — ready

Items someone could pick up today. Sprint tickets keep their own IDs and link to their specs.

| Item | Kind | Profile | State | Size | Lane | Notes |
|---|---|---|---|---|---|---|
| [OM-03](sprints/2026-09_operating_model/03-OM-03-register-test.md) — `tests/repo/test_spine.py` | feature | chore+TEST | `ready` | S | operating-model | ⭐ **Not optional.** Without it every rule in `07` is a preference |
| [OM-04](sprints/2026-09_operating_model/04-OM-04-sensitive-path-at-intake.md) — sensitive-path question at intake | feature | chore+SPEC | `ready` | S | operating-model | The PR checklist already exists; it moves |
| [OM-05](sprints/2026-09_operating_model/05-OM-05-product-and-roadmap.md) — `PRODUCT.md` + `ROADMAP.md` | feature | chore+SPEC | `ready` | M | operating-model | Mostly assembly |
| [OM-06](sprints/2026-09_operating_model/06-OM-06-standard-amendments.md) — four standard amendments | feature | chore+SPEC | `ready` | M | operating-model | Packs · design gate · verification ladder · session close |
| [OM-09](sprints/2026-09_operating_model/09-OM-09-release-and-versioning.md) — release + versioning | feature | chore+SPEC+RELEASE | `ready` | M | operating-model | A tag is cut on production deploy ([D-009](DECISIONS.md)) |
| [OM-07](sprints/2026-09_operating_model/07-OM-07-intake-and-tracker.md) — unify intake, wire the tracker | feature | backend-feature −DATA | `blocked` | M | operating-model | **Blocker:** OM-02. Ungated otherwise — repo is private |
| [OM-08](sprints/2026-09_operating_model/08-OM-08-starter-kit-extraction.md) — starter-kit extraction | feature | chore+SPEC | `blocked` | S | operating-model | **Blocker:** OM-01…OM-06. Last by design |
| [QA-01](sprints/2026-09_qa_automation/01-QA-01-deploy-safety.md) — stop the next deploy being an outage | feature | backend-feature | `ready` | S | qa *(sprint not approved)* | ½ d · from the 2026-09-04 deploy outage |
| [QA-02](sprints/2026-09_qa_automation/02-QA-02-ci-built-images.md) — CI-built images | feature | backend-feature+RELEASE | `ready` | L | qa *(not approved)* | ⚠ **Q-01 must be re-decided** — its GHCR premise inverted when the repo went private |
| [QA-03](sprints/2026-09_qa_automation/03-QA-03-stack-isolation.md) — `COMPOSE_PROJECT_NAME` + ports | feature | chore | `blocked` | S | qa *(not approved)* | **Blocker:** QA-02 |
| [QA-04](sprints/2026-09_qa_automation/04-QA-04-browser-harness.md) — Playwright harness + coverage | feature | chore+TEST | `ready` | L | qa *(not approved)* | ⚠ 04c needs a flow inventory that does not exist |
| [QA-05](sprints/2026-09_qa_automation/05-QA-05-ci-gate-and-coverage.md) — run it in CI | feature | chore+TEST | `blocked` | M | qa *(not approved)* | **Blockers:** QA-02, QA-03, QA-04; and its own Q-16 |
| `GRM-065` — the orchestrator port is published on every deployed host | deviation | chore+SENSITIVE | `ready` | S | standing | 🔴 **First action is a measurement:** `curl` `:8000` from outside the DOR host. The fork is which side moves — close the port, or document the exposure and rely on the firewall |
| `GRM-014` — orchestrator `:8000` has no auth | deviation | backend-feature+SENSITIVE | `ready` | M | standing | 🔴 The half of `GRM-065` a firewall cannot fix. `backend/orchestrator/main.py:102` |
| `GRM-013` — DOR prod firewall for `:5001` unverified | chore | chore+SENSITIVE | `ready` | XS | standing | 🔴 Minutes. ⭐ **A chore with a register row** — §1.2, because `+SENSITIVE` is never waived (§4.2) |
| `GRM-066` — `dpg/02_questions.md` has drifted from the source it is generated from | bug | chore+TEST | `ready` | XS | standing | Found 2026-09-04 while running the full `tests/repo` suite for OM-03. `test_dpg_questions_generated` is **red at the session's starting commit** with `docs/dpg/` untouched — so it is pre-existing, not caused by this sprint. ⭐ **It is a bug, not debt:** the generator's own pinning test says the two must agree, and they do not. Fix is `python scripts/ops/gen_dpg_questions.py`, then read the diff before committing — the drift is the finding |
| `GRM-001` — bump `next` off 16.2.6 | chore | chore+SENSITIVE | `ready` | S | standing | 🔴 Nine advisories, ships. Chore-shaped, Opus-and-boundary-tests by blast radius |
| **HR-05** — prove a red build blocks | bug | chore+TEST | `ready` | XS | hardening | ⭐ **Five minutes.** The ruleset is active; nobody has watched it refuse a merge ([17](deployment/17_manual_browser_sweep.md)) |
| **HR-07** — manual browser sweep | chore | chore+VERIFY | `ready` | M | hardening | [`deployment/17_manual_browser_sweep.md`](deployment/17_manual_browser_sweep.md) · 60–75 min · ⚠ read its warning first |
| **DPG sprint** — `2026-08-llm` | feature | mixed | `current` *(own lane)* | XL | dpg | 27 tickets, in progress — [tracker](sprints/2026-08-llm/PROGRESS.md). ⚠ **XL means split**, and it is already split into four sub-sprints |
| **Review feedback loop** | feature | UI feature | `proposed` | L | — | [DESIGN](sprints/2026-09_review_feedback_loop/DESIGN-review-feedback-loop.md) · its D1 is settled by [D-010](DECISIONS.md); OM-07 owns the vocabulary |
| **Public repo split** | feature | chore+RELEASE | `proposed` | M | — | Prune list · the 17-file infrastructure-identifier scrub · history decision. Gated on [D-009](DECISIONS.md) |

---

## Backlog — proposed

**Not ready, not forgotten.** Absorbed from `TODO.md` on 2026-09-04 (Q-03). ⚠ **These rows were given
an id and a home, not a classification** — every title is preserved **verbatim**, including its own
status marker. Per [07 §11.9](engineering/07_work_items.md) and Q-05, an item's kind, profile and
state are confirmed **when it is scheduled**, not in a big-bang pass. Several rows below are marked
done in their own text; those resolve as they are picked up.

### Carrying `+SENSITIVE` — PII · auth · SEAH · complainant channel · egress

⚠ §4.2: **the modifier is never waived by kind or by size.** A one-line fix on any of these is not a chore.

| Id | Severity | Kind | Profile | Item | Where |
|---|---|---|---|---|---|
| `GRM-002` | 🟡 low | debt | **+SENSITIVE** | 🟡 **The officer's category correction overwrites the AI's answer with no record of what it proposed** | `ticketing/api/routers/tickets/crud.py:523` · `backend/services/database_services/grievance_manager.py:83`  |
| `GRM-003` | 🟡 low | debt | **+SENSITIVE** | 🟡 **The SEAH detector's confidence is computed on every call and thrown away** | `backend/services/LLM_services.py:633` · `backend/actions/grievance_intake/sensitive.py:103` · `ticketing/models/ticket.py:94`  |
| `GRM-004` | ⏳ stale | debt | **+SENSITIVE** | ⏳ **The classification benchmark has not been re-run since the D-51 storage guard** | `scripts/ops/llm_benchmark.py` · [`docs/dpg/model-benchmarks.md`](dpg/model-benchmarks.md) §3.1  |
| `GRM-006` | 🟠 med | debt | **+SENSITIVE** | 🟠 **The deploy should run `ops.selfcheck`, not trust a runbook** | `Makefile` (`REMOTE_DEPLOY_CORE`)  |
| `GRM-007` | 🟠 med | debt | **+SENSITIVE** | 🟠 **`AWS_DEPLOY_SERVICES` omits the orchestrator, which is what executes `backend/actions/`** | `Makefile:88` (`AWS_DEPLOY_SERVICES`) · `REMOTE_VERIFY_GRM_PORTS`  |
| `GRM-008` | 🔴 high | debt | **+SENSITIVE** | 🔴 **A routine `make aws-deploy` took staging OFF THE NETWORK for ~40 minutes — the box has 4 GB and no swap, and builds the Next.js image on itself** | `Makefile` (`REMOTE_DEPLOY_CORE` → `build --pull`) · EC2 `i-07e144c2f6d9db18e` (`t4g.medium`, 2 vCPU / 3825 MB / **swap 0**)  |
| `GRM-009` | 🟠 med | debt | **+SENSITIVE** | 🟠 **`ops/config.py`'s password fallback should be fatal, not a warning** | `ops/config.py:104-118`  |
| `GRM-010` | — unset | debt | **+SENSITIVE** | **Keycloak event storage** — ✅ **local 2026-08-24, STAGING 2026-09-03**; ⛔ **DOR production still OFF** | `ticketing/auth/keycloak_setup.py` (`setup_realm_event_logging`)  |
| `GRM-011` | 🔵 info | debt | **+SENSITIVE** | 🔵 **`NEXT_PUBLIC_OIDC_CLIENT_ID` holds the CONFIDENTIAL client, and the name says the opposite** | `docker-compose.grm.yml:322` · `channels/ticketing-ui/lib/auth/runtime-config.ts:22` · `channels/ticketing-ui/Dockerfile:25`  |
| `GRM-012` | — unset | debt | **+SENSITIVE** | **Breach procedure: B1/B2/B3 have no DOR owner** | [`deployment/19_incident_response.md`](deployment/19_incident_response.md) §0  |

### Debt

| Id | Kind | Profile | Item | Where |
|---|---|---|---|---|
| `GRM-015` | debt | — | 🔵 **Encrypt the original narrative and work from the redacted one — reveal by case type, not by frequency** | [`docs/sprints/2026-08-llm/04-pii-redaction-spec.md`](sprints/2026-08-llm/04-pii-redaction-spec.md) · `backend/services/pii_ser… |
| `GRM-016` | debt | — | 🟡 **The grievance taxonomy is authored in two files — and the copy that seeds every database is not the one anybody edits** | [`ticketing/constants/grievance_categories_default.json`](../ticketing/constants/grievance_categories_default.json) · [`backend… |
| `GRM-017` | debt | — | 🔴 **A shortlisted open model refuses grievances about harm to children — and the filter may be the provider's, not the model's** | `scripts/ops/llm_candidates.json` · `docs/dpg/open-model-configuration.md` |
| `GRM-018` | debt | — | ⏸ **The end-to-end test against a live vLLM endpoint is deferred — it is the step that turns "documented" into "demonstrated"** | `docs/dpg/vllm-deployment.md` |
| `GRM-019` | debt | — | 🔵 **A Nepali ASR fine-tune on OpenSLR SLR54 would be a genuine DPG *contribution*, not just a dependency** | — (research task, no code) |
| `GRM-020` | debt | — | 🔴 **`.env.open`'s ASR endpoint does not exist — the committed open configuration cannot transcribe** | [`.env.open`](../.env.open) · `docs/dpg/open-model-configuration.md` |
| `GRM-021` | debt | — | 🟡 **The SEAH detector flags gendered complaints that are not harassment — ⭐ REFRAMED 2026-08-24: this is intentional, and the gap is the return path** | `backend/services/LLM_services.py:625` (the detection prompt) |
| `GRM-022` | debt | — | ⏸ **The Hugging Face account has no inference credit — the measurement half of Sprint 2 is blocked on a purchase, not on code** | `env.local` (`HG_TOKEN`) · `scripts/ops/llm_smoke.py` |
| `GRM-023` | debt | — | 🟠 **The stored grievance summary carries no names** ✅ **DECIDED by the owner 2026-08-27** | `ticketing/models/ticket.py:59` · `ticketing/api/routers/tickets/crud.py:341` · `ticketing/services/report_rows.py:459` · Sprin… |
| `GRM-024` | debt | — | 🔵 **The OTP-expired message says "invalid code" — accurate in effect, imprecise about why** | `backend/actions/utils/utterance_mapping_rasa.py` (`action_ask_otp_input` utterance 6) · `backend/actions/forms/form_otp.py:390` |
| `GRM-025` | debt | — | 🟡 **A credential is written to the application log — and the OTP has no expiry at all** | `backend/actions/forms/form_otp.py:312`, `:343`, `:121`, `:352-364` · `backend/actions/services/otp/verification.py` · `form_st… |
| `GRM-026` | debt | — | 🟠 **Nothing re-drives a classification that never ran — grievances can sit at `pending` forever** | `backend/task_queue/celery_app.py` (no `beat_schedule`) · `backend/config/database_tables.py:41` |
| `GRM-027` | debt | — | 🔵 **The live LLM spec never says which of the nine call sites actually run** | [`docs/services/06_llm_service.md`](services/06_llm_service.md) |
| `GRM-028` | debt | — | 🔵 **The two-minute back-fill is what makes the classification budget survivable, and the ticketing spec does not mention it** | [`docs/deployment/11_llm_pipeline_policy.md`](deployment/11_llm_pipeline_policy.md) |
| `GRM-029` | debt | — | 🟠 **Nobody has measured the one path the 30 s classification budget exists for** | `backend/actions/forms/form_otp.py:181-183` · [`deployment/17_manual_browser_sweep.md`](deployment/17_manual_browser_sweep.md) |
| `GRM-030` | debt | — | 🟠 **The benchmark set has no audio, so DPG-22 cannot measure word error rate** | `tests/data/benchmark/` |
| `GRM-031` | debt | — | ✅ **DONE 2026-08-19 — two degraded-mode terminal states that no code path reached** — `LLM_failed` after a model outage, and the closure document after an LLM failure | `backend/task_queue/registered_tasks.py` (`_persist_classification_failed_if_final`) · `ticketing/tasks/llm.py` (`generate_reso… |
| `GRM-032` | debt | — | 🟠 **Classification can take longer than the chatbot waits for it — the complainant sees "no classification" on a *successful* call** | `backend/actions/grievance_intake/classification.py` (`CLASSIFICATION_POLL_MAX_SECONDS = 20.0`) · `backend/services/LLM_service… |
| `GRM-033` | debt | — | 🟠 **The translation error path raises `UnboundLocalError`, and the one-line fix would leak the narrative into the logs** | `backend/services/LLM_services.py` · `translate_grievance_to_english_LLM` (⚠ a line number was here and rotted twice — the func… |
| `GRM-034` | debt | — | ✅ **DONE 2026-08-19 — CI was red on `integration/stage` for 10 consecutive runs (2026-08-08 → 08-17) and gated nothing** | `.github/workflows/ci.yml` · `channels/ticketing-ui/lib/useTicketThread.ts` · `tests/ticketing/test_donor_guardrail.py`, `test_… |
| `GRM-035` | debt | — | ✅ **DONE 2026-08-19 — a tracked file was rewritten on import** | `backend/task_queue/config.py` → `backend/scripts/task_queue/config.sh` |
| `GRM-036` | debt | — | 🟡 **112 backticked paths in `docs/` point at files that do not exist** | 39 distinct targets · worst: `ticketing/api/routers/tickets.py` ×22 (module → package, prose never chased) |
| `GRM-037` | debt | — | 🟠 **`ops` writes no findings at all when `OPS_DB_PASSWORD` is unset** | `ops/config.py:104-111` · `ops/migrations/versions/ops001_init.py:54-64` · `env.local` |
| `GRM-038` | debt | — | ✅ **DONE 2026-08-19 — three privacy defects in the storage layer** | `backend/services/database_services/base_manager.py:266-297`, `:559-573` · `scripts/ops/backup_db.sh:45-60` |
| `GRM-039` | debt | — | 🟠 **27 test files have never run in CI** — 21 sitting directly in `tests/` plus 6 in `tests/shared/`, including SEAH routing, complainant functions, sensitive-content detection and Q… | `.github/workflows/ci.yml:178` |
| `GRM-040` | debt | — | 🟠 **NEW FEATURE — a SEAH officer cannot explicitly return a cleared case to the standard queue** | `ticketing/engine/ticket_actions.py:561` (no action) · `ticketing/api/routers/tickets/crud.py:523` + `ticketing/services/ticket… |
| `GRM-041` | debt | — | 🟠 **Two AWS credentials remain in `secrets.enc.env` with no consumer, and the licence audit is stale** | `secrets.enc.env` (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) · `docs/dpg/dependency-licenses.md` |
| `GRM-042` | debt | — | ⏸ **Governance model + release/versioning policy deferred** (DPG indicator 8) | repo root |
| `GRM-043` | debt | — | 🟡 **Demo officer switcher one-way door — ROOT FIX LANDED 2026-07-16; C4 unblocked. Optional portal hardening remains.** | `ticketing/api/dependencies.py` (`require_admin_or_bypass`) · `ticketing/api/routers/users.py` (roster routes) |
| `GRM-044` | debt | — | Seed log message still says `PROVINCE_1` | `kl_road_standard.py:319` |
| `GRM-045` | debt | — | `_scope_candidates` calls `_location_and_ancestors` twice (branches B + C) | `workflow_engine.py` |
| `GRM-046` | debt | — | `OfficerScope` seed creates `UserRole` rows but no `OfficerScope` rows | `mock_tickets.py` |
| `GRM-047` | debt | — | Utterance `file_name` derived from module name (~200 sites) — move a class to another file and its copy silently breaks | `backend/actions/base_classes/base_mixins.py:63` |
| `GRM-048` | debt | — | `backend/actions/forms/form_story_main_route_step.py` is **entirely dead code** (79 lines, `ValidateMenuForm` + `ValidateFormStoryStep`, zero importers) | `backend/actions/forms/form_story_main_route_step.py` |
| `GRM-049` | debt | — | The grievance API has **no rate limiting** — `§6`'s "loggable, authorizable, **rate-limitable** at one place" chokepoint argument is now 2/3 true, not 3/3 | `backend/api/routers/grievance.py` |
| `GRM-050` | debt | — | `5001:5001` binds the backend API to **all host interfaces** on deployed hosts — a dev convenience applied verbatim in staging | `docker-compose.grm.yml:112-117` |
| `GRM-051` | debt | — | Voice-chunk upload sessions live in a **process-local dict** (+ local `.part` file) — the chunked protocol is stateful across requests, so every chunk must hit the same process | `backend/services/file_server_core.py:29-31`, `docker-compose.yml:48` |
| `GRM-052` | debt | — | Portal ESLint debt: 143 warnings, 0 errors (HR-05 downgraded 5 rule families to `warn` to reserve the CI error channel) | `channels/ticketing-ui/` |
| `GRM-053` | debt | — | Settings tabs have **no render smoke tests** — the portal has no DOM test harness at all | `channels/ticketing-ui/vitest.config.ts`, `package.json` |
| `GRM-054` | debt | — | `ProjectWorkflowSelect` is **dead code** (zero callers; superseded by `ProjectWorkflowsEditor`) | `channels/ticketing-ui/components/settings/workflows/ProjectWorkflowSelect.tsx` |
| `GRM-055` | debt | — | `StepCast` greys **wrong-track** roles only; the other two "why-excluded" reasons need a backend endpoint, and role labels are EN-only (`ticketing.roles` has no `_ne`) | `channels/ticketing-ui/components/settings/workflows/StepCast.tsx` · `ticketing/api/routers/users.py` · `ticketing/models/user.py` |
| `GRM-056` | debt | — | ⬜ **Purge decision: secrets in public git history — scanned, and the recommendation is NOT to purge** | `git history`, 3 branches on origin |
| `GRM-057` | debt | — | 🟠 **Dependency vulnerabilities: 34 on GitHub are against a 2-month-stale `main`; the real count on this branch is 6 Python + 4 npm-high** | `requirements*.txt`, `channels/ticketing-ui/package.json` |
| `GRM-058` | debt | — | ⬜ **Secrets migrated to SOPS + age locally; staging + DOR prod not started, and no credential rotated** | `secrets.enc.env`, `.env.shared`, `scripts/ops/gen_env_local.sh` |
| `GRM-059` | debt | — | Outstanding | Why |
| `GRM-060` | debt | — | **Scopes left where the key backed 2 slots in one workflow** | Which slot a row meant is unknowable; guessing could promote an observer to actor. They are inert (no slot uses those keys) — r… |
| `GRM-061` | debt | — | Outstanding | Why it is not done |
| `GRM-062` | debt | — | **Drop `ticketing.project_locations`** | Left in place, unread. Dropping a populated table is irreversible and belongs in its own migration — see [`followups/drop-proje… |
| `GRM-063` | debt | — | **Staffing screen wording for overlapping packages** | Packages may overlap (a bridge contract covers several road packages), so a district can have *plural* responsible officers. Th… |
| `GRM-064` | debt | — | **`ui/04` mockup is stale** | The HTML mockup still shows Locations and Packages as separate sections, and organizations inside the package card |

---

## Done — 2026 Q3

| Item | Kind | Closed | Verification |
|---|---|---|---|
| [OM-01](sprints/2026-09_operating_model/01-OM-01-work-item-standard.md) — the work-item standard | feature | 2026-09-04 | `implemented` — ⚠ the standard is adopted, **not in force**; its §11 is the gap list |
| **A-3 / HR-05 (settings half)** — branch protection | chore | 2026-09-04 | `verified` — ruleset active on `main` + `integration/*`, read back through the API. ⚠ The **proof** half is `GRM-`-less and sits in the register above |
| **D-010** — the working repository is private | chore | 2026-09-04 | `verified` — `gh repo view` → `PRIVATE` |
| `GRM-005` — the ops monitor was blind and the report had never worked | debt | 2026-08-24 | `deployed` — ⚠ absorbed from `TODO.md` already marked ✅ FIXED; **not re-verified in this pass** |

*Closed items move to `sprints/archive/` at quarter end (Q-06).*

---

## What this replaced

| Source | What happened to it |
|---|---|
| `TODO.md` | **Retired 2026-09-04.** Open rows are the Backlog above; the full file is preserved at [`sprints/archive/TODO-2026-09-04.md`](sprints/archive/TODO-2026-09-04.md). ⚠ Roughly 60 `followups/` documents say *"logged in `TODO.md`"* — **those records are historically accurate and are not being rewritten** |
| `PROGRESS.md` § *In progress / next* | Deleted (Q-04). `PROGRESS.md` keeps the build narrative and the deviations record — it answers *how did we get here*, never *what is next* |
| `sprints/README.md` status column | Still the map of sprints. Ticket-level status lives here |

⚠ **This file is not yet validated.** `tests/repo/test_spine.py` (OM-03) does not exist, so nothing
stops a duplicate id, two `current` items in one lane, or a `done` row whose verification level does
not meet its profile. **Until OM-03 lands, every rule above is a preference** — which is the failure
this project has measured twice.
