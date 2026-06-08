// UI Actions Module - Pure UI manipulation functions
// Handles DOM manipulation, message display, and UI state updates

import { format, get } from "../utterances.js";

// Global state (will be initialized from app.js)
let messages;
let grievanceId = null;
let attachmentButton = null;
let voiceNoteButton = null;
let messageInput = null;
let sendButton = null;
let voiceNoteEnabled = false;
let grievanceCreatedInDb = false;
let voiceStatusBanner = null;
let voiceStatusBannerText = null;

// Initialize UI Actions with DOM elements
export function initializeUIActions(
  messagesElement,
  initialGrievanceId = null,
  options = {}
) {
  messages = messagesElement;
  grievanceId = initialGrievanceId;
  attachmentButton = options.attachmentButton ?? document.getElementById("attachment-button");
  voiceNoteButton = options.voiceNoteButton ?? document.getElementById("voice-note-button");
  messageInput = options.messageInput ?? document.getElementById("message-input");
  sendButton = options.sendButton ?? document.querySelector("#form .send-button");
  voiceStatusBanner = document.getElementById("voice-status-banner");
  voiceStatusBannerText = voiceStatusBanner;
  updateAttachButtonState();
}

/** Light-blue banner above composer toolbar; each call replaces prior text. */
export function setVoiceStatusBanner(text, { error = false, recording = false } = {}) {
  if (!voiceStatusBanner) {
    voiceStatusBanner = document.getElementById("voice-status-banner");
    voiceStatusBannerText = voiceStatusBanner;
  }
  if (!voiceStatusBanner) return;
  const message = (text || "").trim();
  if (!message) {
    clearVoiceStatusBanner();
    return;
  }
  voiceStatusBanner.textContent = message;
  voiceStatusBanner.classList.toggle("is-error", !!error);
  voiceStatusBanner.classList.toggle("is-recording", !!recording);
  voiceStatusBanner.classList.remove("hidden");
}

export function clearVoiceStatusBanner() {
  if (!voiceStatusBanner) {
    voiceStatusBanner = document.getElementById("voice-status-banner");
  }
  if (!voiceStatusBanner) return;
  voiceStatusBanner.textContent = "";
  voiceStatusBanner.classList.remove("is-error", "is-recording");
  voiceStatusBanner.classList.add("hidden");
}

// Update attach button disabled state and tooltip when grievanceId changes
function updateAttachButtonState() {
  const hasGrievance = !!grievanceId;
  const canUploadFiles = hasGrievance && grievanceCreatedInDb;
  // Voice at description step: allow upload once grievance_id exists (DB row ensured on upload).
  const canVoice = hasGrievance && voiceNoteEnabled;

  if (attachmentButton) {
    attachmentButton.disabled = !canUploadFiles;
    attachmentButton.classList.toggle("is-active", canUploadFiles);
    if (!hasGrievance) {
      attachmentButton.title = get("attach_button.start_first");
    } else if (!grievanceCreatedInDb) {
      attachmentButton.title = get("attach_button.saving");
    } else {
      attachmentButton.title = get("attach_button.ready");
    }
  }

  if (voiceNoteButton) {
    voiceNoteButton.disabled = !canVoice;
    voiceNoteButton.classList.toggle("is-active", canVoice);
    if (canVoice) {
      voiceNoteButton.title = get("voice_note.tap_to_record");
    } else if (!hasGrievance) {
      voiceNoteButton.title = get("voice_note.need_grievance");
    } else {
      voiceNoteButton.title = get("voice_note.inactive_step");
    }
  }
}

export function setVoiceNoteEnabled(enabled) {
  voiceNoteEnabled = !!enabled;
  if (!voiceNoteEnabled) {
    clearVoiceStatusBanner();
  }
  updateAttachButtonState();
}

// Message display functions
export function appendMessage(msg, type) {
  const timestamp = new Date();
  const messageDiv = document.createElement("div");
  messageDiv.classList.add("message", `message_${type}`);
  messageDiv.textContent = msg;

  const timestampDiv = document.createElement("div");
  timestampDiv.classList.add("timestamp");
  timestampDiv.textContent = formatTimestamp(timestamp);

  const container = document.createElement("div");
  container.appendChild(messageDiv);
  container.appendChild(timestampDiv);

  messages.appendChild(container);
  messages.scrollTop = messages.scrollHeight;
}

export function clearMessages() {
  if (!messages) return;
  messages.innerHTML = "";
}

export function appendQuickReplies(quickReplies) {
  const quickRepliesDiv = document.createElement("div");
  quickRepliesDiv.classList.add("quick-replies");

  quickReplies.forEach((reply) => {
    const button = document.createElement("button");
    button.classList.add("quick-reply-button");
    button.textContent = reply.title;
    button.onclick = () => {
      appendMessage(reply.title, "sent");
      const handledLocally = window.handleQuickReplyClick(reply.payload);
      if (!handledLocally) {
        // Remove all quick-reply groups once a choice is made so old
        // buttons cannot be clicked later in the flow.
        messages
          .querySelectorAll(".quick-replies")
          .forEach((el) => el.remove());
      }
    };
    quickRepliesDiv.appendChild(button);
  });

  messages.appendChild(quickRepliesDiv);
  messages.scrollTop = messages.scrollHeight;
}

