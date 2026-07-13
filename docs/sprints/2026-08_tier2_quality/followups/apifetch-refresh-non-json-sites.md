# Follow-up — extend silent refresh to the non-`apiFetch` fetch sites

> **Status:** open (unstarted) · **Owner:** portal · **Priority:** low–medium (upload sites can lose a file selection on token expiry)
> **Origin:** H2-01 (`docs/sprints/2026-08_tier2_quality/PROGRESS.md` deviation, 2026-07-13). The OIDC refresh+retry was scoped to `apiFetch` only (spec item 3). The remaining fetch sites still hard-logout on a 401.

## The gap

`channels/ticketing-ui/lib/api.ts` has 4 fetch sites that bypass `apiFetch` (they need blob/multipart handling `apiFetch` doesn't do) and therefore did **not** get H2-01's proactive refresh + `401 → refresh → retry-once`. They still call `isSessionExpiredResponse(...)` → `handleSessionExpired()`, i.e. bounce the officer to `/login` on an expired token:

| Site | Function | 401 handling | Work lost on logout |
|---|---|---|---|
| `api.ts:1196` | `fetchAuthenticatedBlobUrl` (protected file GET → blob URL) | `isSessionExpiredResponse` | none (read-only) |
| `api.ts:1278` | attachment upload (`POST /tickets/{id}/attachments`, multipart) | `isSessionExpiredResponse` | **the file selection + caption** |
| `api.ts:1407` | XLSX export (`fetchAuthenticatedBlob`) | `isSessionExpiredResponse` | none (re-runnable) |
| `api.ts:2121` | `importOrganizations` (`POST /organizations/import`, multipart) | `isSessionExpiredResponse` | **the chosen CSV + dry-run state** |

**Mitigation today:** `apiFetch`'s proactive (<60 s) refresh keeps the token fresh during active JSON use, so an upload shortly after normal navigation is unlikely to hit expiry. The gap is a long-idle tab where the first action is one of these four.

## Definition of done

- [ ] A shared authed-fetch preflight (e.g. `ensureFreshToken()` reusing `refreshTokens()` single-flight) applied to all 4 sites: proactive refresh before the request, and `401 → refresh → retry-once`.
- [ ] Multipart retry re-sends the body — `File`/`FormData` are re-readable, so rebuild+resend on retry (confirm the second POST carries the same parts).
- [ ] `isSessionExpiredResponse` retired once every site routes through the shared path (it exists only to serve these 4 now).
- [ ] Vitest: one upload site 401→refresh→retry→success; refresh-fail→logout once. `tsc` + `eslint` + `next build` green.

## Optional (same area, lower priority)

- Background/interval refresh in `AuthProvider` — currently refresh happens on mount + inside `apiFetch` (proactive/reactive) only; there is no timer that renews a token in a tab left open with no API activity. Low value given the proactive path; note here so it isn't rediscovered.
