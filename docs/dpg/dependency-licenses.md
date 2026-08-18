# Dependency licence audit

> **Generated 2026-08-18** · commit `8470df63` (branch `dpg/sprint0-licensing`) · ticket **DPG-02**
> **Serves DPG indicator 2** (use of an approved open licence) and, for the container-image set,
> indicator 4 (platform independence).
>
> **This supersedes the hand-written inventory** in
> [`01_consultant_briefing.md`](01_consultant_briefing.md) §6 and
> [`00_compliance_status.md`](00_compliance_status.md) Appendix A, both of which are marked
> "pending the generated report". Where they disagree with this file, this file is right — it was
> produced from the resolved trees that actually ship, not from the manifests.

## How this was produced

Every scan ran **inside the running containers**, against the resolved dependency tree, per
CLAUDE.md §Docker-only. Reading manifests would have missed 98 of the 133 Python packages —
including the `jwcrypto` LGPL finding, and both LGPL libvips binaries on the npm side. **None of
those three is anyone's declared dependency**; they arrive transitively, and a licence obligation
does not care how a package got there.

```bash
# Python — the merged tree (see the correction below)
docker compose --env-file env.local -f docker-compose.yml -f docker-compose.grm.yml \
  exec ticketing_api sh -c "pip install pip-licenses && pip-licenses --format=json"

# npm — production tree only, from the image that ships
docker compose ... exec grm_ui npx license-checker --production --json

# container images — resolved digests
docker image inspect <image> --format '{{index .RepoDigests 0}}'
```

### ⚠ Correction to the DPG-02 spec: there is one Python image, not two

The ticket says to run the scan against "both images — the chatbot image (`requirements.txt`) and
the ticketing/ops image (`requirements.grm.txt`) … they are not the same tree." **They are the same
tree.** One `Dockerfile` at the repo root serves every Python service and installs *both* manifests
into one image:

```dockerfile
COPY requirements.txt requirements.grm.txt /app/
RUN pip install -r /app/requirements.txt && pip install -r /app/requirements.grm.txt
```

Verified in the running container: `flask`, `rasa_sdk` and `openai` (chatbot) import alongside
`pydantic_settings`, `openpyxl` and `apscheduler` (GRM/ops). So the split below is by **manifest**,
recovered by parsing each requirements file — not by image, which cannot distinguish them.

## Summary

| Set | Packages | Non-OSI | Unknown | Needs a disposition |
|---|---|---|---|---|
| Python — declared (both manifests) | 35 | 0 | 0 | 2 |
| Python — transitive | 98 | 0 | 0 | 4 |
| npm — production tree | 16 | 0 | 0 | 3 |
| Container images | 4 | 0 | 0 | 1 |
| **Total** | **153** | **0** | **0** | **10** |

**No package in any tree carries an unknown, unparseable or non-OSI licence.** Indicator 2 is
answerable on the dependency tree; the remaining gap is the repository's own licence file, which is
DPG-01 (landed, provisional pending the consultant — see NOTICE).

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
| `ticketing-ui@0.1.0` | ~~UNLICENSED~~ → **Apache-2.0** | ✅ **Fixed in this ticket.** Our own package manifest declared no licence, so the tooling reported `UNLICENSED` — directly contradicting the Apache-2.0 `LICENSE` that DPG-01 had just added at the repo root. `channels/ticketing-ui/package.json` and `channels/REST_webchat/package.json` now both declare `"license": "Apache-2.0"`. **A DPG reviewer running `license-checker` would have found this before we did.** |
| `redis:8.10` | RSALv2 / SSPLv1 / **AGPLv3** (tri-licensed) | **Keep, elected under AGPLv3** — the one OSI-approved option of the three. Runs as an unmodified upstream image behind a network boundary; no Redis source is conveyed, so AGPLv3 imposes nothing on this repository or a downstream fork. Consultant Q7(a) asks whether AGPL anywhere in the stack is a problem for ADB/DOR procurement; Valkey (BSD-3-Clause) is the costed fallback. |

## Open decision #3 — the Rasa licence question, closed

The source narrative flagged Rasa as a possible week-one indicator-2 emergency. **Resolved
mechanically, from the resolved tree:**

| Package | Version | Licence | What it actually is |
|---|---|---|---|
| `rasa-sdk` | 3.6.2 | Apache-2.0 | The only Rasa-family package installed. There is no Rasa server, no Rasa NLU and no TensorFlow anywhere in the tree — the conversational state machine is this project's own code, and `rasa-sdk` survives as a type shim for `Tracker` / `CollectingDispatcher`. |

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
to hold continuously. Per **Q-06**, the licence scan is now **scheduled**, not a pre-submission
artefact:

* `ops/security.py` → `licence_scan()`, running nightly at 01:50 beside the existing `pip-audit`
  CVE scan, writing to `ops.dependency_findings` with `source='pip-licenses'`. Report-only; it
  never blocks a deploy.
