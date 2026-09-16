# `GRM-109` — officer session tokens live where any script on the page can read them

**Deferred 2026-09-14**, while fixing `GRM-105`. Logged here and in [`SPINE.md`](../../../SPINE.md)
per the standing deferral rule. **Kind:** `debt` — nothing is broken; a stronger control exists and was
not taken.

## What is true today

The officer UI keeps the access, ID and refresh tokens in `localStorage`
(`channels/ticketing-ui/lib/auth/token-storage.ts`). Any script running on the page can read them: an
XSS, a compromised dependency, a browser extension with page access.

## What `GRM-105` changed, and what it did not

- ✅ **A stolen refresh token can no longer run quietly beside the officer's session.** The realm now
  allows one use per refresh token, and — measured on Keycloak — any second use ends the whole
  session. Whichever of the thief and the officer renews second, both are signed out, and the server
  logs the reuse at `WARNING`.
- ⛔ **It does not stop the theft.** A thief who renews first holds a working session until the officer
  next renews (at most the 1-hour access-token lifetime), and a stolen *access* token works until it
  expires regardless.

## The stronger control

Keep the refresh token in an `HttpOnly`, `Secure`, `SameSite=Strict` cookie scoped to `/api/v1/auth/`,
set and read only by the server. Script can then never read it, and renewal becomes a same-origin POST
with no body.

## Why it was not done with `GRM-105`

- **It is a different change in kind.** Sign-in, renewal and sign-out endpoints all change contract;
  `persistAuthTokens`, `clearAuthStorage`, the cross-tab sign-out (keyed on a `localStorage` removal
  event) and every test around them change with it.
- **Cookies bring CSRF into scope** for the auth endpoints, which today accept only a JSON body.
- **The access token would still be readable** unless it moved too, and `apiFetch` sends it as a
  `Bearer` header built from storage.

## What would make it ready

A short design note answering: where the access token lives; how cross-tab sign-out is signalled
without a storage removal event; the CSRF defence (`SameSite=Strict` plus an `Origin` check is likely
enough for same-origin JSON endpoints); and whether sign-in by PKCE (`ticketing-ui`) is kept at all.