// Replace all quick reply blocks with a single set of buttons (e.g. Add more / Go back)
export function replaceQuickReplies(quickReplies) {
  messages.querySelectorAll(".quick-replies").forEach((el) => el.remove());
  if (Array.isArray(quickReplies) && quickReplies.length > 0) {
    appendQuickReplies(quickReplies);
  }
  messages.scrollTop = messages.scrollHeight;
}

// Lock or unlock message input and send button (e.g. during file upload)
export function setInputLocked(locked) {
  if (messageInput) messageInput.disabled = !!locked;
  if (sendButton) sendButton.disabled = !!locked;
}

// Task status display functions
export function updateTaskStatus(taskStatus) {
  const { task_id, status, progress, result, error } = taskStatus;

  // Create or update task status message
  let statusElement = document.getElementById(`task-status-${task_id}`);
  if (!statusElement) {
    statusElement = document.createElement("div");
    statusElement.id = `task-status-${task_id}`;
    statusElement.className = "task-status";
    messages.appendChild(statusElement);
  }

  // Update status message
  let statusMessage = "";
  switch (status) {
    case "PENDING":
      statusMessage = "Processing...";
      break;
    case "STARTED":
      statusMessage = progress ? `Processing: ${progress}%` : "Processing...";
      break;
    case "SUCCESS":
      statusMessage = "Completed successfully";
      if (result) {
        // Handle successful result
        if (result.grievance_id) {
          grievanceId = result.grievance_id;
          window.grievanceId = grievanceId;
        }
        if (result.message) {
          appendMessage(result.message, "received");
        }
      }
      break;
    case "FAILURE":
      statusMessage = `Failed: ${error || "Unknown error"}`;
      break;
    default:
      statusMessage = `Status: ${status}`;
  }

  statusElement.textContent = statusMessage;

  // Remove status message after success/failure
  if (status === "SUCCESS" || status === "FAILURE") {
    setTimeout(() => {
      if (statusElement && statusElement.parentNode) {
        statusElement.remove();
      }
    }, 5000);
  }
}

// File status → composer banner (shared with app.js poll handler)
export function updateFileStatus(fileId, data) {
  const { status, progress, result, error } = data;
  const isAudio = result?.file_type === "audio";
  let statusMessage = "";

  switch (status) {
    case "PENDING":
      statusMessage = isAudio
        ? get("status_banner.voice_processing")
        : get("status_banner.files_processing");
      break;
    case "STARTED":
      if (isAudio) {
        statusMessage = get("status_banner.voice_uploaded_processing");
      } else {
        statusMessage = progress
          ? format(get("status_banner.files_processing_progress"), { progress })
          : get("status_banner.files_processing");
      }
      break;
    case "SUCCESS":
      statusMessage = isAudio
        ? get("status_banner.voice_saved")
        : get("status_banner.files_saved");
      if (result?.grievance_id) {
        grievanceId = result.grievance_id;
        window.grievanceId = grievanceId;
      }
      if (result?.message) {
        appendMessage(result.message, "received");
      }
      break;
    case "FAILURE": {
      const errorMsg = error || "Unknown error";
      statusMessage = isAudio
        ? format(get("status_banner.voice_failure"), { error: errorMsg })
        : format(get("status_banner.files_failure"), { error: errorMsg });
      console.error("Task failed:", errorMsg);
      setVoiceStatusBanner(statusMessage, { error: true });
      return;
    }
    default:
      statusMessage = `${get("file_upload.status_prefix")} ${status}`;
  }

  setVoiceStatusBanner(statusMessage, { error: false });
}

// File preview functions
export function displayFilePreview(selectedFiles, onFileRemove) {
  const existingPreview = document.querySelector(".file-preview");
  if (existingPreview) {
    existingPreview.remove();
  }

  if (selectedFiles.length === 0) return;

  const previewContainer = document.createElement("div");
  previewContainer.classList.add("file-preview");

  selectedFiles.forEach((file, index) => {
    const fileItem = document.createElement("div");
    fileItem.classList.add("file-item");

    const fileName = document.createElement("span");
    fileName.classList.add("file-item-name");
    fileName.textContent = file.name;

    const removeButton = document.createElement("button");
    removeButton.classList.add("file-item-remove");
    removeButton.textContent = "×";
    removeButton.onclick = () => {
      onFileRemove(index);
    };

    fileItem.appendChild(fileName);
    fileItem.appendChild(removeButton);
    previewContainer.appendChild(fileItem);
  });

  // Insert before the form (this will be handled by the caller)
  return previewContainer;
}

// Utility functions
export function formatTimestamp(date) {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function setGrievanceId(id) {
  grievanceId = id;
  window.grievanceId = grievanceId;
  updateAttachButtonState();
}

export function setGrievanceCreatedInDb(value) {
  grievanceCreatedInDb = !!value;
  window.grievanceCreatedInDb = grievanceCreatedInDb;
  updateAttachButtonState();
}

export function getGrievanceId() {
  return grievanceId;
}

// Error display functions
export function showError(message) {
  appendMessage(message, "received");
}

export function showConnectionError() {
  appendMessage(get("errors.connection"), "received");
}

export function showTimeoutError() {
  appendMessage(get("errors.connection_timeout"), "received");
}

export function showReconnectError() {
  appendMessage(get("errors.reconnect"), "received");
}