* Classification lives in `ops/licences.py` — pure logic, unit-tested by
  `tests/repo/test_licence_scan.py`. Anything unrecognised surfaces as a **high** finding rather
  than passing silently, which is the only failure direction that is safe.
* `pip-licenses>=5.0` is declared in `requirements.grm.txt`. ⚠ It was installed ad-hoc in the
  container for *this* scan, so the nightly job starts working on the next image rebuild.

## Python — declared dependencies (35)

| Package | Version | Licence | Declared in |
|---|---|---|---|
| `alembic` | 1.18.5 | MIT | chatbot + GRM |
| `APScheduler` | 3.11.3 | MIT License | GRM/ops |
| `boto3` | 1.37.28 | Apache Software License | chatbot |
| `celery` | 5.5.2 | BSD License | chatbot |
| **`email-validator`** | 2.3.0 | The Unlicense (Unlicense) | chatbot |
| `fastapi` | 0.139.2 | MIT | chatbot |
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
| `pydantic-settings` | 2.14.2 | MIT | GRM/ops |
| `pytest` | 9.1.1 | MIT | GRM/ops |
| `python-dotenv` | 1.1.1 | BSD License | chatbot |
| `python-jose` | 3.5.0 | MIT License | GRM/ops |
| `python-keycloak` | 7.1.1 | MIT License | GRM/ops |
| `python-multipart` | 0.0.32 | Apache-2.0 | chatbot |
| `python-socketio` | 5.16.3 | MIT | chatbot |
| `pytz` | 2026.2 | MIT License | chatbot |
| `pyvips` | 3.1.1 | MIT License | chatbot |
| `PyYAML` | 6.0.3 | MIT License | chatbot |
| `RapidFuzz` | 3.13.0 | MIT | chatbot |
| `rasa-sdk` | 3.6.2 | Apache Software License | chatbot |
| `redis` | 4.6.0 | MIT License | chatbot |
| `reportlab` | 5.0.0 | BSD License | GRM/ops |
| `requests` | 2.34.2 | Apache Software License | chatbot |
| `SQLAlchemy` | 2.0.51 | MIT | chatbot |
| `uvicorn` | 0.49.0 | BSD-3-Clause | chatbot |
| `Werkzeug` | 3.1.8 | BSD-3-Clause | chatbot |

## Python — transitive dependencies (98)

Not declared in any manifest; resolved by pip. Included because a licence obligation does not care
whether you chose the package directly — and because both LGPL findings above live here.

