# Follow-up — voice-chunk upload sessions live in a process-local dict

> **Status:** 🔴 **OPEN — deferred out of T3-03 (2026-07-15).** · **Owner:** backend / file services · **Priority:** low *today*, blocking the moment the backend API scales past one worker
> **Origin:** surfaced while fixing T3-03 ([`../02-webchat-voice-spec.md`](../02-webchat-voice-spec.md)), which explicitly scopes out `file_server_core.py` session lifecycle: *"Anything found in `file_server_core.py` session lifecycle / expiry. Log to PROGRESS.md → Deviations + followup + TODO.md row."* This is that log.

## The finding

Voice-chunk upload sessions are held in a module-level dict in the API process:

```python
# backend/services/file_server_core.py:29-31
# In-memory voice chunk upload sessions (upload_id -> session dict). TTL 1 hour.
_VOICE_CHUNK_SESSIONS: Dict[str, Dict[str, Any]] = {}
_VOICE_CHUNK_TTL_SEC = 3600
```

The chunked-upload protocol is **stateful across requests**: chunk 0 mints an `upload_id` and creates the session (`files.py:431-436`), chunks 1..N look it up to find `next_chunk_index` and the `.part` path (`file_server_core.py:310`), and `/upload-voice-complete` assembles from it (`:384`). Every request in that sequence must therefore land on **the same process**.

The assembled `.part` file is likewise a local filesystem path, so this is not only a memory-affinity problem — the partial audio itself is process-local.

## Why it is not a live bug today

The backend API runs a single uvicorn worker, so every chunk necessarily lands on the same process:

```yaml
# docker-compose.yml:48
command: uvicorn backend.api.fastapi_app:app --host 0.0.0.0 --port 5001
```

No `--workers`, no `--reload` multi-process, no replica count. **Verified 2026-07-15** — this is why chunked voice upload works in production. The finding is a **latent constraint**, not a defect.

## Why it matters

The constraint is invisible and unguarded. Any of these silently breaks voice notes:

- adding `--workers N` to the uvicorn command (the standard first move when the API is CPU-bound),
- scaling the `backend` service to >1 replica,
- putting a second API instance behind the nginx upstream.

The failure mode is not a clean error at deploy time: chunk 0 succeeds, then chunk 1 hits a worker without the session → `upload_session_not_found` → **404**. On the client, `isIgnorableLateChunkError` matches `"not found"` and **swallows it** (`voiceNote.js:31`), so the user sees a recording that appears to work and then fails or truncates at finalize. It would read as a flaky voice feature, not as a scaling misconfiguration — the same "invisible on dev, deterministic in prod" shape as the T3-03 bug itself.

Note T3-03 deliberately did **not** widen the `"not found"` swallow to cover this: mid-recording a 404 means the session is gone and finalize will fail loudly anyway, so unlike the `"out of order"` case it does not silently truncate. Gating it was out of scope; revisit here.

## Why it was deferred

- **Out of scope by the spec's own terms** — T3-03 is a client-side ordering fix and explicitly must not change the server, which "behaves correctly" for the single-worker deployment it ships in.
- **Not currently reachable** — no configuration in the repo scales the API past one worker.
- **The fix is a real design choice, not a patch** — see below. It does not belong bolted onto a client bugfix.

## Definition of done

1. **Guard it first, cheaply.** Either assert single-worker at startup, or add a comment at `docker-compose.yml:48` recording that voice-chunk upload requires worker affinity. This alone converts a silent trap into a known constraint and is worth doing independently of the rest.
2. Choose the durable model:
   - **Redis-backed sessions** + shared/object storage for the `.part` file — the broker already exists in the stack;
   - **or** sticky sessions on `upload_id` at nginx — cheaper, but pins scaling policy to a client-supplied key;
   - **or** accept single-worker and document it as a deployment invariant.
3. Whichever is chosen, add a test that exercises chunk 0 and chunk 1 against **different** core instances — today no test would catch a regression here, because the suite shares one process.
4. Revisit the client's `"not found"` swallow (`voiceNote.js:31`) once the server can answer 404 for a reason other than genuine expiry.

**Recommended trigger:** before any change to the backend API's worker/replica count — this should be on the checklist for that work, not discovered by it.
