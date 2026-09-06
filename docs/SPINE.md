# The register — what is next

**Status:** authoritative (2026-09-04). **The single answer to "what is next."** If another document
appears to answer it too, that document is wrong — say so and fix it.
**Last updated:** 2026-09-06 — OM-02 + OM-03 closed, OM-04 is `current`, OM-07 unblocked; and the port measurement landed: `GRM-013` closed, `GRM-065` fixed pending
deploy, `GRM-014` reframed and downgraded, `GRM-067` + `GRM-068` opened. Created 2026-09-04 (OM-02), seeded from
`sprints/README.md`, the four live sprint trackers, and the open rows of `TODO.md`, which is now
retired behind a forwarding note.
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

⚠ **`GRM-069` is the next free id.** (`GRM-067` and `GRM-068` were opened 2026-09-06 — the port measurement and the full-suite run it triggered.)

---

## Open security findings

⭐ **This section exists because a `+SENSITIVE` row buried in a backlog reads as less urgent than it
is.** Severity is a field here, not a marker inside prose, so *"how many open high-severity findings"*
is answerable without a grep — a question ADB and a DPG assessor both ask.
Full list, including the low-severity ones: § *Backlog → Carrying `+SENSITIVE`*.

| Id | Severity | Item | State | Note |
|---|---|---|---|---|
| `GRM-065` | 🔴 **high** | **The orchestrator's port was published on every deployed host — and on staging it was reachable** | `merged` · `implemented` | ✅ **MEASURED AND FIXED 2026-09-06.** Measured 2026-09-06 from outside both hosts (egress `146.70.252.25`, read-only: no `POST` sent): DOR prod filtered on 8000/5001/5002/5433/3001/18080; **AWS staging ANSWERED on `:8000`** — the orchestrator's uvicorn direct, `/docs` rendering the interactive Swagger UI and `/openapi.json` returning `securitySchemes: NONE`. Not an unconfigured firewall: 5001/5002 were filtered on the same host, so the security group was configured and 8000 explicitly allowed. **Two fixes:** the staging SG rule was removed by the owner (re-probed closed ×3, `/message` still routing 200/405 through nginx), and [`docker-compose.grm.yml`](../docker-compose.grm.yml) now binds `127.0.0.1:` on 8000 and 5001. Nothing needed the published port — nginx reaches both by Docker service name. ⚠ **`implemented`, not `deployed`:** the compose change is true on neither host until the next deploy |
| `GRM-014` | 🟠 **med** *(was 🔴 high)* | **The public complainant endpoint's only possible controls are edge-side — and staging had none** | `ready` · `implemented` | ⭐ **REFRAMED 2026-09-06, and the old title asked for something that would break the chatbot.** `POST /message` is publicly reachable on **both** hosts through nginx on 443 (confirmed: `GET /message` → 405, routed, no session created) and **must be** — the complainant webchat calls it unauthenticated, by design. So "add auth to the orchestrator" is not implementable; the controls are rate limiting, CORS and session-id unguessability. Prod carried `limit_req`/`limit_conn` on `/message`; **staging carried none, plus `Access-Control-Allow-Origin: *`**, so any page could drive a complainant session from a visitor's browser at unlimited rate. Ported prod's zones + limits into [`webchat_rest_compose_aws.conf`](../deployment/nginx/webchat_rest_compose_aws.conf) and restricted CORS to the staging origin (`nginx -t` clean). **Left open:** session-id unguessability is unmeasured, and `backend/orchestrator/main.py:102` still declares no security scheme |
| `GRM-013` | ✅ **closed** | DOR prod firewall for `:5001` is **unverified** | `done` · `verified` | ✅ **ANSWERED 2026-09-06 — the firewall holds.** Measured 2026-09-06 from outside both hosts (egress `146.70.252.25`, read-only: no `POST` sent): 5001 filtered on DOR prod, as were 8000/5002/5433/3001/18080, with 443/80 answering from the same probe so the path was live. ⚠ **One vantage only** — a source-IP allowlist would look identical from here; this observes reachability, not the ruleset. See § *Done* |
| `GRM-001` | 🔴 **high** | `next@16.2.6` ships nine advisories in the officer portal | `ready` | Middleware/proxy bypass in App Router · SSRF in Server Actions · SSRF in rewrites · unauthenticated disclosure of internal Server Function endpoints. **Ships.** ⭐ Chore-shaped, `+SENSITIVE` by blast radius (§4.2) |
| `GRM-067` | 🟠 **med** | **Staging's nginx has drifted from prod's hardened conf, and nobody diffed them** | `ready` | ⭐ **Found 2026-09-06 while fixing `GRM-014` — by diffing the two confs, which is the check that was missing.** Beyond the rate limiting now ported: staging carries a **server-wide `add_header Access-Control-Allow-Origin * always`** ([`webchat_rest_compose_aws.conf:370`](../deployment/nginx/webchat_rest_compose_aws.conf)) that prod does not, and lacks prod's security-header block entirely — `server_tokens off`, HSTS, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`. **Deliberately not fixed in the same commit:** removing a server-wide CORS header can break an embed silently, and the approved change was the rate limiting. Needs a look at what actually embeds the staging webchat first |
| `GRM-008` | 🔴 high | A routine `make aws-deploy` took staging off the network for ~40 min | `ready` | **Owned by [QA-01](sprints/2026-09_qa_automation/01-QA-01-deploy-safety.md)** — not loose |
| `GRM-006` `GRM-007` `GRM-009` `GRM-010` | 🟠 med ×4 | ops selfcheck on deploy · `AWS_DEPLOY_SERVICES` omits the orchestrator · `ops` password fallback should be fatal · Keycloak event storage on DOR prod | `proposed` | Backlog |
| `GRM-002` `GRM-003` `GRM-004` `GRM-011` | 🟡🔵 low ×4 | See the backlog table | `proposed` | Backlog |

