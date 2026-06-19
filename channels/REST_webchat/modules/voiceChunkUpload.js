/** Chunked voice-note upload (streams 1s MediaRecorder slices). */

import { VOICE_CHUNK_UPLOAD_CONFIG } from "../config.js";

const MAX_RETRIES = 3;
const RETRY_BASE_MS = 800;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function postVoiceChunk(formData) {
  const response = await fetch(VOICE_CHUNK_UPLOAD_CONFIG.CHUNK_URL, {
    method: "POST",
    body: formData,
  });
  let data;
  const contentType = response.headers.get("content-type") || "";
  try {
    data = contentType.includes("application/json")
      ? await response.json()
      : { error: (await response.text()) || `Server error (${response.status})` };
  } catch {
    data = {
      error: (await response.text().catch(() => `Server error (${response.status})`)),
    };
  }
  if (!response.ok) {
    const err = new Error(data.error || data.detail || `Chunk upload failed (${response.status})`);
    err.status = response.status;
    err.data = data;
    throw err;
  }
  return data;
}

async function withRetry(fn) {
  let lastError;
  for (let attempt = 0; attempt < MAX_RETRIES; attempt += 1) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      if (attempt >= MAX_RETRIES - 1) break;
      await sleep(RETRY_BASE_MS * (attempt + 1));
    }
  }
  throw lastError;
}

/**
 * Upload one recording slice. Returns server payload including upload_id.
 */
export async function uploadVoiceChunk({
  uploadId,
  chunkIndex,
  blob,
  fileName,
  mimeType,
  grievanceId,
  complainantId,
  flaskSessionId,
  rasaSessionId,
}) {
  const formData = new FormData();
  formData.append("chunk_index", String(chunkIndex));
  if (uploadId) formData.append("upload_id", uploadId);
  if (fileName) formData.append("file_name", fileName);
  if (mimeType) formData.append("mime_type", mimeType);
  if (grievanceId) formData.append("grievance_id", grievanceId);
  if (complainantId) formData.append("complainant_id", complainantId);
  if (flaskSessionId) formData.append("flask_session_id", flaskSessionId);
  if (rasaSessionId) formData.append("rasa_session_id", rasaSessionId);
  formData.append("chunk", blob, `chunk_${chunkIndex}.bin`);

  return withRetry(() => postVoiceChunk(formData));
}

/**
 * Finalize chunked upload and queue server processing.
 */
export async function completeVoiceUpload({
  uploadId,
  grievanceId,
  complainantId,
  flaskSessionId,
  rasaSessionId,
}) {
  const formData = new FormData();
  formData.append("upload_id", uploadId);
  if (grievanceId) formData.append("grievance_id", grievanceId);
  if (complainantId) formData.append("complainant_id", complainantId);
  if (flaskSessionId) formData.append("flask_session_id", flaskSessionId);
  if (rasaSessionId) formData.append("rasa_session_id", rasaSessionId);

  const response = await fetch(VOICE_CHUNK_UPLOAD_CONFIG.COMPLETE_URL, {
    method: "POST",
    body: formData,
  });
  let data;
  const contentType = response.headers.get("content-type") || "";
  try {
    data = contentType.includes("application/json")
      ? await response.json()
      : { error: (await response.text()) || `Server error (${response.status})` };
  } catch {
    data = {
      error: (await response.text().catch(() => `Server error (${response.status})`)),
    };
  }
  if (!response.ok) {
    const err = new Error(data.error || data.detail || `Complete failed (${response.status})`);
    err.status = response.status;
    err.data = data;
    throw err;
  }
  return data;
}
