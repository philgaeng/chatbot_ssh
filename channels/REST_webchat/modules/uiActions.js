// UI Actions Module - Pure UI manipulation functions
// Handles DOM manipulation, message display, and UI state updates

import { get } from "../utterances.js";

// Global state (will be initialized from app.js)
let messages;
let grievanceId = null;
let attachmentButton = null;
let messageInput = null;
let sendButton = null;
let grievanceCreatedInDb = false;

// Initialize UI Actions with DOM elements
export function initializeUIActions(
  messagesElement,
  initialGrievanceId = null,
  options = {}
) {
  messages = messagesElement;
  grievanceId = initialGrievanceId;
  attachmentButton = options.attachmentButton ?? document.getElementById("attachment-button");
  messageInput = options.messageInput ?? document.getElementById("message-input");
  sendButton = options.sendButton ?? document.querySelector("#form .send-button");
  updateAttachButtonState();
}

// Update attach button disabled state and tooltip when grievanceId changes
function updateAttachButtonState() {
  if (!attachmentButton) return;
  const hasGrievance = !!grievanceId;
  const canUploadFiles = hasGrievance && grievanceCreatedInDb;

  attachmentButton.disabled = !canUploadFiles;
  if (!hasGrievance) {
    attachmentButton.title = get("attach_button.start_first");
  } else if (!grievanceCreatedInDb) {
    attachmentButton.title = get("attach_button.saving");
  } else {
    attachmentButton.title = get("attach_button.ready");
  }
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

// File status display functions
export function updateFileStatus(fileId, data) {
  const { status, progress, result, error } = data;

  // Create or update file status message
  let statusElement = document.getElementById(`file-status-${fileId}`);
  if (!statusElement) {
    statusElement = document.createElement("div");
    statusElement.id = `file-status-${fileId}`;
    statusElement.className = "file-status";
    messages.appendChild(statusElement);
  }

  // Update status message
  let statusMessage = "";
  switch (status) {
    case "PENDING":
      statusMessage = "Processing files...";
      break;
    case "STARTED":
      if (result && result.file_type === "audio") {
        statusMessage = progress
          ? `Transcribing audio: ${progress}%`
          : "Transcribing audio...";
      } else {
        statusMessage = progress
          ? `Processing files: ${progress}%`
          : "Processing files...";
      }
      break;
    case "SUCCESS":
      if (result && result.file_type === "audio") {
        statusMessage =
          "Voice recording processed and transcribed successfully";
      } else {
        statusMessage = "Files processed successfully";
      }
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
      let errorMsg = error || "Unknown error";
      if (result && result.file_type === "audio") {
        statusMessage = `Failed to process voice recording: ${errorMsg}`;
      } else {
        statusMessage = `Failed to process files: ${errorMsg}`;
      }
      // Always show failure message to user
      appendMessage(statusMessage, "received");
      console.error("Task failed:", errorMsg);
      break;
    default:
      statusMessage = `Status: ${status}`;
  }

  statusElement.textContent = statusMessage;
  statusElement.setAttribute("data-status", status);

  // Remove status element after a delay
  if (status === "SUCCESS" || status === "FAILURE") {
    setTimeout(() => {
      if (statusElement && statusElement.parentNode) {
        statusElement.remove();
      }
    }, 5000);
  }
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
