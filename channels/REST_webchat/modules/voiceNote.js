/** CB-01: in-chat voice note recording (MediaRecorder). */

const MAX_SECONDS = 90;

let mediaRecorder = null;
let chunks = [];
let recordTimer = null;
let recordStartedAt = 0;

export function initVoiceNote({
  button,
  onStatus,
  onRecorded,
}) {
  if (!button) return;

  button.addEventListener("click", async (event) => {
    if (button.disabled) {
      event.preventDefault();
      return;
    }
    if (mediaRecorder?.state === "recording") {
      stopRecording(onRecorded, onStatus);
      return;
    }
    await startRecording(button, onStatus, onRecorded);
  });
}

async function startRecording(button, onStatus, onRecorded) {
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
      button.classList.remove("is-recording");
      button.setAttribute("aria-pressed", "false");
    };
    mediaRecorder.start(1000);
    recordStartedAt = Date.now();
    button.classList.add("is-recording");
    button.setAttribute("aria-pressed", "true");
    onStatus?.("recording");

    recordTimer = setTimeout(() => {
      if (mediaRecorder?.state === "recording") {
        stopRecording(onRecorded, onStatus);
        onStatus?.("max_length");
      }
    }, MAX_SECONDS * 1000);
  } catch (err) {
    onStatus?.("denied");
    console.error("Microphone access failed:", err);
  }
}

function stopRecording(onRecorded, onStatus) {
  if (recordTimer) {
    clearTimeout(recordTimer);
    recordTimer = null;
  }
  if (mediaRecorder?.state === "recording") {
    mediaRecorder.stop();
    onStatus?.("stopped");
  }
}
