# T3-03 — Serialize voice-chunk uploads (M)

> Workstream C · Branch `dev/tier3-structural` · **Independent** — touches only `channels/REST_webchat/modules/` (+ optionally `tests/backend/test_fastapi_files.py`).
> Evidence: [`00-reassessment.md`](00-reassessment.md) §5. **This is the one Tier-3 item the source review got exactly right** — but it missed a second bug in the same code (§Silent truncation below).
> Line numbers as of `dev/tier3-structural` @ 2026-07-15 — re-locate before editing.

---

## Problem (verified by hand, 2026-07-15)

**This is a live bug, not a determinism nicety. On a link with RTT > 1 s, the entire voice recording is aborted and discarded.** Deterministic on 2G/3G, invisible on dev wifi — which is why it shipped.

### The protocol

| Piece | File |
|---|---|
| Chunker (MediaRecorder, `CHUNK_TIMESLICE_MS = 1000` at `:8`) | `channels/REST_webchat/modules/voiceNote.js` |
| Transport + retry | `channels/REST_webchat/modules/voiceChunkUpload.js` |
| Endpoints | `channels/REST_webchat/config.js:24-26` |
| Server handler | `backend/api/routers/files.py:390-482` |
| Server core | `backend/services/file_server_core.py:302-333` |

**Chunk 0 mints the id.** A chunk with no `upload_id` is only legal at `chunk_index == 0` (`files.py:423-436`), which calls `create_voice_chunk_session()` and returns `upload_id` in the response (`files.py:466`). Chunks 1..N **must** carry it.

**The server is strict-sequential**, appending to a single `.part` file (`file_server_core.py:328-331`):
- `chunk_index < expected` → `{"duplicate": True}` — retry-safe (`:315-316`)
- `chunk_index > expected` → `ValueError("chunk_out_of_order")` → **409** (`:317-318`, `files.py:451-452`)

### The race

Uploads fire **fully concurrently** — no `await`, no queue (`voiceNote.js:121-127`, inside `ondataavailable`, every 1 s):

```js
const index = chunkIndex;
chunkIndex += 1;
void uploadRecordingChunk(event.data, index).catch((error) => {
```

The only join is at *stop*: `await Promise.all(pendingChunkUploads)` (`:220`). **Nothing serializes chunk 1 behind chunk 0 during recording.**

It is the **"no id"** variant (not wrong-id, not duplicate-session). `uploadRecordingChunk` reads module-level `uploadId` at call time (`:75`); it is assigned only inside chunk 0's `.then()` (`:85-89`). If chunk 0's response hasn't returned by t=2000 ms, `uploadId` is still `null` and `voiceChunkUpload.js:67` omits the field:

```js
if (uploadId) formData.append("upload_id", uploadId);
```

→ `files.py:423-428` → **400 `"upload_id required for chunk_index > 0"`**.

### Why the existing retry cannot heal it — the load-bearing detail

`uploadVoiceChunk` builds the `FormData` **once** (`voiceChunkUpload.js:65-74`) and the retry closure re-posts that **frozen** body (`:76` → `withRetry` at `:37-49`):

```js
return withRetry(() => postVoiceChunk(formData));
```

All 3 attempts (800/1600 ms backoff) resend an **identical id-less body** and get 400 each time — even though `uploadId` became available in the meantime.

Then `isIgnorableLateChunkError` (`voiceNote.js:25-35`) matches only `"upload session expired"`, `"not found"`, `"out of order"`, or `isStopping && (404|409)`. `"upload_id required for chunk_index > 0"` matches **none** → the error propagates → `:123-127` → `stopRecording(..., "upload_error")` → `onStatus("upload_error")` + `resetUploadState()` (`:206-212`).

**Concrete failure:** user taps record on a slow link; at the 2-second mark chunk 1 is built id-less, 400s three times over ~2.4 s, and the whole recording dies with a generic upload error.

### HR-07's send lock does NOT cover this — do not assume it does

`app.js:59-64` says so in its own declaration comment: it is an **"In-flight text-send lock"**. Its only guard is gated on a non-empty text `message` (`app.js:934`), set/cleared only around `window.safeSendMessage(message)` (`:959-962`). `beginSendLock` disables `sendButton` (`:910`) — not the record button. `voiceNote.js` never imports or consults it; `grep -rn 'isSending|sendLock'` hits **only** `app.js`.

### Second bug in the same code — silently truncated voice notes (NEW, review missed it)

`isIgnorableLateChunkError`'s `"out of order"` match (`voiceNote.js:32-34`) is **unconditional** — not gated on `isStopping` / `uploadFinalized`. So a **409 mid-recording** that exhausts its 3 retries is silently swallowed (`:92-95` returns `null`); the chunk is lost forever; every later chunk then 409s against a now-permanently-behind `next_chunk_index`; and `completeVoiceUpload` **succeeds**, producing a **silently truncated voice note**. The user gets no error and a shorter recording than they made.

**Serializing the queue eliminates this class too** — which is why it is in scope here rather than a followup.

---

## Change

**The real fix is the queue, not the FormData.** Both are listed; do both, but understand the difference: moving `FormData` construction inside the retry closure alone would only convert a hard failure into a slow one — it does not fix ordering, and does not fix the truncation bug.

