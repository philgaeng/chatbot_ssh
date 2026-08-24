# Security Policy

## Why this file is not boilerplate

This platform receives **grievances from people affected by road construction in Nepal**, and one of
its intake streams handles **SEAH disclosures** — reports of sexual exploitation, abuse and
harassment. A report may name a survivor, a witness, or an accused person. Some complainants are
anonymous precisely because being identified is dangerous for them.

That changes what a responsible disclosure looks like:

- A vulnerability report must **never** be filed in a public issue tracker. A public issue that
  names a data-exposure path is a map for anyone who wants the data.
- Testing must **never** involve reading, exfiltrating or modifying real grievance data. The
  platform is in scope; the grievances inside it are not.

Please read the scope section below before you start looking.

---

## Reporting a vulnerability

**Email: contact@grm-chatbot-nepal.org**

> ⚠ **This mailbox is a placeholder pending public release of the repository.** It is recorded here
> as the single, private disclosure route; it must be live and monitored before the repository is
> published. Until then, reports may also reach the maintainer through the contact address on the
> GitHub account that owns the repository. This caveat exists rather than a silently dead address —
> see the project's rule against unverified claims
> ([`docs/engineering/00_engineering_index.md`](docs/engineering/00_engineering_index.md), rule 9).

Please include, as far as you can:

1. What you found, and where — file, endpoint, or service
2. How to reproduce it, on a local Docker stack (see [`docs/deployment/DOCKER.md`](docs/deployment/DOCKER.md))
3. What an attacker gets — read access, write access, privilege escalation, data exposure
4. Whether you believe it has been exploited
5. How you would like to be credited, or that you would prefer not to be

**Do not open a GitHub issue, a pull request, or a discussion for a security report.** If you have
already done so, email us and we will take it from there.

### What happens next

| Stage | Target |
|---|---|
| We acknowledge your report | **3 working days** |
| We give you an initial assessment — is it a vulnerability, how severe, what we intend to do | **10 working days** |
| We keep you updated | at least every **14 days** until it is resolved or closed |
| Fix released for a confirmed high-severity issue | as fast as we can; we will tell you the target date in the assessment |

These are targets, not guarantees. This is a small team on a public-sector project, not a
24/7 security operation, and saying so is more useful to you than a promise we would miss.

### Coordinated disclosure

We ask that you give us **90 days** from acknowledgement before publishing, and we will work to be
faster than that. If we cannot fix an issue in 90 days we will tell you why and agree a date with
you rather than let the clock run out silently. If a vulnerability is being actively exploited, tell
us and we will move immediately — that case overrides the schedule above.

We will credit reporters who want credit, in the release notes and in this file's history.

---

## Scope

### In scope — please do test

- The application code in this repository: `backend/`, `ticketing/`, `ops/`, `channels/`
- Authentication and authorization: Keycloak OIDC integration, JWT verification
  (`ticketing/auth/`), role and jurisdiction gates on API routes
- The API surfaces: the grievance API (`:5001`), the ticketing API (`:5002`), the orchestrator
  (`:8000`), and the Next.js officer UI (`:3001`)
- The PII boundary: anything that would let `ticketing.*` learn complainant PII, or let a caller
  decrypt without going through the authenticated, audited grievance endpoint
- **SEAH access isolation** — any path that reveals a sensitive-workflow ticket to a role not cast
  on it is a high-severity finding, and we want to hear about it first
- Container and deployment configuration in `docker-compose*.yml` and `deployment/`
- Dependency vulnerabilities not already reported by our nightly `pip-audit` and licence scan

### Out of scope — please do not

- **Any production or staging deployment.** Do not test against `grm-chatbot.dor.gov.np` or
  `nepal-gms-chatbot.facets-ai.com`. Run a local Docker stack instead; it takes one command.
- **Real grievance data, in any environment.** Do not read, copy, retain or publish complainant
  narratives, contact details, attachments, or SEAH reports. If you encounter real data by accident
  while reproducing a bug, stop, do not save it, and tell us what you saw in general terms.
- Denial of service, load testing, spam or brute-force against any hosted instance
- Social engineering of project staff, government officials, contractors or complainants
- Physical access attempts
- Findings that require an already-compromised officer device or an already-stolen credential
- Reports from an automated scanner with no demonstrated impact, and issues in third-party services
  we merely consume (report those upstream)

### Known and accepted

Some weaknesses are already documented and tracked rather than unknown. Reporting them again is
welcome but will be closed as known:

- Grievance text is sent to a third-party model provider for classification, summarisation and
  translation; deterministic PII redaction at that boundary is specified and **not yet built**
  ([`docs/sprints/2026-08-llm/04-pii-redaction-spec.md`](docs/sprints/2026-08-llm/04-pii-redaction-spec.md))
- Celery task payloads and some log lines carry unredacted grievance text (same sprint, DPG-34)
- The partial-controls list in
  [`docs/deployment/13_security.md`](docs/deployment/13_security.md) §13

If you find something in that list that is **worse than we have described**, that is a report we
very much want.

---

## Handling of your report

- Reports go to a private mailbox, not a ticket queue visible to officers or implementing-agency
  staff.
- We will not share your identity outside the maintainer team without your permission.
- If a report reveals that real complainant data was exposed, we will follow the incident-response
  procedure in [`docs/deployment/19_incident_response.md`](docs/deployment/19_incident_response.md),
  which may require us to notify the implementing agency and affected data subjects. We will tell you
  when that happens.

  > ⚠ **Be aware of what that procedure does and does not yet commit us to.** Detection, containment
  > and evidence handling are written down and were verified against the running system. **Three
  > decisions are still blank** — who declares a breach, who is notified on what clock, and how a
  > survivor is told in a SEAH case — because they belong to the implementing agency, not to us. They
  > are held on an interim basis by the maintainer. We would rather you knew that than discover it
  > after reporting.

---

## For maintainers

Security architecture, the control inventory, and the fail-closed guarantees are documented in
[`docs/deployment/13_security.md`](docs/deployment/13_security.md). Key and secret rotation is
[`docs/deployment/14_key_and_secret_lifecycle.md`](docs/deployment/14_key_and_secret_lifecycle.md).
The incident-response runbook — detection, containment, evidence and its clocks — is
[`docs/deployment/19_incident_response.md`](docs/deployment/19_incident_response.md). The privacy
position it serves is [`docs/dpg/privacy-assessment.md`](docs/dpg/privacy-assessment.md).
