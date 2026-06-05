/** CB-01: voice note recording (MediaRecorder). */

export const MAX_RECORD_SECONDS = 45;

let mediaRecorder = null;
let chunks = [];
let recordTimer = null;
let tickTimer = null;
let recordStartedAt = 0;

export function initVoiceNote({
  button,
  onStatus,
  onTick,
  onRecorded,
}) {
  if (!button) return;

  button.addEventListener("click", async (event) => {
    if (button.disabled) {
      event.preventDefault();
      return;
    }
    if (mediaRecorder?.state === "recording") {
      stopRecording(button, onRecorded, onStatus);
      return;
    }
    await startRecording(button, onStatus, onRecorded, onTick);
  });
}

async function startRecording(button, onStatus, onRecorded, onTick) {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeType = MediaRecorder.isTypeSupported("audio/webm")
      ? "audio/webm"
      : "audio/mp4";
    mediaRecorder = new MediaRecorder(stream, { mimeType });
    chunks = [];
    mediaRecorder.ondataavailable = (e) => {
      if (e.data?.size) chunks.push(e.data);
    };
    mediaRecorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(chunks, { type: mimeType });
      const ext = mimeType.includes("webm") ? "webm" : "m4a";
      const file = new File([blob], `voice_note_${Date.now()}.${ext}`, {
        type: mimeType,
      });
      onRecorded?.(file);
    };
    mediaRecorder.start(1000);
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
        stopRecording(button, onRecorded, onStatus);
        onStatus?.("max_length");
      }
    }, MAX_RECORD_SECONDS * 1000);
  } catch (err) {
    onStatus?.("denied");
    console.error("Microphone access failed:", err);
  }
}

function stopRecording(button, onRecorded, onStatus) {
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
  if (mediaRecorder?.state === "recording") {
    mediaRecorder.stop();
    onStatus?.("stopped");
  }
}