| Package | Version | Licence | Declared in |
|---|---|---|---|
| `aiofiles` | 25.1.0 | Apache Software License | transitive |
| `amqp` | 5.3.1 | BSD License | transitive |
| `annotated-doc` | 0.0.4 | MIT | transitive |
| `annotated-types` | 0.8.0 | MIT | transitive |
| `anyio` | 4.14.2 | MIT | transitive |
| `asttokens` | 3.0.2 | Apache 2.0 | transitive |
| `async-timeout` | 5.0.1 | Apache Software License | transitive |
| **`bidict`** | 0.23.1 | Mozilla Public License 2.0 (MPL 2.0) | transitive |
| `billiard` | 4.2.4 | BSD License | transitive |
| `blinker` | 1.9.0 | MIT License | transitive |
| `boolean.py` | 5.0 | BSD-2-Clause | transitive |
| `botocore` | 1.37.38 | Apache Software License | transitive |
| `CacheControl` | 0.14.4 | Apache-2.0 | transitive |
| **`certifi`** | 2026.7.22 | Mozilla Public License 2.0 (MPL 2.0) | transitive |
| `cffi` | 2.1.0 | MIT-0 | transitive |
| `charset-normalizer` | 3.4.9 | MIT | transitive |
| `click` | 8.4.2 | BSD-3-Clause | transitive |
| `click-didyoumean` | 0.3.1 | MIT License | transitive |
| `click-plugins` | 1.1.1.2 | BSD License | transitive |
| `click-repl` | 0.2.0 | MIT | transitive |
| `colorama` | 0.4.6 | BSD License | transitive |
| `coloredlogs` | 15.0.1 | MIT License | transitive |
| `cryptography` | 49.0.0 | Apache-2.0 OR BSD-3-Clause | transitive |
| `cyclonedx-python-lib` | 11.11.0 | Apache Software License | transitive |
| `defusedxml` | 0.7.1 | Python Software Foundation License | transitive |
| `deprecation` | 2.1.0 | Apache Software License | transitive |
| `distro` | 1.9.0 | Apache Software License | transitive |
| `dnspython` | 2.8.0 | ISC License (ISCL) | transitive |
| `ecdsa` | 0.19.2 | MIT | transitive |
| `et_xmlfile` | 2.0.0 | MIT License | transitive |
| `exceptiongroup` | 1.3.1 | MIT License | transitive |
| `executing` | 2.2.1 | MIT License | transitive |
| `filelock` | 3.32.0 | MIT | transitive |
| `greenlet` | 3.5.4 | MIT AND PSF-2.0 | transitive |
| `h11` | 0.16.0 | MIT License | transitive |
| `httpcore` | 1.0.9 | BSD-3-Clause | transitive |
| `httptools` | 0.8.0 | MIT | transitive |
| `humanfriendly` | 10.0 | MIT License | transitive |
| `humanize` | 4.16.0 | MIT | transitive |
| `idna` | 3.18 | BSD-3-Clause | transitive |
| `iniconfig` | 2.3.0 | MIT | transitive |
| `itsdangerous` | 2.2.0 | BSD License | transitive |
| `Jinja2` | 3.1.6 | BSD License | transitive |
| `jiter` | 0.16.0 | MIT | transitive |
| `jmespath` | 1.1.0 | MIT License | transitive |
| **`jwcrypto`** | 1.5.8 | LGPL-3.0-or-later | transitive |
| `kombu` | 5.5.4 | BSD License | transitive |
| `license-expression` | 30.4.4 | Apache-2.0 | transitive |
| `Mako` | 1.3.12 | MIT License | transitive |
| `markdown-it-py` | 4.2.0 | MIT License | transitive |
| `MarkupSafe` | 3.0.3 | BSD-3-Clause | transitive |
| `mdurl` | 0.1.2 | MIT License | transitive |
| `msgpack` | 1.2.1 | Apache-2.0 | transitive |
| `multidict` | 5.2.0 | Apache Software License | transitive |
| `packageurl-python` | 0.17.6 | MIT License | transitive |
| `packaging` | 26.2 | Apache-2.0 OR BSD-2-Clause | transitive |
| `pillow` | 12.3.0 | MIT-CMU | transitive |
| `pip-api` | 0.0.34 | Apache Software License | transitive |
| `pip-requirements-parser` | 32.0.1 | MIT | transitive |
| `platformdirs` | 4.11.0 | MIT | transitive |
| `pluggy` | 1.6.0 | MIT License | transitive |
| `prometheus_client` | 0.25.0 | Apache-2.0 AND BSD-2-Clause | transitive |
| `prompt-toolkit` | 3.0.28 | BSD License | transitive |
| `py-serializable` | 2.1.0 | Apache Software License | transitive |
| `pyasn1` | 0.6.4 | BSD-2-Clause | transitive |
| `pycparser` | 3.0 | BSD-3-Clause | transitive |
| `pydantic_core` | 2.46.4 | MIT | transitive |
| `Pygments` | 2.20.0 | BSD-2-Clause | transitive |
| `pyparsing` | 3.3.2 | MIT | transitive |
| `python-dateutil` | 2.9.0.post0 | Apache Software License; BSD License | transitive |
| `python-engineio` | 4.13.3 | MIT | transitive |
| `requests-toolbelt` | 1.0.0 | Apache Software License | transitive |
| `rich` | 15.0.0 | MIT License | transitive |
| `rsa` | 4.9.1 | Apache Software License | transitive |
| `ruamel.yaml` | 0.17.40 | MIT License | transitive |
| `ruamel.yaml.clib` | 0.2.15 | MIT License | transitive |
| `s3transfer` | 0.11.5 | Apache Software License | transitive |
| `sanic` | 21.12.2 | MIT License | transitive |
| `Sanic-Cors` | 2.2.0 | MIT License | transitive |
| `sanic-routing` | 0.7.2 | MIT License | transitive |
| `simple-websocket` | 1.1.0 | MIT License | transitive |
| `six` | 1.17.0 | MIT License | transitive |
| `sniffio` | 1.3.1 | Apache Software License; MIT License | transitive |
| `sortedcontainers` | 2.4.0 | Apache Software License | transitive |
| `starlette` | 1.3.1 | BSD-3-Clause | transitive |
| `tomli_w` | 1.2.0 | MIT License | transitive |
| `tornado` | 6.5.7 | Apache Software License | transitive |
| **`tqdm`** | 4.69.0 | MPL-2.0 AND MIT | transitive |
| `typing-inspection` | 0.4.2 | MIT | transitive |
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
| **`ticketing-ui@0.1.0`** | **UNLICENSED** ⚠ *scan output, pre-fix* |

⚠ **That last row is the scan as it ran, and it is why the scan was worth running.** The source
manifest has since been corrected — `channels/ticketing-ui/package.json` and
`channels/REST_webchat/package.json` now declare `"license": "Apache-2.0"` — but the `grm_ui`
container still carries the package.json baked in at image build, so **this row will not change
until the image is rebuilt**. Re-run the npm scan after the next `docker compose build grm_ui` and
the row should read `Apache-2.0`. Recorded as-scanned rather than hand-corrected, because a
generated report that quietly disagrees with the command that produced it is not evidence.
