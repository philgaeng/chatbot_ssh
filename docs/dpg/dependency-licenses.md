# Dependency licence audit

**Status:** evidence pack — cited by the DPG assessment.
**Last updated:** 2026-09-15 — regenerated against the images CI built and staging runs (`app`/`ui` at commit `f436f89`): licences, CVEs and image digests in one pass. No licence moved; the CVE picture split — Python improved, the web framework now carries two critical advisories. The nightly licence scan has run for real, and the CVE scan beside it was found writing nothing.

> **Regenerated 2026-09-15** — licences, CVEs and image digests in one pass, so this file carries **one
> date**. **Serves DPG indicator 2** (use of an approved open licence) and, for the container-image set,
> indicator 4 (platform independence).
>
> **What the re-run changed, and what it did not.**
>
> - ✅ **The compliance claim is unchanged and re-measured:** **zero non-OSI, zero unknown**, across all
>   four sets. **Same 149 packages** — nothing added, nothing removed.
> - ✅ **14 Python packages moved version since 2026-09-03 and no licence moved with them** — the result
>   the pin-drift check exists to make boring.
> - ⭐ **The scheduled licence scan has now run, on a deployed host, eleven nights running** — and it
>   flags exactly the five weak-copyleft packages this report dispositions by hand. The control this file
>   has promised since August is producing evidence. See [Staying true](#staying-true).
> - ⛔ **But the CVE scan scheduled beside it has written nothing on any of those nights** — a
>   persistence defect that discards the whole night's findings. See [Staying true](#staying-true).
> - 🔴 **The web framework's findings got worse, not better.** `next` now carries **11 advisories, two
>   of them critical** — one an unauthenticated remote-code-execution flaw in the image optimisation
>   endpoint, which is enabled and publicly reachable. See
>   [Known vulnerabilities](#known-vulnerabilities--measured-2026-09-15).
> - ✅ **Python CVEs fell from 6 advisories to 4**, and every remaining one is either unreachable or a
>   free bump.
> - ⚪ npm licences (16 packages) are identical. Three of the four base images have moved to newer
>   upstream builds under the same tag; **none changed licence**.
>
> **This report is generated. Re-run it rather than editing the rows by hand** — a hand-patched
> generated report is exactly the drift this file exists to remove.
>
> **This is the authoritative inventory, and it is the only one.** [`00_compliance_status.md`](00_compliance_status.md)
> cites this file and keeps no mirror of it. Where anything disagrees with this file, this file is right —
> it was produced from the resolved trees that actually ship, not from the manifests.

## How this was produced

⭐ **Changed in this run: the scans ran inside the images that ship, not a development build.** Since
2026-09-06 CI builds and publishes every image, and staging pulls them rather than building on the host.
This report scanned **exactly those images** — `app` and `ui` at commit `f436f89`, pulled from the
registry by digest — so there is no longer a gap between "the tree we scanned" and "the tree that runs".

| Image scanned | Registry digest |
|---|---|
| `app:f436f89` (every Python service) | `sha256:905071205a293943ff8d1271cad92329341cb4bd6181a7e8727994b0efb5a05f` |
| `ui:f436f89` (the officer portal) | `sha256:0c68bf6fa67ac2e3273a3d1aed854adcb2e3f699ec9a6844a6195eb861c6e319` |

```bash
# Python licences — inside the shipped image
docker run --rm --entrypoint sh <registry>/app:<sha> -c "pip-licenses --format=json"

# Python CVEs — same image, what is actually installed
docker run --rm --entrypoint sh <registry>/app:<sha> -c "pip-audit --format json"

# npm licences — production tree, inside the shipped image
docker run --rm --entrypoint sh <registry>/ui:<sha> -c "cd /app && npx license-checker --production --json"

# base images — the digests the staging host is running
docker image inspect <image> --format '{{index .RepoDigests 0}}'

# npm CVEs — ⚠ NOT in-container: the shipped image has no lockfile (ENOLOCK)
cd channels/ticketing-ui && npm audit --omit=dev --json
```

⚠ **The last command is the one exception to "in the shipped image", and it is not cosmetic.** `npm
audit` requires a lockfile, which a production image deliberately does not ship, so it measures the
**declared graph** rather than the **installed tree**. The image's `node_modules` holds **10 entries**;
the lockfile's production graph is larger. Findings from that command are checked against the image
before being treated as shipped exposure — see the vulnerability section.

⚠ **Licence scans read the resolved tree, not the manifests.** Reading manifests would have missed **95
of the 129** Python packages — including the `jwcrypto` LGPL finding, and both LGPL libvips binaries on
the npm side. **None of those three is anyone's declared dependency**; they arrive transitively, and a
licence obligation does not care how a package got there.

### ⚠ There is one Python image, not two

One `Dockerfile` at the repo root serves every Python service and installs *both* manifests into one
image:

```dockerfile
COPY requirements.txt requirements.grm.txt /app/
RUN pip install -r /app/requirements.txt && pip install -r /app/requirements.grm.txt
```

So the split below is by **manifest**, recovered by parsing each requirements file — not by image, which
cannot distinguish them.

## Summary

| Set | Packages | Non-OSI | Unknown | Needs a disposition |
|---|---|---|---|---|
| Python — declared (both manifests) | 34 | 0 | 0 | 2 |
| Python — transitive | 95 | 0 | 0 | 4 |
| npm — production tree | 16 | 0 | 0 | 2 + 1 tool artefact |
| Container images | 4 | 0 | 0 | 1 |
| **Total** | **149** | **0** | **0** | **10** |

⚠ **34, not 35.** `pip-licenses` is declared in `requirements.grm.txt` but **excludes itself and its own
dependencies from its output by default**, so it cannot appear in its own report. It is Apache-2.0
(verified from its metadata) and it is a scanning tool, not a runtime dependency of the platform.

**No package in any tree carries an unknown, unparseable or non-OSI licence.** Indicator 2 is answerable
on the dependency tree; the remaining gap is the repository's own licence choice, which is applied and
provisional pending the consultant — see `NOTICE`.

## Dispositions

Ten entries carry conditions beyond simple attribution. None blocks the submission; each is recorded
so a reviewer does not have to rediscover it.

| Package | Licence | Disposition |
|---|---|---|
| `psycopg2-binary` | LGPL-3.0 **with linking exception** | **Keep.** Unmodified library dependency, dynamically linked, standard across the Python ecosystem. The linking exception exists for exactly this use. Raised with the consultant as **Q-02-02** in case the DPGA reads it differently. |
| `jwcrypto` | LGPL-3.0-or-later | **Keep, and note it was not previously known.** Arrives transitively via the Keycloak JWT path. No linking exception, but it is an unmodified, dynamically-imported Python library — the LGPL's own §5 covers this. ⚠ **The hand-written inventory missed it entirely**, which is the clearest argument for this report existing. |
| `bidict` · `certifi` | MPL-2.0 | **Keep.** File-level weak copyleft; unmodified, not redistributed in modified form. `certifi` is the CA bundle every Python HTTP client uses. |
| `tqdm` | MPL-2.0 AND MIT | **Keep.** Same reasoning; the MPL portion is unmodified. |
| `email-validator` | The Unlicense | **Keep.** Public-domain dedication, OSI-approved. ⚠ Not to be confused with npm's `UNLICENSED`, which means *no licence declared* — the opposite. |
| `@img/sharp-libvips-linux-x64` · `-linuxmusl-x64` *(amd64)* · `-linux-arm64` · `-linuxmusl-arm64` *(arm64)* | LGPL-3.0-or-later | **Keep.** ⚠ **The images are multi-architecture and the binaries are per-architecture:** the tables below were scanned on the amd64 build; the arm64 build staging runs carries the `-arm64` pair instead — verified from the image's files, same version `1.2.4`, same licence. Prebuilt libvips binaries pulled in by `sharp`, which Next.js uses for image optimisation. Shipped unmodified as separate shared objects and dynamically loaded — the LGPL-compliant pattern. ⚠ Also absent from the hand-written inventory: `sharp` is nobody's declared dependency, it is a Next.js transitive. |
| `ticketing-ui@0.1.0` | reported `UNLICENSED` | **Explained, and partly fixed — but the row will not change.** Our own manifest declared no licence at all, contradicting the repository's Apache-2.0 `LICENSE`; `channels/ticketing-ui/package.json` and `channels/REST_webchat/package.json` now both declare `"license": "Apache-2.0"`. ⚠ **`license-checker` still reports `UNLICENSED`, and always will:** it hard-codes that value for any package with `"private": true` and ignores the `license` field entirely. Verified after rebuilding the image — the record it emits is `{"licenses": "UNLICENSED", "private": true}`. So this row is a **tool artefact for an unpublished package, not a finding**: our own code's licence is `LICENSE` + the per-file SPDX headers, and the manifest now states it too for anyone reading the file. |
| `redis:8.10` | RSALv2 / SSPLv1 / **AGPLv3** (tri-licensed) | **Keep, elected under AGPLv3** — the one OSI-approved option of the three. Runs as an unmodified upstream image behind a network boundary; no Redis source is conveyed, so AGPLv3 imposes nothing on this repository or a downstream fork. Consultant question **Q-02-02** asks whether AGPL anywhere in the stack is a problem for ADB/DOR procurement; Valkey (BSD-3-Clause) is the costed fallback. |

## The Rasa licence question — closed

The source narrative flagged Rasa as a possible week-one indicator-2 emergency. **Resolved
mechanically, from the resolved tree:**

| Package | Version | Licence | What it actually is |
|---|---|---|---|
| `rasa-sdk` | 3.6.2 | Apache-2.0 | The only Rasa-family package installed, and **Apache-2.0, so the licence question is closed either way**. There is no Rasa server, no Rasa NLU and no TensorFlow anywhere in the tree — verified against the resolved tree. ⚠ **It is not merely a type shim**: 49 modules import it, `BaseFormValidationAction` inherits `FormValidationAction`, and the orchestrator executes `action.run(...)`. Removing it is a refactor, not a deletion — see §Known vulnerabilities. |

Nothing further is owed on this. The alarm cost an hour, not a week.

## Container images

Digests as **running on the staging host**, 2026-09-15 — the environment the scans above describe.

| Image | Resolved digest | Licence | Since 2026-09-03 |
|---|---|---|---|
| `postgres:15` | `sha256:29342cb52157b098821961d2c14eec3c019071f56a5d559e990cf07cf541ea9b` | PostgreSQL Licence (OSI-approved) | ⚪ new upstream build, same major |
| `redis:8.10` | `sha256:298e5b3bc566bade82f46ad5511777a4a07a294097ce16ada2f6a42be5239df5` | AGPLv3 at our election — see dispositions | ⚪ new upstream build — `8.10.1`, same tri-licence |
| `nginx:stable` | `sha256:1a9ab83e2892b75773978e8d91f42a7a2a0d8bb704959a51ff17c0377481973d` | BSD-2-Clause | ⚠ **moved minor** — `1.30.0` on staging |
| `quay.io/keycloak/keycloak:26.0.7` | `sha256:4388e2379b7e870a447adbe7b80bd61f5fbf04e925832b19669fda4957f05a81` | Apache-2.0 | ✅ identical |

⚠ **Three of four digests moved in twelve days, and that is the pins working as designed — not drift.**
`redis:8.10` pins MAJOR.MINOR, so a patch release arrives under it; `postgres:15` and `nginx:stable` are
the two documented exceptions whose licences are stable across the range the tag spans. **No licence
moved.** ⚠ But `nginx:stable` is the loosest pin in the stack, and it has a practical cost beyond
licensing: a development machine pulled months ago runs `1.28`, staging runs `1.30`, and **a directive
valid on one can be refused by the other** — which has already happened once while hardening staging's
configuration.

### The pin-drift check

Container images were **a fourth dependency set nobody was auditing, and the only place a licence
actually drifted.** `redis:7` pinned the major only; Redis 7.2 was BSD-3-Clause and 7.4 moved to
RSALv2/SSPLv1. The tag followed upstream across that boundary with nobody editing the file.

`tests/repo/test_image_pins.py` fails the build when an image is pinned looser than MAJOR.MINOR, unless
it is in an explicit exception list that must state why the licence is stable across the range the tag
spans. `postgres:15` and `nginx:stable` are the two current exceptions. It also asserts Compose and CI
declare the *same* image, so CI cannot test a different Redis than production runs.

## Staying true

A dated audit is stale the next time anybody adds a dependency, and indicator 2 is a claim that has to
hold continuously. The licence and CVE scans are therefore **scheduled**, not pre-submission artefacts:
`ops/security.py` runs `licence_scan()` (nightly, 01:50) and `dependency_scan()` (`pip-audit`, nightly,
01:30), both writing to `ops.dependency_findings`. Report-only; neither blocks a deploy. Classification
lives in `ops/licences.py` — pure logic, unit-tested — and anything unrecognised surfaces as a **high**
finding rather than passing silently.

### ✅ The licence scan has run on a deployed host — eleven nights, and it agrees with this report

**Measured on the staging host, 2026-09-15**, from the monitor's own tables:

| | |
|---|---|
| Runs recorded | **11 nights**, 2026-09-04 → 2026-09-14, every one completing |
| Latest result | `warn · {"scanned": 129, "flagged": {"warn": 5}}` |
| Open findings | `psycopg2-binary` (LGPL) · `jwcrypto` (LGPL-3.0-or-later) · `certifi`, `bidict` (MPL-2.0) · `tqdm` (MPL-2.0 AND MIT) |

⭐ **The five it flags are exactly the five this report dispositions by hand, and the 129 it scans is the
129 this report counts.** Two independent routes to the same answer — a person running commands, and a
scheduled job on a server — is what turns indicator 2 from a dated artefact into a continuous control.
`warn` is the designed severity for weak copyleft: flag for review, do not fail the build.

⚠ **Scope of that claim:** staging, not DOR production, which has no `ops` container at all.

### ⛔ The CVE scan beside it has saved nothing on any of those nights

Found while reading the same tables for this regeneration, and **the more important half of this
section.**

| | |
|---|---|
| Runs recorded | **11 nights**, every one ending `warn` |
| Message | *"persist failed: … UniqueViolation … `uq_dep_finding` … `(pip-audit, ecdsa, PYSEC-2026-1325)` already exists"* |
| `pip-audit` rows in `ops.dependency_findings` | **zero** — while a manual run finds 4 distinct advisories |

**The mechanism.** In the shipped image `pip-audit` reports **every advisory twice** (verified: all four
appear as duplicated `(package, advisory)` pairs). The scan upserts findings one at a time inside a
single transaction, the second copy violates the table's uniqueness key, and **the whole night's results
are rolled back.** The check then records `warn` — which, beside a licence scan also recording `warn`,
looks like a monitor doing its job.

⚠ **This is the second time the monitor has failed silently rather than loudly**, from an unrelated cause:
in August it authenticated with the wrong database role and reported `healthy` while writing nothing. A
monitor whose failure looks like a finding is the one control you cannot audit from its own output — so
**treat this report's CVE section as the measurement, and the nightly scan as not yet working**, until it
is fixed and has written a real row. The fix is small (de-duplicate before upserting, and a test with a
duplicated advisory); it is queued, not done.

### The monitor found things nobody asked it about

Reading its tables for this report also surfaced two findings outside this file's scope, recorded here
because they are the best evidence available about whether the monitor is *read*:

- the **certificate check** — which on staging is configured to watch the **production** hostname —
  reported production's TLS certificate as critical for ten consecutive nights, then expired. **It
  expired on 2026-09-13**; verified from outside on 2026-09-15.
- the **backup check** has been critical on every night: no backup has run on the staging host.

⭐ **Neither was acted on, because neither reached a person.** The scans work; the path from a finding to
someone who acts on it is the part not yet built. Assessed in
[`00_compliance_status.md`](00_compliance_status.md) indicators 7 and 8.

## Python — declared dependencies (34)

| Package | Version | Licence | Declared in |
|---|---|---|---|
| `alembic` | 1.20.0 | MIT | chatbot + GRM |
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
| `pydantic` | 2.13.5 | MIT | chatbot |
| `pydantic-settings` | 2.15.0 | MIT | chatbot |
| `pytest` | 9.1.1 | MIT | GRM/ops |
| `python-dotenv` | 1.1.1 | BSD License | chatbot |
| `python-jose` | 3.5.0 | MIT License | GRM/ops |
| `python-keycloak` | 7.1.1 | MIT License | GRM/ops |
| `python-multipart` | 0.0.32 | Apache-2.0 | chatbot |
| `python-socketio` | 5.16.4 | MIT | chatbot |
| `pytz` | 2026.3.post1 | MIT License | chatbot |
| `pyvips` | 3.2.0 | MIT License | chatbot |
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
| `anyio` | 4.15.1 | MIT | transitive |
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
| `filelock` | 3.32.6 | MIT | transitive |
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
| `jiter` | 0.17.0 | MIT | transitive |
| **`jwcrypto`** | 1.6.0 | LGPL-3.0-or-later | transitive |
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
| `pip_api` | 0.0.35 | Apache Software License | transitive |
| `pip-requirements-parser` | 32.0.1 | MIT | transitive |
| `platformdirs` | 4.11.8 | MIT | transitive |
| `pluggy` | 1.6.0 | MIT License | transitive |
| `prometheus_client` | 0.26.0 | Apache-2.0 AND BSD-2-Clause | transitive |
| `prompt-toolkit` | 3.0.28 | BSD License | transitive |
| `py-serializable` | 2.1.0 | Apache Software License | transitive |
| `pyasn1` | 0.6.4 | BSD-2-Clause | transitive |
| `pycparser` | 3.0 | BSD-3-Clause | transitive |
| `pydantic_core` | 2.46.5 | MIT | transitive |
| `Pygments` | 2.21.0 | BSD-2-Clause | transitive |
| `pyparsing` | 3.3.2 | MIT | transitive |
| `python-dateutil` | 2.9.0.post0 | Apache Software License; BSD License | transitive |
| `python-engineio` | 4.14.0 | MIT | transitive |
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
| **`tqdm`** | 4.70.1 | MPL-2.0 AND MIT | transitive |
| `typing_extensions` | 4.16.0 | PSF-2.0 | transitive |
| `typing-inspection` | 0.4.4 | MIT | transitive |
| `tzdata` | 2026.4 | Apache-2.0 | transitive |
| `tzlocal` | 5.4.4 | MIT | transitive |
| `ujson` | 6.0.0 | BSD-3-Clause AND TCL | transitive |
| `urllib3` | 2.7.0 | MIT | transitive |
| `uvloop` | 0.22.1 | Apache Software License; MIT License | transitive |
| `vine` | 5.1.0 | BSD License | transitive |
| `websockets` | 10.4 | BSD License | transitive |
| `wsproto` | 1.3.2 | MIT | transitive |

## npm — production tree (16)

`--production` only: the dev toolchain (TypeScript, ESLint, Vitest, Tailwind, Playwright) does not ship
and is out of scope for redistribution. Sixteen packages is the entire runtime tree — there is no
component library, state-management library, charting library or analytics SDK.

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

## Known vulnerabilities — measured 2026-09-15

Distinct from the licence question above, and recorded here because a reviewer's first question about
any repository is its vulnerability count.

⚠ **Where a count comes from matters, so this one is stated.** The working repository has been
**private since 2026-09-04**; the public copy will be a generated release, cut when a build reaches
production, and none has been cut yet. So there is no public GitHub alert count to quote, and the
private one is measured against `main`, which is months stale. **Measured here instead**, against the
images that ship:

| Set | 2026-09-03 | **2026-09-15** | Notes |
|---|---|---|---|
| Python (`pip-audit`, inside `app:f436f89`) | 6 advisories, 5 packages | ✅ **4 advisories, 4 packages** | `ecdsa` ⚠ no fix released · `sanic-cors` · `python-dotenv` → 1.2.2 · `setuptools` → 83.0.0. `wheel` is gone |
| npm, production graph (`npm audit --omit=dev`) | 4 high | 🔴 **1 critical · 3 high · 1 moderate** | `next` **critical** (11 advisories) · `postcss` · `nanoid` · `sharp` · `baseline-browser-mapping` |

### 🔴 The framework row is the one to act on — and part of it is reachable today

`next@16.2.6` is the officer portal's framework and **it ships**. Its advisories grew from **nine** to
**eleven**, and the two new ones are **critical**:

| Advisory | Applies here? |
|---|---|
| **Unauthenticated remote code execution in the Image Optimization API when AVIF files are used** | ⛔ **The endpoint is live.** The portal leaves Next's image optimiser at its default (enabled), the reverse proxy forwards `/_next/`, and on the staging host `GET /_next/image?url=/next.svg&w=64&q=75` is answered by the optimiser itself — *"url parameter is valid but image type is not allowed"*. That request was benign; **the flaw was not exercised and exploitability has not been assessed** |
| Unauthenticated remote code execution on Windows-hosted servers | ✅ No — every host is Linux |
| Plus the nine carried since 2026-09-03 | a middleware/proxy bypass in App Router, two server-side request forgeries, two denial-of-service issues, cache confusion, and disclosure of internal Server Function endpoints |

⭐ **The portal does not use the image optimiser at all** — there is no `next/image` import anywhere in
the application. So the reachable critical has a **same-day mitigation with no functional change**
(`images: { unoptimized: true }`), independent of the upgrade; and the upgrade itself — to `next@16.3.5`,
which npm names as the fix — takes `postcss`, `sharp` and its new libheif advisories with it.

⚠ **This row has been "the one to act on" since 2026-09-03, and in twelve days it became worse.** It is
the plainest evidence in this pack that a listed remediation is not a scheduled one.

**The other rows:**

- **`postcss`, `nanoid`** — four and two advisories respectively, arriving under `next` in the lockfile
  graph. ⚠ **Neither is in the shipped image** — verified again: `ui`'s `node_modules` holds **10
  entries** and contains neither. Lockfile findings, not shipped exposure.
- **`sharp`** — the libvips inheritance, now joined by two libheif advisories. It **is** shipped (it
  backs the image optimiser above), and its fix is the same framework bump.
- **`baseline-browser-mapping`** — new, moderate, a build-time browser-support table. Not in the shipped
  image.

⚠ **Method, stated because it matters.** `pip-audit` runs **inside the shipped image**. `npm audit` needs
a lockfile, which the image does not ship, so it measures the **declared graph** — which is why every
npm row above had to be checked against the image by hand.

⭐ **The transferable point, and it is the same one this file makes about licences:** a count is not a
tree. On 2026-09-03 the npm count held still while every finding behind it changed; on 2026-09-15 it rose
by one while its severity jumped a class. **Re-run the command; do not re-read the number.**

### ⚠ Two Python findings come from `rasa-sdk`'s tree — and neither the fix nor the risk is what it looks like

`sanic-cors` arrives through `rasa-sdk` (`wheel`, its other build-tooling finding, has left the image
since the last run). The tempting conclusion is that removing a "type shim" removes findings cheaply.
**Both halves of that are wrong.**

**The risk is near zero.** `sanic-cors` is CORS middleware for a Sanic web server — `sanic` is never
imported by any module in this repository, so the code never executes. **A finding in a count, not
exposure in a system.**

**The removal is a refactor, not a deletion.** `rasa-sdk` is imported by **49 modules**. The surface
used is `Tracker`, `CollectingDispatcher`, `Action`, `DomainDict`, six event constructors — **and
`FormValidationAction`, which `BaseFormValidationAction` inherits** and whose `run()` the orchestrator
invokes. Replacing it means reimplementing a slot-validation loop that the live chatbot's intake path
runs on. **Do not do this for the CVEs.** If `rasa-sdk` is ever removed it should be for its own
reasons, with a characterization net over the intake path first.

### The remaining Python rows

- **`ecdsa`** — arrives via `python-jose`, the Keycloak JWT path. ⚠ **No fix version has been
  published**, so it cannot be closed by a bump: mitigate, or move to a different JWT library.
- **`python-dotenv`, `setuptools`** — ordinary version bumps, no downstream constraint.

### ⏭ What this section owes, ranked

| | Item | Why it is where it is |
|---|---|---|
| ⛔ | **Switch off the unused image optimiser** | A critical, unauthenticated RCE advisory on an endpoint that is live, public and serves nothing the portal uses. One configuration line, no functional change |
| 🔴 | **Bump `next` to 16.3.5** | Eleven advisories in a framework that ships and faces officers; takes `postcss`, `nanoid` and `sharp` with it |
| 🔴 | **Fix the nightly CVE scan so it saves what it finds** | Until then every finding here was found by a person running a command, and the next one will be too |
| 🟠 | **`ecdsa` — mitigate or move off `python-jose`** | No fix exists; it sits on authentication |
| 🟡 | **`python-dotenv`, `setuptools`** | Free bumps. Do them with anything else |
| ⚪ | **`sanic-cors`** | **Deliberately last.** Unreachable, and doing it first is how a remediation plan optimises the count over the risk |
