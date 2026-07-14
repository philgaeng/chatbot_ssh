# Follow-up — extend silent refresh to the non-`apiFetch` fetch sites

> **Status:** ✅ **RESOLVED (2026-07-15).** All 4 sites route through the new shared `authedFetch`; `isSessionExpiredResponse` retired. · **Owner:** portal · **Priority:** low–medium (upload sites can lose a file selection on token expiry)
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

- [x] **Shared `authedFetch(makeRequest)` preflight** (`lib/api.ts`) reusing `refreshTokens()`'s single-flight: proactive refresh (token expiring within 60s) + `401 → refresh → retry-once` before `handleSessionExpired()`. All 4 sites (`fetchAuthenticatedBlobUrl`, `uploadOfficerAttachment`, `downloadApiFile`/XLSX, `importOrganizations`) route through it.
- [x] **Multipart retry re-sends the body** — the `FormData` is built *inside* the `makeRequest` thunk, so the retry rebuilds and re-sends the same parts (`authedFetch` re-invokes the thunk). Vitest asserts the 2nd fetch body is a fresh `FormData`.
- [x] **`isSessionExpiredResponse` retired** — removed from `session-expired.ts` (a comment records why), dropped from the `api.ts` import and the `api.test.ts` mock. Every 401 path is now status-code-based (apiFetch for JSON, authedFetch for blob/multipart).
- [x] **Vitest / tsc / eslint / next build green** — vitest 61 passed (8 files; +3 new `authedFetch` tests: multipart 401→refresh→retry→success with parts re-sent, multipart refresh-fail→logout-once, blob 401→refresh→retry). `tsc --noEmit` clean; `eslint` 0 errors / 141 warnings (baseline, none new); `next build` via the grm_ui Docker image build.

## Optional (same area, lower priority)

- Background/interval refresh in `AuthProvider` — currently refresh happens on mount + inside `apiFetch` (proactive/reactive) only; there is no timer that renews a token in a tab left open with no API activity. Low value given the proactive path; note here so it isn't rediscovered.
