# Keycloak recorded no login events at all — and the ops report read that as a quiet day

**Logged:** 2026-08-24 · **Found by:** writing [`docs/deployment/19_incident_response.md`](../../../deployment/19_incident_response.md)
· **Register:** privacy assessment **F-18** · **Severity when found:** 🟠 Medium

## What was wrong

Keycloak persists **no** login, login-failure or admin events unless the realm asks for it. Both
`eventsEnabled` and `adminEventsEnabled` default to **off**, nothing in this repository turned them on,
and no realm export exists to carry the setting. Verified against the live realm on 2026-08-24:

```
 name | events_enabled | admin_events_enabled | events_expiration
------+----------------+----------------------+-------------------
 grm  | f              | f                    |                 0
```

`keycloak.event_entity` held **0 rows**.

## Why nobody noticed

`ops/reports.py` already queried that table — `:45` for "Officer logins (24h)", `:55` for "Failed logins
(24h)". With storage off both counts returned **0**, which is indistinguishable from a day on which
nothing happened. **A monitoring row that cannot tell "none happened" from "none recorded" is worse than
an absent one**, because it reads as reassurance. The privacy assessment then listed the same events among
the controls that existed (§5.3), which is how the claim survived every review of that document.

## The fix

`setup_realm_event_logging` in [`ticketing/auth/keycloak_setup.py`](../../../../ticketing/auth/keycloak_setup.py)
— login + admin events, `adminEventsDetailsEnabled`, `EVENTS_EXPIRATION = 7776000` (90 days), applied by
`make keycloak-setup` alongside the other realm settings. `enabledEventTypes` is deliberately left unset,
which stores every type: a responder cannot know in advance which event turns out to matter.

Verified end to end on the local realm: settings applied, and a failed password grant wrote a
`LOGIN_ERROR` row.

**90 days, and the reason:** long enough that a disclosure arriving weeks later is still investigable
(backups roll at 14 days), short enough to stay data-minimising. The retention decision in
privacy-assessment §5.1 may override it.

## What is still outstanding

- [ ] ⚠ **Apply to staging and DOR production.** The change is in the image, so it lands on the next
      build; `make keycloak-setup` must then be re-run against each environment. **Until that happens,
      neither server records any authentication evidence.**
- [ ] ⚠ **Forward-only, permanently.** No login on any environment before 2026-08-24 was recorded, and
      none of it is recoverable. Any incident investigation reaching back past that date has no
      authentication evidence and must say so.
- [ ] Consider an `ops` health check that fails when realm event storage is off, so this cannot regress
      silently the next time a realm is recreated. The defect class — *a monitoring query against a store
      nothing writes to* — is not specific to Keycloak.
