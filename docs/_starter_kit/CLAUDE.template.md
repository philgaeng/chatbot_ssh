# CLAUDE.md — ‹Project name›

> Root instruction file for AI coding agents. **Locked architecture decisions live here; craft rules live in `docs/engineering/`.** Keep this file short — under ~200 lines. Everything long belongs in a specification that this file points at. A root file that grows past a few screens stops being read in full, and the rules at the bottom stop being followed.

---

## ⚡ READ THIS BEFORE ANY CODE DECISION

| File | Read for |
|---|---|
| **→ `docs/‹PROGRESS›.md`** | Current build state, deviations, commit log |
| **→ `docs/‹TODO›.md`** | Open gaps, next features, tech debt |
| **→ `docs/engineering/00_index.md`** | **HOW we build** — binding on every change |
| **→ `docs/‹deployment/RUNBOOK›.md`** | Build, start, migrate, seed, debug |
| **→ `docs/README.md`** | Index of the full specification tree |

The build log says what was *actually built*. The backlog says what's next. `docs/engineering/` says **how to build it**. This file holds the locked **architecture** — the decisions the craft rules follow from. Where this file and a live specification disagree on a locked decision, this file wins; on *how* to implement it, `docs/engineering/` wins.

---

## 🔒 BUILD & RUN — ‹the one supported way›

**FILL:** the single supported way to build and run, stated absolutely, with the failure mode of doing it otherwise.

> *Worked example:* "**Always build and run with Docker Compose — never on the host.** Do not `pip install`, `npm run build`, or run migrations natively to build or serve. Native runs cause port, version, and schema drift. Host CLIs are for **reading only**; anything that builds an image, starts a service, or mutates the database goes through Docker."

---

## ⚠️ SUPERSEDED DECISIONS

**FILL:** as the project evolves, decisions in this file get superseded by what was actually built. Do not silently edit them away — keep a table, so an agent that has read an old version, or found an old reference elsewhere, is corrected.

| This file said | As-built reality | Authoritative spec |
|---|---|---|
| ‹old decision› | ‹what was built› | ‹path› |

---

## Project overview

**FILL:** two or three sentences — what this system does and for whom. Repository, main branch, active branch, and any branch that must not be touched.

---

## Git workflow

**Rule:** ‹the integration branch› is never a working branch. Work happens on feature branches and arrives by pull request. **FILL:** branch naming, review requirement, and how to recover if commits land in the wrong place.

---

## Architecture — locked

**FILL:** the decisions that must not be re-litigated by an agent mid-task. Keep each to a few lines and link out for detail. Typical set:

- **Services and their boundaries** — what each owns, which are stable and need care.
- **Data ownership** — which component owns which schema; what may cross a boundary and what may not. **Make the permitted set closed and pin it with a test.**
- **The sensitive-data rule** — state it absolutely: *what* must never be stored where, and *why*. Name the pinning test.
- **Integration points** — how components talk (HTTP contract, queue, webhook), and which calls must never be reimplemented locally.
- **Authentication** — the mechanism and where it is configured.

**Rule — when you amend a rule here, move its reason with it.** A rule stripped of its reason reads as arbitrary fiat, gets quietly violated, and cannot be defended in review.

---

## Conventions

**FILL:** language, formatting, identifier and datetime policy, environment-variable handling, and the commit convention. Everything deeper belongs in `docs/engineering/`.

---

## Where new code goes

**FILL:** a short map. `‹path›` → ‹what belongs there›. This one table prevents most misplaced-file pull requests.