1. **Serialize the chunk queue** (`voiceNote.js`). Chain each upload on the previous one's completion so chunk N never starts before chunk N-1 resolves — which also guarantees `uploadId` is populated for every chunk > 0, because chunk 0 is the head of the chain. `pendingChunkUploads.push()` (`:98`) already gives you the tail to await; build the chain off it rather than firing `void uploadRecordingChunk(...)` (`:123`).
   - Preserve the existing `await Promise.all(pendingChunkUploads)` join at stop (`:220`) — it stays correct for a chained queue.
   - **Throughput note:** the 1 s timeslice means serializing adds **no** throughput risk for RTT < 1 s, and naturally applies backpressure above it. This is a feature — do not add concurrency back.
2. **Build `FormData` inside the retry closure** (`voiceChunkUpload.js:65-76`) so a retry re-reads the current `uploadId` rather than resending a frozen id-less body. This mirrors the **H2-01 + `apifetch-refresh-non-json-sites`** precedent in the portal, where multipart bodies are rebuilt **in the thunk** so the retry re-sends them (`channels/ticketing-ui/lib/api.ts` → `authedFetch`; see [`../2026-08_tier2_quality.md`](../../2026-08_tier2_quality.md) §Follow-ups and [`../archive/2026-08_tier2_quality/followups/apifetch-refresh-non-json-sites.md`](../../archive/2026-08_tier2_quality/followups/apifetch-refresh-non-json-sites.md)). **Follow that precedent** — it is the same bug shape (a frozen body re-sent by a retry that cannot pick up state that landed meanwhile) solved in the same repo two weeks earlier.
3. **Gate the `"out of order"` swallow** on `isStopping` / `uploadFinalized` (`voiceNote.js:32-34`). A mid-recording 409 that exhausts retries must **surface**, not be silently dropped — it means the `.part` file is now permanently behind and the note will truncate. Late chunks *after* stop remain legitimately ignorable.
4. **Do not** change the server. It behaves correctly: it rejects id-less and out-of-order chunks before any mutation (`files.py:423-428`, `file_server_core.py:317-318`) — hard-fail, not corruption. This is a **client** bug.

---

## Tests (acceptance)

There is **no JS test suite for `channels/REST_webchat/` at all** — only `node_modules` hits. That is the honest constraint on this ticket.

**Decide and record in PROGRESS.md** which path is taken:
- **(a) Stand up a minimal vitest/node harness** for `channels/REST_webchat/modules/` — highest value, makes this class testable forever, but expands the ticket. If chosen, log the CI wiring as a followup if not completed.
- **(b) Server-side tests only** + a scripted manual sweep — cheaper, but the race is **client-side** and would remain unguarded.

**Recommendation: (a)**, scoped to `voiceNote.js` + `voiceChunkUpload.js` with a stubbed `fetch`. The bug is a client ordering bug; a server test cannot catch a regression in it.

If (a):
- [ ] **The race, verified red pre-fix**: stub `fetch` so chunk 0's response resolves after a delay > `CHUNK_TIMESLICE_MS`; drive 3 `ondataavailable` events; assert **every** chunk > 0 carries an `upload_id` and no request 400s. Must **fail** on `HEAD~`.
- [ ] **Ordering**: assert chunks post in index order 0,1,2 — never overlapping.
- [ ] **Retry heals**: stub chunk 1's first attempt to 400, assert the retry re-reads a now-populated `uploadId` and succeeds (guards change 2).
- [ ] **Truncation guard**: a mid-recording 409 that exhausts retries **surfaces** (does not silently resolve `null`) while `isStopping === false`; a late 409 **after** stop is still ignored (guards change 3, verify red pre-fix).
- [ ] **No regression**: a fast-network run (chunk 0 resolves < 1 s) behaves exactly as today.

Server-side, regardless of path:
- [ ] Extend `tests/backend/test_fastapi_files.py` (existing: `:251` `test_upload_voice_chunk_and_complete`, `:313` `test_upload_voice_chunk_duplicate_is_idempotent`) with an **id-less chunk > 0 ⇒ 400** case, pinning the server contract the client now relies on.

---

## Manual verification

- [ ] Chrome DevTools → Network → throttle to **Slow 3G** (or Fast 3G): record a ≥ 5 s voice note ⇒ it uploads and completes. **On pre-fix code this aborts** with an upload error — confirm the red first, record it in PROGRESS.md.
- [ ] Normal network: record a ≥ 5 s note ⇒ unchanged behavior, no latency regression.
- [ ] Slow 3G: stop recording mid-flight ⇒ late chunks still ignored gracefully (no spurious error).
- [ ] Verify the resulting note plays back **at full length** (guards the truncation bug).
- [ ] *(May be marked pending-human if no browser is available in the build env — record as such. Note HR-07's manual webchat sweep is **also** still pending-human; see [`../2026-08_tier2_quality.md`](../../2026-08_tier2_quality.md) §Leftovers. Consider doing both in one browser session.)*

---

## Out of scope — log, don't fix

- Anything found in `file_server_core.py` session lifecycle / expiry. Log to PROGRESS.md → Deviations + followup + TODO.md row.
