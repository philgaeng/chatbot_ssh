# Follow-up — the e2e suite drives officer admin up to account provisioning, and stops

**Logged:** 2026-09-06, while writing QA-04c's tier-1 flow *"settings → create/edit an officer"*.
**Owner:** qa · **Status:** deliberate scope boundary, tracked as `GRM-075`. Everything short of
provisioning **is** driven.

## What is covered, and what is not

| Driven today (`e2e/flows/settings-officers.spec.ts`) | Not driven |
|---|---|
| Directory renders the seeded roster | Submitting an invite |
| Search narrows it (asserted by what disappears) | The set-password email |
| Invite form's office → position cascade unlocks | Editing an existing officer's position |
| Non-admins get the locked panel instead | Deactivation / reactivation |

## Why provisioning is not driven

**It has an external side effect that a test run must not have.** `POST` invite calls
`keycloak_create_user` whenever `keycloak_admin_url` is set — measured 2026-09-06, it **is** set on
the dev stack — so each run would create a real Keycloak user in the realm and ask it to send a
set-password email through realm SMTP. Running that on every pull request means a realm slowly
filling with `e2e-*@…` accounts and, wherever SMTP is live, mail to an address somebody owns.

That is a different class of problem from the rest of the suite, which only writes rows this system
already treats as append-only.

## What would make it drivable — two options, both cheap, neither free

1. **A stack with no `KEYCLOAK_ADMIN_URL`.** `keycloak_configured()` returns false and the invite
   records the ticketing-side officer row without provisioning. This is the smaller change and it
   suits CI, where the e2e stack is built from compose anyway. ⚠ It also means the spec would cover
   a **different** code path from the one production runs, which must be said out loud in the spec
   rather than discovered later.
2. **A disposable realm.** Closest to production and the only version that covers `keycloak_create_user`
   itself. Costs a Keycloak container in the e2e stack — the single heaviest service, and the one
   [Q-07](../QUESTIONS.md#q-07--what-auth-mode-does-the-suite-run-against) chose the bypass build
   specifically to avoid.

⭐ **Recommendation: (1), and only once the deferred Keycloak login smoke test (Q-07) exists** — that
job needs a realm anyway, and putting both in it keeps every Keycloak dependency in one place instead
of two.

## Definition of done

- [ ] An invite is submitted end to end and the officer appears in the Directory as *invited, unstaffed*
- [ ] The spec states which provisioning path it exercised, and which it did not
- [ ] No account or email is created against a realm anybody uses

## Related

⚠ **On a freshly seeded database this flow cannot be completed at all** — `GRM-074`, a separate
finding: every seeded position type is restricted to a unit type no seeded organisation has, so
"Pick a position…" is empty under both DOR and ADB. That one is a seed defect, not a test gap, and
fixing it is a precondition for the definition of done above.
