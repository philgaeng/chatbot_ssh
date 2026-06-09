# File Processing Service Spec

## 1) Scope

Shared file upload, storage, processing-status, and task-status bridge for webchat and related channels.

Primary implementation:

- API router: `backend/api/routers/files.py`
- core logic: `backend/services/file_server_core.py`
- async workers: `backend/task_queue/registered_tasks.py`

## 2) API Endpoints

### `POST /upload-files`

Multipart upload endpoint.

Inputs:

- `grievance_id` (required)
- `files[]` (required)
- optional metadata: `rasa_session_id`, `flask_session_id`, `client_type`

Behavior:

- Validates extension and max-size rules
- Stores files in grievance directory
- Enqueues `process_file_upload_task`
- Returns `202` with `task_id` and `files` (file ids) on accepted batch

### `GET /file-status/{file_id}`

Returns file processing state:

- `STARTED`
- `SUCCESS`
- `FAILURE`

Failure statuses are cached from failed task-status pushes.

### `GET /files/{item}`

Dual behavior:

- if `item` matches grievance-id pattern -> list file metadata for grievance
- else -> serve file by filename from upload folder

### `GET /download/{file_id}`

Resolves file metadata by id and returns attachment stream.

### `POST /task-status`

Internal bridge endpoint for async workers to publish status.

Behavior:

- Accepts task status payload
- routes events based on source mode:
  - accessible source (`A`) emits accessible status updates
  - bot/webchat source (`B`) emits room events (`task_status` / `file_status_update`)

## 3) Core Validation Rules

In `FileServerCore`:

- extension allow-list
- MIME allow-list checks
- per-file max sizes by file type

Audio uploads can include metadata extraction (duration/format where available).

## 4) Async Pipeline

File tasks:

- `process_file_upload_task`
- `process_batch_files_task`
- `aggregate_batch_results`

Status tracking:

- task manager emits status updates to backend `/task-status`
- frontend polling via `/file-status/{file_id}` remains authoritative UX fallback

## 5) Operational Notes

- Requires valid grievance id context to persist attachment records.
- Upload path defaults to `UPLOAD_FOLDER`/`uploads`.
- Endpoint includes compatibility behavior with legacy Flask service contracts.

---

## 6) Image compression (prod — locked 2026-06-05)

Server-side normalization for **chatbot complainant image uploads** only (v1). Officers review evidence mostly on phone; compress before object storage to save RAM, bandwidth, and S3 cost.

### 6.1 Goals

| Goal | Approach |
|------|----------|
| Low RAM on 2 vCPU / 8 GiB host | **libvips** via `pyvips` (streaming), not Pillow full-raster decode |
| iPhone HEIC | **libheif** + libde265; build must verify HEIF loader at image build time |
| Mobile-first viewing | Max long edge **1280 px** (aligns with webchat client pre-compress at 1200 px) |
| Limited prod scope this week | One output object per upload (JPEG); no originals bucket yet |

### 6.2 Pipeline placement

```
POST /upload-files
  → validate + write temp to uploads/{grievance_id}/
  → enqueue process_file_upload_task (202 + task_id)
Celery worker (file tasks, concurrency 1)
  → file_server_core.process_file_upload()
  → if file_type == image: image_compression.compress_image(path)
  → PUT compressed JPEG to private object storage (when S3 wired; else local path until cutover)
  → store_file_attachment() with final size/path/key
  → task-status SUCCESS / FAILURE
```

Client-side canvas compress in `channels/REST_webchat/app.js` remains as **first pass**; server policy is **authoritative**.

### 6.3 Compression policy (locked)

| Parameter | Value |
|-----------|-------|
| Max long edge | **1280 px** (preserve aspect ratio) |
| Output format | **JPEG** |
| JPEG quality | **80** |
| Skip re-encode if | long edge ≤ 1280 **and** `file_size < 500_000` bytes |
| EXIF in output pixels | **Strip** (geo/time live in `client_metadata` when user consented — CB-08) |
| Animated GIF | First frame → JPEG, or skip compress and store as-is (implementer picks one; document in code) |
| On compress failure | **Keep original**, log warning, set `compression_status: skipped` in processing metadata — do not fail upload |
| Target output size | ~200 KB – 800 KB typical |

### 6.4 Engine and dependencies

**Python:** `pyvips` in `requirements.txt`.

**System (Dockerfile — backend + celery images that run file tasks):**

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libvips42 \
    libvips-tools \
    libheif1 \
    libde265-0 \
    && vips -l foreign | grep -iq heif \
    && echo "HEIF loader OK" \
    || (echo "ERROR: libvips missing HEIF support" && exit 1)
```

Package names may differ on Ubuntu 24.04 / ARM64 — adjust pin names; **build must fail** if `vips -l foreign` shows no HEIF loader.

**Runtime startup (Celery worker):** log whether HEIF load is available (`pyvips.get_suffixes()` or `vips -l foreign`).

### 6.5 Worker concurrency (prod host)

Application server: **2 vCPU, 8 GiB RAM** (Postgres, Redis, APIs, Celery share the box).

| Setting | Value |
|---------|-------|
| Image compress concurrency | **1** (never > 2 on this spec) |
| Queue | `default` or dedicated `file_queue` with `concurrency=1` |

LLM and file CPU work must not run unbounded in parallel on the same worker process pool.

### 6.6 Storage

Prod attachments: **private encrypted object storage (~50 GB)**, not root disk.

- Compress **before** `PUT` to bucket.
- DB `file_attachments`: store final `s3_key` (or path during local-dev), `file_size`, optional JSON `processing_metadata`:
  - `original_bytes`, `compressed_bytes`, `width`, `height`, `compression_status` (`compressed` | `skipped` | `failed`)

### 6.7 Code layout (to implement)

| Piece | Location |
|-------|----------|
| Pure compress logic | `backend/services/image_compression.py` |
| Hook | `FileServerCore.process_file_upload()` when `file_type == 'image'` |
| Task | existing `process_file_upload_task` in `registered_tasks.py` |
| Constants | `backend/config/constants.py` — `IMAGE_COMPRESS_*` or env-driven policy |

### 6.8 Verification checklist

1. Docker build fails without HEIF in `vips -l foreign`.
2. CI or manual: convert sample `.heic` → `.jpg` inside container.
3. 8 MB JPEG phone photo → output ≤ ~1 MB, long edge ≤ 1280.
4. Already-small PNG (< 500 KB) → `compression_status: skipped`.
5. Corrupt image → original kept, upload still succeeds.
6. Worker memory stable under 3 concurrent uploads (queue serializes at concurrency 1).

### 6.9 Out of scope (v1)

- Officer ticketing uploads (`ticketing/api/routers/tickets.py`) — same policy later.
- Thumbnail variants for queue list.
- Original + display dual-object retention.
- Cloudinary / external image SaaS.

---

## 7) Archived attachments

When a resolved grievance is archived per [`docs/ARCHIVING_AND_RETENTION.md`](../ARCHIVING_AND_RETENTION.md):

| Phase | Attachment behaviour |
|-------|---------------------|
| Active case | Objects under active storage key/path; normal officer + complainant access rules |
| Archive job (`attachment_tier_on_archive: none`) | DB `storage_tier = 'archive'`; blobs unchanged |
| Archive job (`cold`) | Copy/move to `archive/{grievance_id}/…`; update `file_attachments.storage_key` |
| Complainant download | Denied by default when archived |
| New upload to archived `grievance_id` | `POST /upload-files` returns **409** |

Compression (§6) runs **before** archive; archived objects are not re-compressed.
