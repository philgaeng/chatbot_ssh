# Dependency licence audit

**Status:** evidence pack — cited by the DPG assessment.
**Last updated:** 2026-09-03 · ⚠ backfilled from git 2026-09-04; not re-verified against the code

> **Regenerated 2026-09-03** on `integration/stage` — licences, CVEs and image digests in one pass,
> so this file now carries **one date** rather than three.
> **Serves DPG indicator 2** (use of an approved open licence) and, for the container-image set,
> indicator 4 (platform independence).
>
> **What the re-run changed, and what it did not.**
>
> - ✅ **The `boto3` prediction was right and is now measured.** The 2026-08-18 report warned it was
>   *"high by roughly four"* after the AWS SNS SMS path was deleted (privacy assessment F-12). It was
>   high by exactly four: `boto3`, `botocore`, `jmespath`, `s3transfer`. `python-dateutil` stayed —
>   something else pulls it. **133 → 129 Python packages; 153 → 149 overall.**
> - ✅ **The compliance claim is unchanged and is now re-measured rather than reasoned:**
>   **zero non-OSI, zero unknown**, across all four sets.
> - ✅ **26 packages moved version** since 08-18 and **no licence changed with them.** That is the
>   result the pin-drift check exists to make boring — and it is worth stating, because the one time
>   a licence *did* move under a stable pin is the finding this file was written around.
> - 🔴 **The npm vulnerability picture changed shape while keeping its count.** Still "4 high", but
>   they are now four different packages, and `next` itself carries nine advisories. See
>   [Known vulnerabilities](#known-vulnerabilities--measured-2026-09-03-on-integrationstage).
> - ⚪ npm licences (16 packages) and all four image digests are **byte-identical** to 08-18.
>
> **This report is generated. Re-run it rather than editing the rows by hand** — a hand-patched
> generated report is exactly the drift this file exists to remove.
>
> **This is the authoritative inventory, and it is the only one.** The hand-written summaries it
> replaced are gone — [`00_compliance_status.md`](00_compliance_status.md) cites this file and keeps no
> mirror of it, deliberately: a summary table in a second document is precisely the drift this evidence
> pack exists to remove. Where anything disagrees with this file, this file is right — it was produced
> from the resolved trees that actually ship, not from the manifests.

## How this was produced

**Licence scans run inside the running containers**, against the resolved dependency tree, per
CLAUDE.md §Docker-only. Reading manifests would have missed **95 of the 129** Python packages —
including the `jwcrypto` LGPL finding, and both LGPL libvips binaries on the npm side. **None of
those three is anyone's declared dependency**; they arrive transitively, and a licence obligation
does not care how a package got there.

```bash
# Python licences — the merged tree (see the correction below)
docker compose --env-file env.local -f docker-compose.yml -f docker-compose.grm.yml \
  exec ticketing_api sh -c "pip install pip-licenses && pip-licenses --format=json"

# Python CVEs — same container, what is actually installed
docker compose ... exec ticketing_api pip-audit --format=json

# npm licences — production tree only, from the image that ships
docker compose ... exec grm_ui npx license-checker --production --json

# container images — resolved digests
docker image inspect <image> --format '{{index .RepoDigests 0}}'

# npm CVEs — ⚠ NOT in-container: the shipped image has no lockfile (ENOLOCK)
cd channels/ticketing-ui && npm audit --omit=dev --json
```

⚠ **The last command is the one exception to "in-container", and it is not cosmetic.** `npm audit`
requires a lockfile, which a production image deliberately does not ship, so it measures the
**declared graph** rather than the **installed tree**. The two differ: the image's `node_modules`
holds 10 entries and the lockfile's production graph is larger. Findings from that command must be
checked against the image before being treated as shipped exposure — which is exactly what the
`postcss`/`nanoid` rows in the vulnerability section required.

### ⚠ There is one Python image, not two

The scan was specified to run against "both images — the chatbot image (`requirements.txt`) and
the ticketing/ops image (`requirements.grm.txt`) … they are not the same tree." **They are the same
tree.** One `Dockerfile` at the repo root serves every Python service and installs *both* manifests
into one image:

```dockerfile
COPY requirements.txt requirements.grm.txt /app/
RUN pip install -r /app/requirements.txt && pip install -r /app/requirements.grm.txt
```

Verified in the running container: `flask`, `rasa_sdk` and `openai` (chatbot) import alongside
`openpyxl` and `apscheduler` (GRM/ops). So the split below is by **manifest**,
recovered by parsing each requirements file — not by image, which cannot distinguish them.

## Summary

| Set | Packages | Non-OSI | Unknown | Needs a disposition |
|---|---|---|---|---|
| Python — declared (both manifests) | 34 | 0 | 0 | 2 |
| Python — transitive | 95 | 0 | 0 | 4 |
| npm — production tree | 16 | 0 | 0 | 2 + 1 tool artefact |
| Container images | 4 | 0 | 0 | 1 |
| **Total** | **149** | **0** | **0** | **10** |

⚠ **34, not 35.** `pip-licenses` is declared in `requirements.grm.txt` but **excludes itself and its
own dependencies from its output by default**, so it cannot appear in its own report. It is
Apache-2.0 (verified from its metadata) and it is a scanning tool that ships in the `ops` image, not
a runtime dependency of the platform. Recorded here because *"the manifest says 35 and the table
shows 34"* is precisely the kind of one-off discrepancy that gets explained away twice and
investigated never.

**No package in any tree carries an unknown, unparseable or non-OSI licence.** Indicator 2 is
answerable on the dependency tree; the remaining gap is the repository's own licence file, which is
landed, provisional pending the consultant — see `NOTICE`.

## Dispositions

Ten entries carry conditions beyond simple attribution. None blocks the submission; each is recorded
so a reviewer does not have to rediscover it.

| Package | Licence | Disposition |
|---|---|---|
| `psycopg2-binary` | LGPL-3.0 **with linking exception** | **Keep.** Unmodified library dependency, dynamically linked, standard across the Python ecosystem. The linking exception exists for exactly this use. Raised with the consultant as Q7(b) in case the DPGA reads it differently. |
| `jwcrypto` | LGPL-3.0-or-later | **Keep, and note it was not previously known.** Arrives transitively via the Keycloak JWT path. No linking exception, but it is an unmodified, dynamically-imported Python library — the LGPL's own §5 covers this. ⚠ **The hand-written inventory missed it entirely**, which is the clearest argument for this report existing. |
| `bidict` · `certifi` | MPL-2.0 | **Keep.** File-level weak copyleft; unmodified, not redistributed in modified form. `certifi` is the CA bundle every Python HTTP client uses. |
| `tqdm` | MPL-2.0 AND MIT | **Keep.** Same reasoning; the MPL portion is unmodified. |
| `email-validator` | The Unlicense | **Keep.** Public-domain dedication, OSI-approved. ⚠ Not to be confused with npm's `UNLICENSED`, which means *no licence declared* — the opposite. |
| `@img/sharp-libvips-linux-x64` · `-linuxmusl-x64` | LGPL-3.0-or-later | **Keep.** Prebuilt libvips binaries pulled in by `sharp`, which Next.js uses for image optimisation. Shipped unmodified as separate shared objects and dynamically loaded — the LGPL-compliant pattern. ⚠ Also absent from the hand-written inventory: `sharp` is nobody's declared dependency, it is a Next.js transitive. |
| `ticketing-ui@0.1.0` | reported `UNLICENSED` | **Explained, and partly fixed — but the row will not change.** Our own manifest declared no licence at all, contradicting the repository's Apache-2.0 `LICENSE`; `channels/ticketing-ui/package.json` and `channels/REST_webchat/package.json` now both declare `"license": "Apache-2.0"`. ⚠ **`license-checker` still reports `UNLICENSED`, and always will:** it hard-codes that value for any package with `"private": true` and ignores the `license` field entirely. Verified after rebuilding the image — the record it emits is `{"licenses": "UNLICENSED", "private": true}`. So this row is a **tool artefact for an unpublished package, not a finding**: our own code's licence is `LICENSE` + the per-file SPDX headers, and the manifest now states it too for anyone reading the file. |
| `redis:8.10` | RSALv2 / SSPLv1 / **AGPLv3** (tri-licensed) | **Keep, elected under AGPLv3** — the one OSI-approved option of the three. Runs as an unmodified upstream image behind a network boundary; no Redis source is conveyed, so AGPLv3 imposes nothing on this repository or a downstream fork. Consultant Q7(a) asks whether AGPL anywhere in the stack is a problem for ADB/DOR procurement; Valkey (BSD-3-Clause) is the costed fallback. |

## Open decision #3 — the Rasa licence question, closed

The source narrative flagged Rasa as a possible week-one indicator-2 emergency. **Resolved
mechanically, from the resolved tree:**

| Package | Version | Licence | What it actually is |
|---|---|---|---|
| `rasa-sdk` | 3.6.2 | Apache-2.0 | The only Rasa-family package installed, and **Apache-2.0, so the licence question is closed either way**. There is no Rasa server, no Rasa NLU and no TensorFlow anywhere in the tree — verified against the resolved tree. ⚠ **It is not merely a type shim**: 49 modules import it, `BaseFormValidationAction` inherits `FormValidationAction`, and the orchestrator executes `action.run(...)`. Removing it is a refactor, not a deletion — see §Known vulnerabilities. |

Nothing further is owed on this. The alarm cost an hour, not a week.

## Container images

| Image | Resolved digest | Licence |
|---|---|---|
| `postgres:15` | `sha256:3e43515057e113ee741fca2f621f15300be34a6d4a8dfcf2e20651288c8272f3` | PostgreSQL Licence (OSI-approved) |
| `redis:8.10` | `sha256:344e3945a0b431c8ff1eecd58c5573538126bd756f02fc7e218ddf1fc2546366` | AGPLv3 at our election — see dispositions |
| `nginx:stable` | `sha256:146adea4768b83c607d0bdfa4188464e3da6e0a3ad4475db1d1d8f64f27c29cc` | BSD-2-Clause |
| `quay.io/keycloak/keycloak:26.0.7` | `sha256:4388e2379b7e870a447adbe7b80bd61f5fbf04e925832b19669fda4957f05a81` | Apache-2.0 |

### The pin-drift check

Container images were **a fourth dependency set nobody was auditing, and the only place a licence
actually drifted.** `redis:7` pinned the major only; Redis 7.2 was BSD-3-Clause and 7.4 moved to
RSALv2/SSPLv1. The tag followed upstream across that boundary with nobody editing the file.

`tests/repo/test_image_pins.py` now fails the build when an image is pinned looser than
MAJOR.MINOR, unless it is in an explicit exception list that must state why the licence is stable
across the range the tag spans. `postgres:15` and `nginx:stable` are the two current exceptions.
It also asserts Compose and CI declare the *same* image, so CI cannot end up testing a different
Redis than production runs.

## Staying true

A dated audit is stale the next time anybody adds a dependency, and indicator 2 is a claim that has
to hold continuously. The licence scan is therefore **scheduled**, not a pre-submission
artefact:

* `ops/security.py` → `licence_scan()`, scheduled nightly at 01:50 beside the existing `pip-audit`
  CVE scan, writing to `ops.dependency_findings` with `source='pip-licenses'`. Report-only; it never
  blocks a deploy.

  ⚠ **Scheduled is not the same as running, and it has still never run on a deployed host — but
  the reason changed on 2026-09-03.** The `ops` container **is now deployed to staging**, healthy,
  with its schema migrated; `ops.dependency_findings` there is **empty**, because the job is nightly
  and has not yet had a night. DOR production has no `ops` at all. **Treat this report's freshness as
  the date at the top, never as a nightly guarantee** — and note that *deployed* and *has run* are
  two claims, not one.
* Classification lives in `ops/licences.py` — pure logic, unit-tested by
  `tests/repo/test_licence_scan.py`. Anything unrecognised surfaces as a **high** finding rather
  than passing silently, which is the only failure direction that is safe.
* `pip-licenses>=5.0` is declared in `requirements.grm.txt` and present in the `ops` image
  (`pip-licenses 5.5.5`). **The scheduled job has been run for real once, on 2026-08-18**, against a
  development stack: `licence_scan()` scanned **133 packages** and wrote **5 findings** to `ops.dependency_findings`, with a `licence_scan` row in `ops.system_health_checks`
  reading `warn · {"flagged": {"warn": 5}, "scanned": 133}`.

  **The five it flagged are exactly the five this report dispositions**, and all are OSI-approved weak
  copyleft — `psycopg2-binary` (LGPL w/ linking exception), `jwcrypto` (LGPL-3.0-or-later), `certifi`
  and `bidict` (MPL-2.0), `tqdm` (MPL-2.0 AND MIT). **Zero unknown, zero non-OSI**, which is the
  hand-written claim above reproduced mechanically by the job that will keep making it. `warn` is the
  designed severity for copyleft: flag for review, do not fail the build.

  ⚠ **One operational precondition surfaced by running it** — see the deviation below.

### ⚠ The scan writes nothing unless `ops` can authenticate — fixed in code, still unset on every host

Found while verifying the run above, and it was never specific to the licence scan: **it disabled
every ops finding, including the `pip-audit` CVE scan.**

`ops` authenticated as the `ops_app` role using the **admin** password, because `ops_db_user` defaults
to the non-empty string `"ops_app"` (so its fallback can never fire) while `ops_db_password` *does*
fall back to `postgres_password`. Meanwhile the migration created the role **without a password at
all** when `OPS_DB_PASSWORD` was unset, so nothing could authenticate it.

⚠ **The failure mode was the problem, and it is the reason this went unnoticed for days.**
`licence_scan()` **returned normally** — it logged a failure to record the check, tried to raise an
alert, and could not send that either. The container reported `healthy` throughout while writing
nothing. **A scan that manufactures confidence is worse than no scan.**

**Status 2026-08-24:** the credential defect is **fixed in code** and `OPS_DB_PASSWORD` is now carried
in `secrets.enc.env` rather than living only on one host. ⚠ **Two things still stand between that and
a working scan**, and both are deployment steps rather than code:

1. **Publishing a database credential does not set it.** Until someone runs `ALTER ROLE ops_app
   PASSWORD` on a given box, `ops` cannot authenticate there — and will still report `healthy` while
   writing nothing.
2. **`ops` is not deployed to staging or DOR prod at all**, so no licence or CVE scan runs anywhere
   but a development stack.

The claim *"the scan runs on the schedule"* is true **given a
deployed and correctly configured ops container**, and that caveat belongs with the claim every time
it is made.

## Python — declared dependencies (34)

| Package | Version | Licence | Declared in |
|---|---|---|---|
| `alembic` | 1.19.1 | MIT | chatbot + GRM |
| `APScheduler` | 3.11.3 | MIT License | GRM/ops |
| `celery` | 5.5.2 | BSD License | chatbot |
| **`email-validator`** | 2.3.0 | The Unlicense (Unlicense) | chatbot |
| `fastapi` | 0.141.1 | MIT | chatbot |
| `Flask` | 3.1.3 | BSD-3-Clause | chatbot |
| `Flask-SocketIO` | 5.6.1 | MIT License | chatbot |
| `flower` | 2.0.1 | BSD License | chatbot |
| `httpx` | 0.28.1 | BSD License | chatbot + GRM |
| `icecream` | 2.2.0 | MIT License | chatbot |
| `langdetect` | 1.0.9 | Apache Software License | chatbot |
| `openai` | 1.70.0 | Apache Software License | chatbot |
| `openpyxl` | 3.1.5 | MIT License | GRM/ops |
| `pip_audit` | 2.10.1 | Apache Software License | GRM/ops |
| **`psycopg2-binary`** | 2.9.10 | GNU Library or Lesser General Public License (LGPL) | chatbot |
| `pydantic` | 2.13.4 | MIT | chatbot |
| `pydantic-settings` | 2.15.0 | MIT | chatbot |
| `pytest` | 9.1.1 | MIT | GRM/ops |
| `python-dotenv` | 1.1.1 | BSD License | chatbot |
| `python-jose` | 3.5.0 | MIT License | GRM/ops |
| `python-keycloak` | 7.1.1 | MIT License | GRM/ops |
| `python-multipart` | 0.0.32 | Apache-2.0 | chatbot |
| `python-socketio` | 5.16.4 | MIT | chatbot |
| `pytz` | 2026.3.post1 | MIT License | chatbot |
| `pyvips` | 3.1.1 | MIT License | chatbot |
| `PyYAML` | 6.0.3 | MIT License | chatbot |
| `RapidFuzz` | 3.13.0 | MIT | chatbot |
| `rasa-sdk` | 3.6.2 | Apache Software License | chatbot |
| `redis` | 4.6.0 | MIT License | chatbot |
| `reportlab` | 5.0.1 | BSD License | GRM/ops |
| `requests` | 2.34.2 | Apache Software License | chatbot |
| `SQLAlchemy` | 2.0.52 | MIT | chatbot |
| `uvicorn` | 0.49.0 | BSD-3-Clause | chatbot |
| `Werkzeug` | 3.1.8 | BSD-3-Clause | chatbot |

## Python — transitive dependencies (95)

Not declared in any manifest; resolved by pip. Included because a licence obligation does not care
whether you chose the package directly — and because both LGPL findings above live here.

| Package | Version | Licence | Declared in |
|---|---|---|---|
| `aiofiles` | 25.1.0 | Apache Software License | transitive |
| `amqp` | 5.3.1 | BSD License | transitive |
| `annotated-doc` | 0.0.5 | MIT | transitive |
| `annotated-types` | 0.8.0 | MIT | transitive |
| `anyio` | 4.14.2 | MIT | transitive |
| `asttokens` | 3.0.2 | Apache 2.0 | transitive |
| `async-timeout` | 5.0.1 | Apache Software License | transitive |
| **`bidict`** | 0.23.1 | Mozilla Public License 2.0 (MPL 2.0) | transitive |
| `billiard` | 4.2.4 | BSD License | transitive |
| `blinker` | 1.9.0 | MIT License | transitive |
| `boolean.py` | 5.0 | BSD-2-Clause | transitive |
| `CacheControl` | 0.14.4 | Apache-2.0 | transitive |
| **`certifi`** | 2026.7.22 | Mozilla Public License 2.0 (MPL 2.0) | transitive |
| `cffi` | 2.1.1 | MIT-0 | transitive |
| `charset-normalizer` | 3.5.1 | MIT | transitive |
| `click` | 8.5.0 | BSD-3-Clause | transitive |
| `click-didyoumean` | 0.3.1 | MIT License | transitive |
| `click-plugins` | 1.1.1.2 | BSD License | transitive |
| `click-repl` | 0.2.0 | MIT | transitive |
| `colorama` | 0.4.6 | BSD License | transitive |
| `coloredlogs` | 15.0.1 | MIT License | transitive |
| `cryptography` | 50.0.1 | Apache-2.0 OR BSD-3-Clause | transitive |
| `cyclonedx-python-lib` | 11.12.0 | Apache Software License | transitive |
| `defusedxml` | 0.7.1 | Python Software Foundation License | transitive |
| `deprecation` | 2.1.0 | Apache Software License | transitive |
| `distro` | 1.9.0 | Apache Software License | transitive |
| `dnspython` | 2.8.0 | ISC License (ISCL) | transitive |
| `ecdsa` | 0.19.2 | MIT | transitive |
| `et_xmlfile` | 2.0.0 | MIT License | transitive |
| `exceptiongroup` | 1.3.1 | MIT License | transitive |
| `executing` | 2.2.1 | MIT License | transitive |
| `filelock` | 3.32.4 | MIT | transitive |
| `greenlet` | 3.5.5 | MIT AND PSF-2.0 | transitive |
| `h11` | 0.16.0 | MIT License | transitive |
| `httpcore` | 1.0.9 | BSD-3-Clause | transitive |
| `httptools` | 0.8.0 | MIT | transitive |
| `humanfriendly` | 10.0 | MIT License | transitive |
| `humanize` | 4.16.0 | MIT | transitive |
| `idna` | 3.19 | BSD-3-Clause | transitive |
| `iniconfig` | 2.3.0 | MIT | transitive |
| `itsdangerous` | 2.2.0 | BSD License | transitive |
| `Jinja2` | 3.1.6 | BSD License | transitive |
| `jiter` | 0.16.0 | MIT | transitive |
| **`jwcrypto`** | 1.5.9 | LGPL-3.0-or-later | transitive |
| `kombu` | 5.5.4 | BSD License | transitive |
| `license-expression` | 30.4.4 | Apache-2.0 | transitive |
| `Mako` | 1.4.1 | MIT | transitive |
| `markdown-it-py` | 4.2.0 | MIT License | transitive |
| `MarkupSafe` | 3.0.3 | BSD-3-Clause | transitive |
| `mdurl` | 0.1.2 | MIT License | transitive |
| `msgpack` | 1.2.2 | Apache-2.0 | transitive |
| `multidict` | 5.2.0 | Apache Software License | transitive |
| `packageurl-python` | 0.17.6 | MIT License | transitive |
| `packaging` | 26.3 | Apache-2.0 OR BSD-2-Clause | transitive |
| `pillow` | 12.3.0 | MIT-CMU | transitive |
| `pip-api` | 0.0.34 | Apache Software License | transitive |
| `pip-requirements-parser` | 32.0.1 | MIT | transitive |
| `platformdirs` | 4.11.5 | MIT | transitive |
| `pluggy` | 1.6.0 | MIT License | transitive |
| `prometheus_client` | 0.26.0 | Apache-2.0 AND BSD-2-Clause | transitive |
| `prompt-toolkit` | 3.0.28 | BSD License | transitive |
| `py-serializable` | 2.1.0 | Apache Software License | transitive |
| `pyasn1` | 0.6.4 | BSD-2-Clause | transitive |
| `pycparser` | 3.0 | BSD-3-Clause | transitive |
| `pydantic_core` | 2.46.4 | MIT | transitive |
| `Pygments` | 2.21.0 | BSD-2-Clause | transitive |
| `pyparsing` | 3.3.2 | MIT | transitive |
| `python-dateutil` | 2.9.0.post0 | Apache Software License; BSD License | transitive |
| `python-engineio` | 4.13.5 | MIT | transitive |
| `requests-toolbelt` | 1.0.0 | Apache Software License | transitive |
| `rich` | 15.0.0 | MIT License | transitive |
| `rsa` | 4.9.1 | Apache Software License | transitive |
| `ruamel.yaml` | 0.17.40 | MIT License | transitive |
| `ruamel.yaml.clib` | 0.2.15 | MIT License | transitive |
| `sanic` | 21.12.2 | MIT License | transitive |
| `Sanic-Cors` | 2.2.0 | MIT License | transitive |
| `sanic-routing` | 0.7.2 | MIT License | transitive |
| `simple-websocket` | 1.1.0 | MIT License | transitive |
| `six` | 1.17.0 | MIT License | transitive |
| `sniffio` | 1.3.1 | Apache Software License; MIT License | transitive |
| `sortedcontainers` | 2.4.0 | Apache Software License | transitive |
| `starlette` | 1.6.0 | BSD-3-Clause | transitive |
| `tomli_w` | 1.2.0 | MIT License | transitive |
| `tornado` | 6.5.8 | Apache Software License | transitive |
| **`tqdm`** | 4.70.0 | MPL-2.0 AND MIT | transitive |
| `typing-inspection` | 0.4.4 | MIT | transitive |
| `typing_extensions` | 4.16.0 | PSF-2.0 | transitive |
| `tzdata` | 2026.3 | Apache-2.0 | transitive |
| `tzlocal` | 5.4.4 | MIT | transitive |
| `ujson` | 5.13.0 | BSD-3-Clause AND TCL | transitive |
| `urllib3` | 2.7.0 | MIT | transitive |
| `uvloop` | 0.22.1 | Apache Software License; MIT License | transitive |
| `vine` | 5.1.0 | BSD License | transitive |
| `websockets` | 10.4 | BSD License | transitive |
| `wsproto` | 1.3.2 | MIT | transitive |

## npm — production tree (16)

`--production` only: the dev toolchain (TypeScript, ESLint, Vitest, Tailwind) does not ship and is
out of scope for redistribution. Sixteen packages is the entire runtime tree — there is no component
library, state-management library, charting library or analytics SDK.

| Package | Licence |
|---|---|
| `@img/colour@1.1.0` | MIT |
| **`@img/sharp-libvips-linux-x64@1.2.4`** | **LGPL-3.0-or-later** |
| **`@img/sharp-libvips-linuxmusl-x64@1.2.4`** | **LGPL-3.0-or-later** |
| `@img/sharp-linux-x64@0.34.5` | Apache-2.0 |
| `@img/sharp-linuxmusl-x64@0.34.5` | Apache-2.0 |
| `@next/env@16.2.6` | MIT |
| `@swc/helpers@0.5.15` | Apache-2.0 |
| `client-only@0.0.1` | MIT |
| `detect-libc@2.1.2` | Apache-2.0 |
| `next@16.2.6` | MIT |
| `react-dom@19.2.4` | MIT |
| `react@19.2.4` | MIT |
| `semver@7.7.4` | ISC |
| `sharp@0.34.5` | Apache-2.0 |
| `styled-jsx@5.1.6` | MIT |
| **`ticketing-ui@0.1.0`** | **UNLICENSED** ⚠ *our own package — see below* |

⚠ **That last row is our own application, and it does not mean what it appears to mean.**
`license-checker` emits `UNLICENSED` for any package marked `"private": true` **regardless of the
`license` field** — the record is literally `{"licenses": "UNLICENSED", "private": true}`.

The scan was still worth running: the manifest genuinely declared no licence at the time, and that
has been fixed (`"license": "Apache-2.0"` in both npm manifests). ⚠ **A rebuild does not flip this
row** — verified by rebuilding `grm_ui` and re-running the scan. `private: true` is what produces
`UNLICENSED`, and it is correct for an application that is not published.

---

## Known vulnerabilities — measured 2026-09-03, on `integration/stage`

Distinct from the licence question above and recorded here because a reviewer reaching this repository
through GitHub sees a vulnerability count before they see anything else.

⚠ **GitHub's alert count is measured against `main`, which is stale by months and hundreds of
commits**, with all three dependency manifests differing. It measures a tree this work has already
moved past; it is not a measurement of the code. **Measured here instead**, against the resolved
trees:

| Set | Findings | Notes |
|---|---|---|
| Python (`pip-audit`, in `ticketing_api`) | **6 across 5 packages** — unchanged since 08-23 | `ecdsa` ⚠ no fix released · `sanic-cors` · `wheel` · `python-dotenv` → 1.2.2 · `setuptools` → 83.0.0 |
| npm, production tree (`npm audit --omit=dev`) | **4 high** — ⚠ **same count, different findings** | `next` (nine advisories) · `postcss` · `nanoid` · `sharp` |

### 🔴 The npm count stayed at four and stopped meaning the same thing

On 2026-08-23 the four were **one package**: `sharp` inheriting four libvips CVEs, with the fix
outside the stated Next.js range. Today they are **four packages**, and the composition is worse than
the count suggests:

* **`next@16.2.6`** now carries **nine** advisories of its own — among them a **middleware/proxy
  bypass in App Router**, **SSRF in Server Actions on custom servers**, **SSRF in rewrites via an
  attacker-controlled destination hostname**, and **unauthenticated disclosure of internal Server
  Function endpoints**. This is the officer portal's framework, it **ships**, and these are not
  build-time findings. **It is the one row on this page that should be acted on rather than
  explained.**
* **`postcss` and `nanoid`** arrive under `next` in the lockfile graph. ⚠ **Neither is present in the
  shipped image** — verified: `grm_ui`'s `node_modules` holds **10 entries** and contains neither.
  They are lockfile-graph findings, and counting them as shipped exposure would repeat the mistake
  the `rasa-sdk` paragraph below corrects.
* **`sharp` < 0.35.0** — unchanged, still the libvips inheritance, still gated behind a framework
  bump.

⚠ **The method differs between the two sets, and it matters.** `pip-audit` runs **inside the running
container**, against what is installed. `npm audit` needs a lockfile, which the production image does
not ship (`ENOLOCK`), so it runs against `channels/ticketing-ui/package-lock.json` — the **declared
graph**, not the shipped tree. That is why the `postcss`/`nanoid` distinction above had to be checked
by hand rather than read off the report.

⭐ **The transferable point, and it is the same one this file makes about licences:** a count that
holds still is not a tree that holds still. Between two runs three weeks apart the npm number was
identical and every finding behind it had changed. **Re-run the command; do not re-read the number.**

### ⚠ Two of the six come from `rasa-sdk` — and neither the fix nor the risk is what it looks like

`rasa-sdk` pulls **`sanic-cors`** and **`wheel`**. The tempting conclusion is that removing a
"type shim" removes a third of the Python findings cheaply. **Both halves of that are wrong, and the
correction is worth more than the original claim.**

**The risk is near zero, not a third.** Neither CVE is reachable. `sanic-cors` is CORS middleware for
a Sanic web server — `sanic` is never imported by any module in this repository, so the code never
executes. `wheel` is build tooling, not a runtime import. **They are findings in a count, not exposure
in a system**, and a remediation plan that optimises the count over the risk is how the expensive work
gets done first.

**The removal is a refactor, not a deletion.** `rasa-sdk` is imported by **49 modules**. The surface
used is `Tracker`, `CollectingDispatcher`, `Action`, `DomainDict`, six event constructors — **and
`FormValidationAction`, which `BaseFormValidationAction` inherits** and whose `run()` the orchestrator
invokes (`backend/orchestrator/action_registry.py`). The events are trivial dict factories and would
be a dozen lines; `Tracker` (302 lines) and the inherited form-validation dispatch are not. This is a
framework dependency being driven at runtime, and replacing it means reimplementing a slot-validation
loop that the live chatbot's intake path runs on.

**Conclusion: do not do this for the CVEs.** If `rasa-sdk` is ever removed it should be for its own
reasons — owning the form loop outright — with the dependency reduction as a side effect, and it needs
a characterization net over the intake path first, exactly as was done for the LLM surfaces.

### The other four

* **`ecdsa`** — arrives via `python-jose`, the Keycloak JWT path. ⚠ **No fix version has been
  published**, so this is a standing exposure requiring either a mitigation or a move to a different
  JWT library. The one on this list that cannot be closed by a version bump.
* **`sharp` / libvips** — the same prebuilt binaries [flagged above as LGPL transitives](#dispositions),
  arriving through Next.js image optimisation. ⚠ The advertised fix moves Next.js **outside the stated
  dependency range**, so it is a framework bump, not a patch.
* **`python-dotenv`, `setuptools`** — ordinary version bumps, no downstream constraint.

### ⏭ What this section owes, ranked

| | Item | Why it is where it is |
|---|---|---|
| 🔴 | **Bump `next` past 16.3.0** | Nine advisories in a framework that ships and faces officers, two of them SSRF. The only row here that is reachable, shipped and fixable in one move — and it takes `postcss`, `nanoid` and `sharp` with it |
| 🟠 | **`ecdsa` — mitigate or move off `python-jose`** | No fix exists, so it cannot be closed by a bump. It sits on the Keycloak JWT path, which is authentication |
| 🟡 | **`python-dotenv`, `setuptools`** | Free bumps, no constraint. Do them with anything else |
| ⚪ | **`sanic-cors`, `wheel`** | **Deliberately last.** Unreachable, and doing them first is how a remediation plan optimises the count over the risk |

⚠ **`ops`'s nightly scan is what should be finding all of this. It is now on staging and has
produced nothing yet** — see [Staying true](#staying-true). Everything above was found by a person
running a command by hand.
