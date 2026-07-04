# Agent runbook — HR-05: CI pipeline

**Branch:** `hardening/hr-05-ci` off `integration/seah-claude` · **Model:** Sonnet (medium effort — mechanical CI/config) · **Spec:** [`../03-ci-pipeline-spec.md`](../03-ci-pipeline-spec.md) · Read [`README.md`](README.md) common rules first.

## Mission

Create `.github/workflows/ci.yml` with three jobs (backend-tests with a Postgres service + all three migration streams, ui-checks with tsc + eslint, docs-links), fix the 4 pytest collection errors, and set the eslint baseline so the error channel only carries crash-class findings.

## Steps

1. **Reproduce the current state locally.** `pip install -r requirements.txt -r requirements.grm.txt -r requirements-dev.txt` in a fresh venv, then `python -m pytest tests/ticketing --collect-only -q`. Confirm the 4 collection errors (`jose`, `reportlab`) disappear with grm requirements installed; if any import is still missing, add it to the correct requirements file (grm deps → `requirements.grm.txt`).
2. **Determine runtime versions.** Python: check the Dockerfiles (`Dockerfile`, ticketing service build) — pin the same major.minor in CI. Node: check `channels/ticketing-ui/package.json` engines / its Dockerfile.
3. **Migration order.** Read `docs/deployment/03_operations.md` (migration run order section) and `docs/deployment/07_migrations_policy.md`. The backend job must run public → ticketing → ops streams against the service DB before pytest.
4. **Write the workflow** exactly per spec §1 (triggers, three parallel jobs, caching). The docs-links job runs an inline python script: walk `docs/` excluding any path containing `archive`, regex `\]\(([^)#\s]+)\)`, skip http/mailto, fail on missing targets (handle `%20`).
5. **ESLint baseline** per spec §2: in `channels/ticketing-ui/eslint.config.mjs`, downgrade `react-hooks/set-state-in-effect` to `warn` with a dated comment referencing the spec; the CI job fails on remaining **errors** only. Expect exactly 2 `rules-of-hooks` errors to remain until HR-06 merges — note this in `../PROGRESS.md` (the ui job will be red on this branch's PR; that is the documented expected state, coordinate merge order with HR-06 or land the two-line hook move here if HR-06 hasn't started — if you do, record it as a deviation).
6. **Verify on GitHub**: push the branch, open a draft PR, confirm all jobs run. Perform the two deliberate-failure checks from the spec (tsc error, broken doc link) as separate pushed-then-reverted commits; link the red runs in PROGRESS.
7. Tick your checklist in `../PROGRESS.md`, record the first green run URL, note the branch-protection manual step for the repo admin.

## Constraints

- Do not modify application code except: requirements files (missing deps) and `eslint.config.mjs`. The optional two-line HR-06 hook fix only under step 5's condition, logged as a deviation.
- Do not enable `npm run build` in CI if it needs live backend env or exceeds ~5 min — document the decision in the workflow file as a comment.
- Total workflow runtime must stay under 10 minutes.

## Done means

All acceptance boxes in spec §Tests ticked; PROGRESS updated; draft PR open with green (or documented-red ui job) status.
