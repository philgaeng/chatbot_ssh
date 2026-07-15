/** CB-01: voice note recording (MediaRecorder) with chunked upload. */

import { uploadVoiceChunk, completeVoiceUpload } from "./voiceChunkUpload.js";

/** With chunked upload, longer clips are viable on patchy networks. */
export const MAX_RECORD_SECONDS = 180;

const CHUNK_TIMESLICE_MS = 1000;
const AUDIO_MAX_BYTES = 10 * 1024 * 1024;

let mediaRecorder = null;
let recordTimer = null;
let tickTimer = null;
let recordStartedAt = 0;
let uploadId = null;
let chunkIndex = 0;
let totalBytes = 0;
let pendingChunkUploads = [];
let uploadChain = Promise.resolve();
let plannedFileName = null;
let plannedMimeType = null;
let getUploadContext = () => ({});
let isStopping = false;
let uploadFinalized = false;

function isIgnorableLateChunkError(error) {
  if (uploadFinalized) return true;
  const status = error?.status;
  if (isStopping && (status === 404 || status === 409)) return true;
  const message = String(error?.message || "").toLowerCase();
  if (message.includes("upload session expired") || message.includes("not found")) {
    return true;
  }
  // Only ignorable once we're stopping. Mid-recording it means the server's .part file
  // is permanently behind: the chunk is gone, every later chunk will also be rejected,
  // and finalize would still succeed — yielding a silently truncated note.
  return isStopping && message.includes("out of order");
}

export function initVoiceNote({
  button,
  onStatus,
  onTick,
  onUploadComplete,
  onUploadError,
  getUploadContext: getContext,
}) {
  if (!button) return;
  getUploadContext = getContext || getUploadContext;

  button.addEventListener("click", async (event) => {
    if (button.disabled) {
      event.preventDefault();
      return;
    }
    if (mediaRecorder?.state === "recording") {
      await stopRecording(button, onUploadComplete, onUploadError, onStatus);
      return;
    }
    await startRecording(button, onStatus, onUploadComplete, onUploadError, onTick);
  });
}

function resetUploadState() {
  uploadId = null;
  chunkIndex = 0;
  totalBytes = 0;
  pendingChunkUploads = [];
  uploadChain = Promise.resolve();
  plannedFileName = null;
  plannedMimeType = null;
  uploadFinalized = false;
}

async function uploadRecordingChunk(blob, index) {
  if (uploadFinalized) return null;
  const ctx = getUploadContext();
  return uploadVoiceChunk({
    // Resolved per attempt, not captured: chunk 0's response is what assigns uploadId.
    getUploadId: () => uploadId,
    chunkIndex: index,
    blob,
    fileName: index === 0 ? plannedFileName : undefined,
    mimeType: index === 0 ? plannedMimeType : undefined,
    grievanceId: ctx.grievanceId,
    complainantId: ctx.complainantId,
    flaskSessionId: ctx.flaskSessionId,
    rasaSessionId: ctx.rasaSessionId,
  })
    .then((result) => {
      if (!uploadId && result?.upload_id) {
        uploadId = result.upload_id;
      }
      return result;
    })
    .catch((error) => {
      if (isIgnorableLateChunkError(error)) {
        console.warn("Ignoring late voice chunk after finalize:", error);
        return null;
      }
      throw error;
    });
}

/**
 * Queue one chunk behind the previous one.
 *
 * The server appends to a single .part file and is strict-sequential, and only chunk 0
 * mints the upload_id that chunks 1..N must carry. Firing uploads concurrently means
 * that on any link slower than CHUNK_TIMESLICE_MS, chunk 1 is built before chunk 0 has
 * answered — no upload_id, 400, recording aborted. Chaining each chunk on its
 * predecessor's settlement makes both hazards structurally impossible.
 *
 * The 1 s timeslice means this costs no throughput below 1 s RTT, and above it the
 * queue applies backpressure instead of stampeding. That is intended — do not
 * reintroduce concurrency here.
 */
function enqueueRecordingChunk(blob, index) {
  // Chain on settlement, not success: a rejected predecessor must not turn into a
  // second rejection here, or one failed chunk would be reported once per queued chunk.
  const runNext = () => uploadRecordingChunk(blob, index);
  const promise = uploadChain.then(runNext, runNext);
  uploadChain = promise.then(
    () => undefined,
    () => undefined
  );
  pendingChunkUploads.push(promise);
  return promise;
}