⚠ **The measurement was run 2026-09-06, and it moved every one of the three.** `GRM-013` closed
(prod's firewall holds), `GRM-065` was confirmed *on staging only* and is fixed pending deploy, and
`GRM-014` turned out to be **mis-specified** — it asked for auth on an endpoint that must stay public,
so it was reframed and dropped to 🟠 med. **One 🔴 high remains `ready` and unassigned: `GRM-001`**
(the `next@16.2.6` bump — recommended paired with `HR-07`, whose browser sweep is what verifies it).

⭐ **The lesson worth keeping.** Two of the three rows were wrong in *opposite* directions, and no
amount of reading the compose file would have told you which: prod was safer than the register
claimed, staging was worse, and the endpoint the register wanted to authenticate is public by
design. **The five minutes were the work.**

---

## Current

| Lane | Item | Kind | Profile | State | Verification |
|---|---|---|---|---|---|
| operating-model | **[OM-04](sprints/2026-09_operating_model/04-OM-04-sensitive-path-at-intake.md)** — sensitive-path question at intake | feature | chore+SPEC | `current` | `planned` |
| *(all others)* | — | | | | *no lane has a second `current`* |

---

## Register — ready

Items someone could pick up today. Sprint tickets keep their own IDs and link to their specs.

| Item | Kind | Profile | State | Size | Lane | Notes |
|---|---|---|---|---|---|---|
| [OM-05](sprints/2026-09_operating_model/05-OM-05-product-and-roadmap.md) — `PRODUCT.md` + `ROADMAP.md` | feature | chore+SPEC | `ready` | M | operating-model | Mostly assembly |
| [OM-06](sprints/2026-09_operating_model/06-OM-06-standard-amendments.md) — four standard amendments | feature | chore+SPEC | `ready` | M | operating-model | Packs · design gate · verification ladder · session close |
| [OM-09](sprints/2026-09_operating_model/09-OM-09-release-and-versioning.md) — release + versioning | feature | chore+SPEC+RELEASE | `ready` | M | operating-model | A tag is cut on production deploy ([D-009](DECISIONS.md)) |
| [OM-07](sprints/2026-09_operating_model/07-OM-07-intake-and-tracker.md) — unify intake, wire the tracker | feature | backend-feature −DATA | `ready` | M | operating-model | ✅ **Unblocked 2026-09-06** — its only blocker was OM-02, now done. Ungated otherwise — repo is private |
| [OM-08](sprints/2026-09_operating_model/08-OM-08-starter-kit-extraction.md) — starter-kit extraction | feature | chore+SPEC | `blocked` | S | operating-model | **Blocker:** OM-01…OM-06. Last by design |
| [QA-01](sprints/2026-09_qa_automation/01-QA-01-deploy-safety.md) — stop the next deploy being an outage | feature | backend-feature | `ready` | S | qa *(sprint not approved)* | ½ d · from the 2026-09-04 deploy outage |
| [QA-02](sprints/2026-09_qa_automation/02-QA-02-ci-built-images.md) — CI-built images | feature | backend-feature+RELEASE | `ready` | L | qa *(not approved)* | ⚠ **Q-01 must be re-decided** — its GHCR premise inverted when the repo went private |
| [QA-03](sprints/2026-09_qa_automation/03-QA-03-stack-isolation.md) — `COMPOSE_PROJECT_NAME` + ports | feature | chore | `blocked` | S | qa *(not approved)* | **Blocker:** QA-02 |
| [QA-04](sprints/2026-09_qa_automation/04-QA-04-browser-harness.md) — Playwright harness + coverage | feature | chore+TEST | `ready` | L | qa *(not approved)* | ⚠ 04c needs a flow inventory that does not exist |
| [QA-05](sprints/2026-09_qa_automation/05-QA-05-ci-gate-and-coverage.md) — run it in CI | feature | chore+TEST | `blocked` | M | qa *(not approved)* | **Blockers:** QA-02, QA-03, QA-04; and its own Q-16 |
| `GRM-065` — the orchestrator port was published on every deployed host | deviation | chore+SENSITIVE | `merged` | S | standing | ✅ Measured + fixed 2026-09-06 — staging `:8000` was open, SG rule pulled, `127.0.0.1:` bound in compose. ⚠ **Stays open until a deploy makes the compose change true on both hosts.** Detail in § *Open security findings* |
| `GRM-014` — the public complainant endpoint has only edge-side controls | deviation | backend-feature+SENSITIVE | `ready` | S *(was M)* | standing | ⭐ **Reframed 2026-09-06** — the old title ("add auth to the orchestrator") is not implementable: the webchat calls `/message` unauthenticated by design. Rate limiting + CORS ported to staging; **what remains is session-id unguessability**, which is unmeasured |
| `GRM-067` — staging nginx has drifted from prod's hardened conf | debt | chore+SENSITIVE | `ready` | S | standing | 🟠 Server-wide `Access-Control-Allow-Origin *` that prod does not carry, and none of prod's security headers (HSTS · `nosniff` · `X-Frame-Options` · `Referrer-Policy` · `server_tokens off`). ⚠ **Check what embeds the staging webchat before pulling the CORS header** |
| `GRM-068` — the doc-header gate is red on 11 commits, and it can only see a violation *after* the commit lands | bug | chore+TEST | `ready` | S | standing | ⭐ **Found 2026-09-06 running the full `tests/repo` suite; pre-existing (red at `14be2a98` with my tree stashed).** All 11 are 2026-09-04 commits that changed a spec body without bumping its header — **including `14be2a98` itself**, the commit that shipped the register's own enforcement point. ⚠ **The design gap is the finding, not the 11 rows:** `test_no_commit_changes_a_spec_body_without_touching_its_header` reads *committed history*, so the violating commit is invisible while it is being written and is discovered by the next session — which can then only fix it in a *later* commit, the very thing rule §3 forbids. A `pre-commit` or a staged-tree check is the shape that would actually hold |
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
| `GRM-050` | debt | — | ✅ **FIXED 2026-09-06 (with `GRM-065`, same one-line class of defect)** — `5001:5001` bound the backend API to **all host interfaces** on deployed hosts; now `127.0.0.1:5001:5001`. ⚠ 5001 was measured **filtered** on both hosts, so this was latent, not exposed. Pending deploy | `docker-compose.grm.yml:112-117` |
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
| [OM-03](sprints/2026-09_operating_model/03-OM-03-register-test.md) — `tests/repo/test_spine.py` | feature | 2026-09-06 | `tested` — nine checks, each proven to fail by a mutation sweep, running in CI ([`ci.yml`](../.github/workflows/ci.yml)). §7.2: a chore-profile item is done at `tested` |
| [OM-02](sprints/2026-09_operating_model/02-OM-02-the-register.md) — the register | feature | 2026-09-06 | `tested` — OM-03 is its TEST gate, and its VERIFY gate was met by use: this session read the register, acted on three of its rows, and wrote five back. ⚠ Closed the day after it was written, by its own author-lineage — a second reader has not audited it |
| `GRM-013` — DOR prod firewall for `:5001` | chore | 2026-09-06 | `verified` — 5001 filtered from outside the host (egress `146.70.252.25`), with 443/80 answering on the same probe. ⚠ **One vantage**: this observes reachability, not the ruleset — a source-IP allowlist is indistinguishable from here |
| `GRM-005` — the ops monitor was blind and the report had never worked | debt | 2026-08-24 | `deployed` — ⚠ absorbed from `TODO.md` already marked ✅ FIXED; **not re-verified in this pass** |

*Closed items move to `sprints/archive/` at quarter end (Q-06).*

---

## What this replaced

| Source | What happened to it |
|---|---|
| `TODO.md` | **Retired 2026-09-04.** Open rows are the Backlog above; the full file is preserved at [`sprints/archive/TODO-2026-09-04.md`](sprints/archive/TODO-2026-09-04.md). ⚠ Roughly 60 `followups/` documents say *"logged in `TODO.md`"* — **those records are historically accurate and are not being rewritten** |
| `PROGRESS.md` § *In progress / next* | Deleted (Q-04). `PROGRESS.md` keeps the build narrative and the deviations record — it answers *how did we get here*, never *what is next* |
| `sprints/README.md` status column | Still the map of sprints. Ticket-level status lives here |

✅ **This file is validated.** [`tests/repo/test_spine.py`](../tests/repo/test_spine.py) (OM-03) landed
2026-09-04 and runs in CI: nine checks covering duplicate ids, a stale next-free-id, an unknown kind,
a `blocked` row with no named blocker, two `current` items in one lane, a `done` row with no
verification level, a security view citing an item the register does not hold, and dead `followups/`
links. ⚠ **What it deliberately does not check** is whether the plan is any good — that judgement
would be wrong often enough to get the gate muted, and a muted gate is decoration.

⚠ **This paragraph claimed the opposite until 2026-09-06** — it said the test "does not exist" for two
days after it shipped, in the file whose entire purpose is to be the one true answer. The commit that
landed the test edited this file and missed this line. **That is rule §3's failure mode reproducing
itself inside the fix for rule §3**, and it is why `GRM-068` (the doc-header gate cannot see a
violation until after the commit lands) is a design gap and not a clerical one.
