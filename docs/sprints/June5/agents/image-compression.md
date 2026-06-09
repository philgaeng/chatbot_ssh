# Agent prompt — Image compression (prod deploy)

You are implementing **server-side image compression** for chatbot complainant uploads, ready for **production this week** on a **2 vCPU / 8 GiB** Docker Compose host.

---

## Read first

1. **`docs/services/04_file_processing_service.md`** — §6 (locked policy)
2. **`docs/services/04_file_processing_service.md`** — §§1–5 (existing upload pipeline)
3. `backend/services/file_server_core.py` — `process_file_upload()`
4. `backend/api/routers/files.py` — `_validate_files`, `POST /upload-files`
5. `backend/task_queue/registered_tasks.py` — `process_file_upload_task`
6. `backend/config/constants.py` — `FILE_TYPES['IMAGE']` (5 MB type cap)
7. `channels/REST_webchat/app.js` — client `compressFile()` (1200 px / 0.7) — do not remove; server is authoritative backstop

**Prod context:** LLM is external API; attachments go to **private object storage**, not root disk. ~10 concurrent chatbot users; file CPU must stay bounded.

---

## Mission

Implement **libvips + libheif** image normalization in the existing Celery file pipeline:

| Deliverable | Detail |
|-------------|--------|
| Compress module | `backend/services/image_compression.py` |
| Integration | Call from `FileServerCore.process_file_upload()` when `file_type == 'image'` |
| Docker | `libvips42`, `libheif1`, `libde265-0`; **fail build** if no HEIF loader |
| Python dep | `pyvips` in `requirements.txt` |
| Policy | Max edge **1280 px**, JPEG **quality 80**, strip EXIF, skip if already small |
| Failure mode | Keep original; `compression_status: skipped` — never block grievance filing |
| Worker | Celery **concurrency 1** for file/image work on prod |

S3 upload wiring may already exist or be stubbed — compress to temp JPEG then follow whatever path `store_file_attachment` / upload helper uses. If only local `uploads/` today, still replace file in place and update `file_size` in DB.

---

## Locked decisions (do not change without user sign-off)

```
ENGINE=libvips (pyvips)
HEIC=libheif (verify at Docker build)
MAX_LONG_EDGE=1280
OUTPUT=JPEG
QUALITY=80
SKIP_IF=long_edge<=1280 AND size<500KB
EXIF_OUTPUT=strip
CONCURRENCY=1
ON_FAILURE=keep_original
SCOPE=chatbot_complainant_images_only_v1
```

---

## You may edit

- `backend/services/image_compression.py` (new)
- `backend/services/file_server_core.py` — image branch in `process_file_upload`
- `Dockerfile` — libvips + libheif + build-time `vips -l foreign` gate
- `requirements.txt` — `pyvips`
- `docker-compose.yml` — only if adding `file_queue` worker or lowering celery concurrency (coordinate with user; file is normally DO NOT TOUCH — **exception: concurrency env for file worker**)
- `backend/config/constants.py` — compression policy constants
- `backend/task_queue/registered_tasks.py` — logging / metadata pass-through only if needed
- `tests/` — unit tests for policy + optional container HEIC smoke test
- `docs/services/04_file_processing_service.md` — implementation notes only if behavior differs from §6

---

## Do not edit

- `channels/ticketing-ui/`, `ticketing/` (officer uploads out of scope v1)
- `backend/orchestrator/`, `backend/actions/` (unless user explicitly extends scope)
- Remove or weaken client-side `compressFile()` in webchat

---

## Implementation steps

### 1. Dockerfile

Add runtime libs and **fail the image build** without HEIF:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libvips42 libvips-tools libheif1 libde265-0 \
    && vips -l foreign | grep -iq heif \
    || (echo "ERROR: libvips missing HEIF" && exit 1)
```

Rebuild **backend** and **celery** images (same Dockerfile in this repo).

### 2. `image_compression.py`

- `compress_image(file_path: str, policy: ImageCompressPolicy) -> CompressResult`
- Use pyvips thumbnail/load with `size=down` to max 1280 on long edge
- Write JPEG q=80 to temp path, atomic replace original (or write `.jpg` and update `file_name` extension)
- Return: `original_bytes`, `compressed_bytes`, `width`, `height`, `status`
- Skip path: probe dimensions/size without full re-encode when under threshold

### 3. `file_server_core.py`

After `file_type == 'image'`, before `store_file_attachment`:

```python
result = compress_image(file_data["file_path"])
file_data["file_size"] = result.compressed_bytes
file_data["processing_metadata"] = {...}  # if column/JSON supported; else log only
```

Persist processing metadata if `file_attachments` has `client_metadata`-style JSON field; if not, log structured fields for now.

### 4. Celery / compose

Ensure file processing does not run **>1** compress job at a time on prod:

- Prefer dedicated queue `file_queue` with `concurrency=1`, **or**
- Lower `celery_default` concurrency and document tradeoff

### 5. Tests

| Test | Expect |
|------|--------|
| Large JPEG fixture | long edge ≤ 1280, smaller bytes |
| Small PNG fixture | `skipped` |
| Invalid file | original kept, no exception to user |
| `vips -l foreign` in CI | grep heif (optional job step) |

Add `backend/dev-resources/fixtures/` sample images if missing (no real PII).

### 6. Deploy verification (prod)

Run inside **celery** container after deploy:

```bash
vips -l foreign | grep -i heif
python -c "import pyvips; print([s for s in pyvips.get_suffixes() if 'heif' in s.lower()])"
```

Upload 1 HEIC + 1 large JPEG through webchat → confirm `file_size` drop and image viewable in portal/ticket files list.

---

## Progress protocol

Update `docs/sprints/June5/PROGRESS.md` with a row under a new subsection **Image compression** (or Agent: Image compression):

| Item | Status |
|------|--------|
| Dockerfile libheif gate | |
| `image_compression.py` | |
| `file_server_core` hook | |
| Tests | |
| Prod smoke (HEIC + JPEG) | |

---

## Definition of done

- [ ] Docker build fails without HEIF loader
- [ ] Complainant image upload compresses to JPEG ≤1280 px / q80
- [ ] HEIC from iPhone decodes in container smoke test
- [ ] Upload failure on corrupt image does **not** block grievance
- [ ] Celery concurrency documented/set for 2 vCPU host
- [ ] `04_file_processing_service.md` §6 matches shipped behavior
- [ ] PROGRESS.md updated

---

## Report back

1. Files changed
2. Sample before/after bytes for one JPEG and one HEIC
3. `vips -l foreign | grep heif` output from built image
4. Any blocker on S3 vs local `uploads/` path
