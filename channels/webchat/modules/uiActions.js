// UI Actions Module - Pure UI manipulation functions
// Handles DOM manipulation, message display, and UI state updates

// Global state (will be initialized from app.js)
let messages;
let grievanceId = null;

// Initialize UI Actions with DOM elements
export function initializeUIActions(
  messagesElement,
  initialGrievanceId = null
) {
  messages = messagesElement;
  grievanceId = initialGrievanceId;
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
      // This will be handled by the event handler in app.js
      window.handleQuickReplyClick(reply.payload);
      messages.removeChild(quickRepliesDiv);
    };
    quickRepliesDiv.appendChild(button);
  });

  messages.appendChild(quickRepliesDiv);
  messages.scrollTop = messages.scrollHeight;
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
}

export function getGrievanceId() {
  return grievanceId;
}

// Error display functions
export function showError(message) {
  appendMessage(message, "received");
}

export function showConnectionError() {
  appendMessage("Connection error. Please try again later.", "received");
}

export function showTimeoutError() {
  appendMessage("Connection timed out. Please try again later.", "received");
}

export function showReconnectError() {
  appendMessage("Unable to reconnect. Please refresh the page.", "received");
}
