# HR-05 — CI Pipeline (pytest + tsc + eslint gates)

> Workstream C · Branch `hardening/hr-05-ci` · Start first: every other workstream merges behind this gate.
> Evidence: no `.github/` exists; `tests/ticketing` has 115 collected tests **+ 4 collection errors** (`ModuleNotFoundError: jose`, `reportlab` — both ARE in `requirements.grm.txt:10,14`, so this is an environment problem, not a code problem); the portal has 137 eslint problems including 2 `react-hooks/rules-of-hooks` errors and **zero** tests; `tsc --noEmit` is clean today and should stay that way.

## Change

### 1. `.github/workflows/ci.yml`

Triggers: `pull_request` + `push` to `integration/**` and `main`. Three parallel jobs:

**backend-tests**
- `services: postgres:15` (db `grievance_db_test`, health-checked).
- Python 3.11 (match the Dockerfiles — verify before pinning), pip cache.
- `pip install -r requirements.txt -r requirements.grm.txt -r requirements-dev.txt`.
- Env: test DB URL, `TICKETING_ENV=dev` (after HR-01 lands; harmless before).
- Run migrations against the service DB in the documented order (public → ticketing → ops; see `docs/deployment/03_operations.md`), then:
  `pytest tests/ticketing tests/orchestrator tests/actions -q --maxfail=20`.
- **Collection errors are failures**: add `--strict-markers` and assert exit code; the current 4 collection errors must be fixed (they disappear once the grm requirements are installed — verify, and if any import is genuinely missing from requirements files, add it there).

**ui-checks** (working dir `channels/ticketing-ui/`)
- Node 20 (match `package.json` engines / Dockerfile — verify), `npm ci` with cache.
- `npx tsc --noEmit` — must pass (it does today; this locks it in).
- `npx eslint . --max-warnings=-1` — see baseline strategy below.
- `npm run build` — include **only if** it completes < ~5 min in CI without backend env vars; otherwise add `NEXT_PUBLIC_*` dummies or drop it and note why in the workflow file.

**docs-links** (cheap, keeps the July reorg honest)
- Run the relative-markdown-link checker over `docs/` excluding `archive/` (inline python step; same logic used in the July reorg). Broken link ⇒ red.

### 2. ESLint baseline strategy

The portal currently has 85 errors / 52 warnings. Do **not** boil the ocean and do **not** silence rules globally:
- Gate on **errors only** in the `react-hooks` family (`rules-of-hooks`, `exhaustive-deps` stays warn) plus `no-unused-vars` as warn.
- HR-06 fixes the 2 `rules-of-hooks` errors; coordinate — this job may be red on the integration branch until HR-06 merges. That's acceptable and expected; note it in PROGRESS.
- Downgrade `react-hooks/set-state-in-effect` (~80 errors, stylistic here) to `warn` in `eslint.config.mjs` with a dated comment pointing at this spec, so the error channel is reserved for crash-class findings.

### 3. Branch protection (manual step, repo admin)

Document in PROGRESS (cannot be done by the agent unless `gh` has admin): require the three jobs on PRs to `main` and `integration/**`.

## Tests (acceptance)

- [ ] A PR touching a ticketing file runs all three jobs; backend job spins Postgres, migrates all three streams, and passes with **0 collection errors**.
- [ ] Introduce a deliberate `tsc` error on a scratch branch ⇒ ui-checks red; revert.
- [ ] Introduce a deliberate broken doc link on a scratch branch ⇒ docs-links red; revert.
- [ ] Workflow completes in < 10 min total (parallel jobs).

## Manual verification
- [ ] `gh run list` shows green on the workstream branch.
- [ ] README badge (optional) or PROGRESS note recording the first green run URL.