async function startRecording(button, onStatus, onUploadComplete, onUploadError, onTick) {
  resetUploadState();
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeType = MediaRecorder.isTypeSupported("audio/webm")
      ? "audio/webm"
      : "audio/mp4";
    plannedMimeType = mimeType;
    const ext = mimeType.includes("webm") ? "webm" : "m4a";
    plannedFileName = `voice_note_${Date.now()}.${ext}`;

    mediaRecorder = new MediaRecorder(stream, { mimeType });
    mediaRecorder.ondataavailable = (event) => {
      if (!event.data?.size) return;
      totalBytes += event.data.size;
      if (totalBytes > AUDIO_MAX_BYTES) {
        void stopRecording(button, onUploadComplete, onUploadError, onStatus, "max_size");
        return;
      }
      const index = chunkIndex;
      chunkIndex += 1;
      void enqueueRecordingChunk(event.data, index).catch((error) => {
        if (isIgnorableLateChunkError(error)) return;
        console.error("Voice chunk upload failed:", error);
        void stopRecording(button, onUploadComplete, onUploadError, onStatus, "upload_error");
      });
    };
    mediaRecorder.onstop = () => {
      stream.getTracks().forEach((track) => track.stop());
    };

    mediaRecorder.start(CHUNK_TIMESLICE_MS);
    recordStartedAt = Date.now();
    button.classList.add("is-recording");
    button.setAttribute("aria-pressed", "true");
    button.setAttribute("aria-label", "Stop recording");
    onStatus?.("recording");

    onTick?.(0);
    tickTimer = setInterval(() => {
      if (mediaRecorder?.state !== "recording") return;
      const elapsed = Math.min(
        MAX_RECORD_SECONDS,
        Math.floor((Date.now() - recordStartedAt) / 1000)
      );
      onTick?.(elapsed);
    }, 250);

    recordTimer = setTimeout(() => {
      if (mediaRecorder?.state === "recording") {
        void stopRecording(button, onUploadComplete, onUploadError, onStatus, "max_length");
      }
    }, MAX_RECORD_SECONDS * 1000);
  } catch (err) {
    onStatus?.("denied");
    onUploadError?.(err);
    console.error("Microphone access failed:", err);
  }
}

async function stopRecording(
  button,
  onUploadComplete,
  onUploadError,
  onStatus,
  reason = "stopped"
) {
  if (isStopping) return;
  isStopping = true;

  if (recordTimer) {
    clearTimeout(recordTimer);
    recordTimer = null;
  }
  if (tickTimer) {
    clearInterval(tickTimer);
    tickTimer = null;
  }
  if (button) {
    button.classList.remove("is-recording");
    button.setAttribute("aria-pressed", "false");
    button.setAttribute("aria-label", "Record voice note");
  }

  const wasRecording = mediaRecorder?.state === "recording";
  if (wasRecording) {
    await new Promise((resolve) => {
      const recorder = mediaRecorder;
      if (recorder.state === "inactive") {
        resolve();
        return;
      }
      recorder.addEventListener("stop", () => resolve(), { once: true });
      recorder.stop();
    });
    if (reason === "max_length") {
      onStatus?.("max_length");
    } else if (reason === "max_size") {
      onStatus?.("max_size");
    } else if (reason !== "upload_error") {
      onStatus?.("uploading");
    }
  }

  if (reason === "upload_error") {
    onStatus?.("upload_error");
    resetUploadState();
    mediaRecorder = null;
    isStopping = false;
    return;
  }

  if (!wasRecording && chunkIndex === 0) {
    isStopping = false;
    return;
  }

  try {
    await Promise.all(pendingChunkUploads);
    if (!uploadId) {
      throw new Error("No audio captured");
    }
    const ctx = getUploadContext();
    const result = await completeVoiceUpload({
      uploadId,
      grievanceId: ctx.grievanceId,
      complainantId: ctx.complainantId,
      flaskSessionId: ctx.flaskSessionId,
      rasaSessionId: ctx.rasaSessionId,
    });
    uploadFinalized = true;
    onStatus?.("stopped");
    onUploadComplete?.(result);
  } catch (error) {
    console.error("Voice upload finalize failed:", error);
    onStatus?.("upload_error");
    onUploadError?.(error);
  } finally {
    resetUploadState();
    mediaRecorder = null;
    isStopping = false;
  }
}
