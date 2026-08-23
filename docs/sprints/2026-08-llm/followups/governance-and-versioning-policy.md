# Follow-up — governance model and release/versioning policy (DPG indicator 8)

> **Raised:** 2026-08-18, closing DPG-05.
> **Deferred from:** [DPG-05](../01-licensing-and-governance-spec.md#dpg-05) §Scope gate — deliberately, on the spec's own recommendation.
> **Blocked on:** the DPG consultant's answer to **consultant-Q17**.
> **Status:** ⏸ blocked on an external answer · **Size:** S to write, M in ongoing commitment

---

## What was shipped, and what was not

DPG-05 shipped the four hygiene files that are uncontroversial and cheap:

| Shipped | |
|---|---|
| `SECURITY.md` | private disclosure channel, named recipient, response targets, scope boundaries |
| `CONTRIBUTING.md` | build/branch/test rules, pointing at the existing standards rather than restating them |
| `CODE_OF_CONDUCT.md` | Contributor Covenant 2.1 + a project-specific clause on grievance confidentiality |
| `.github/ISSUE_TEMPLATE/` + PR template | bug, feature, and a security **redirect** — the security path cannot land in a public issue |

**Not shipped, deliberately:**

1. **A governance model** — who decides what gets merged, how a maintainer is added or removed, how
   a decision is escalated, and what happens when the current maintainer stops.
2. **A release and versioning policy** — semantic versioning, tagged releases, a changelog, a
   supported-version window, and what "supported" obliges anyone to do.

## Why they were deferred rather than written

The four shipped files describe **what is already true**. These two would describe **commitments
nobody has agreed to**.

- A governance model that names decision-makers is a statement about an ADB-financed project whose
  **IP ownership is not yet determined** (DPG-03 / Q-01 — the request to ADB's Office of the General
  Counsel is still open). Writing "the maintainers decide" before knowing who owns the code invents
  an answer to a question that has been formally asked of someone else.
- A supported-version window is an ongoing obligation. Publishing "we patch the last two minor
  versions" for a platform with no funded maintenance line is exactly the kind of confident false
  claim engineering rule 9 exists to prevent — and a DPG reviewer can check it against the release
  history in one click.

**Whether the DPGA requires either is itself the open question** (consultant-Q17, in
[`docs/dpg/00_compliance_status.md`](../../../dpg/00_compliance_status.md) §5). Indicator 8 is
already assessed 🟢 mostly compliant on the strength of OpenAPI, OIDC/PKCE, migrated schema and
architectural pinning tests. Building process commitments to satisfy a requirement that may not
exist is the more expensive mistake.

## What to do when the answer arrives

**If the consultant says these are required:**

- [ ] `GOVERNANCE.md` — decision process, maintainer roles, how maintainers change, escalation path,
      and an honest statement of the current bus factor rather than an implied committee
- [ ] `VERSIONING.md` or a section in `CONTRIBUTING.md` — SemVer, what a breaking change means for
      each of the three schemas and the two API surfaces
- [ ] `CHANGELOG.md`, and git tags for the releases that have actually happened
- [ ] A supported-version window **only if someone has committed to honouring it**; if nobody has,
      say "best effort, no guarantee" and mean it
- [ ] Reconcile with `CLAUDE.md` §Git workflow — `main` as integration target — so a release process
      and the branch rule describe the same thing

**If the consultant says they are not required:** close this document with the answer and the date,
and leave the four shipped files as the indicator-8 evidence.

**Either way, revisit when DPG-03 resolves.** A governance model written before the ownership
determination is a guess; written after, it is a fact.

## Related

- [`../01-licensing-and-governance-spec.md#dpg-05`](../01-licensing-and-governance-spec.md#dpg-05) — the ticket and its scope gate
- [`../../../dpg/00_compliance_status.md`](../../../dpg/00_compliance_status.md) §2.5, §5 (consultant-Q17)
- [`../QUESTIONS.md`](../QUESTIONS.md) — live owner questions
- [`../PROGRESS.md`](../PROGRESS.md) — deviation log
