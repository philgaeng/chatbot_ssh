// Import configurations
import {
  FILE_UPLOAD_CONFIG,
  SESSION_CONFIG,
  ORCHESTRATOR_CONFIG,
} from "./config.js";

// Import modules
import * as eventHandlers from "./modules/eventHandlers.js";
import * as uiActions from "./modules/uiActions.js";
import { get, format, ADD_MORE_PAYLOAD, GO_BACK_PAYLOAD } from "./utterances.js";

// Make FILE_UPLOAD_CONFIG globally available for the file upload function
window.FILE_UPLOAD_CONFIG = FILE_UPLOAD_CONFIG;

// DOM Elements
let chatWidget;
let chatLauncher;
let closeButton;
let messageForm;
let messageInput;
let messages;
let fileInput;
let attachmentButton;

// Session and State Variables
let messageRetryCount = 0;
const MAX_RETRIES = 3;
const RETRY_DELAY = 500; // 500ms

// Global state
window.grievanceId = null;
window.currentRetryTimer = null;
window.hasReceivedResponse = false;
window.introductionSent = false;
window.introductionWindowTimer = null;
window.sessionInitialized = false;
window.lastBotMessageText = "";
window.lastBotQuickReplies = null;

// File type constants
const FILE_TYPES = {
  IMAGE: {
    extensions: ["png", "jpg", "jpeg", "gif", "bmp", "webp", "heic", "heif"],
    maxSize: 5 * 1024 * 1024, // 5MB
  },
  VIDEO: {
    extensions: ["mp4", "mov", "avi", "mkv", "wmv", "flv", "webm", "m4v"],
    maxSize: 50 * 1024 * 1024, // 50MB
  },
  AUDIO: {
    extensions: ["mp3", "wav", "ogg", "m4a", "aac", "wma", "flac", "webm"],
    maxSize: 10 * 1024 * 1024, // 10MB
  },
  DOCUMENT: {
    extensions: [
      "pdf",
      "doc",
      "docx",
      "xls",
      "xlsx",
      "ppt",
      "pptx",
      "txt",
      "rtf",
      "csv",
      "odt",
      "ods",
      "odp",
    ],
    maxSize: 2 * 1024 * 1024, // 2MB
  },
  ARCHIVE: {
    extensions: ["zip", "rar", "7z", "tar", "gz"],
    maxSize: 20 * 1024 * 1024, // 20MB
  },
};

// Function to get URL parameters
function getUrlParams() {
  const params = new URLSearchParams(window.location.search);
  return {
    province: params.get("province"),
    district: params.get("district"),
  };
}

// Create a temporary session ID
const tempSessionId =
  "temp_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);

function generateSessionId() {
  return "temp_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);
}

// Make getSessionId available globally
window.getSessionId = function () {
  const storage = localStorage;
  const storageKey = SESSION_CONFIG.STORAGE_KEY;
  return storage.getItem(storageKey) || tempSessionId;
};

// Make grievance ID status available globally for debugging
window.getGrievanceIdStatus = function () {
  return {
    grievanceId: window.grievanceId,
    hasGrievanceId: !!window.grievanceId,
    sessionId: window.getSessionId(),
  };
};

const ORCHESTRATOR_URL = ORCHESTRATOR_CONFIG.URL;

async function restSendMessage(message, additionalData = {}) {
  const userId = window.getSessionId();

  const payload = {
    user_id: userId,
    message_id: null,
    text: "",
    payload: null,
    channel: "webchat-rest",
  };

  if (message && message.startsWith("/")) {
    payload.payload = message;
  } else {
    payload.text = message || "";
  }

  if (additionalData && Object.keys(additionalData).length > 0) {
    payload.metadata = additionalData;
  }

  try {
    const resp = await fetch(ORCHESTRATOR_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!resp.ok) {
      console.error("Orchestrator error:", await resp.text());
      uiActions.showError(get("errors.connection"));
      return false;
    }

    const data = await resp.json();
    handleOrchestratorResponse(data);
    return true;
  } catch (error) {
    console.error("Error calling orchestrator:", error);
    uiActions.showError(get("errors.connection"));
    return false;
  }
}

window.safeSendMessage = restSendMessage;

function handleOrchestratorResponse(response) {
  const { messages = [], next_state, expected_input_type } = response || {};

  if (!Array.isArray(messages)) {
    return;
  }

  // Mark that we received a response - stops retry logic and prevents false "connection issue" error
  window.hasReceivedResponse = true;
  if (window.currentRetryTimer) {
    clearTimeout(window.currentRetryTimer);
    window.currentRetryTimer = null;
  }
  if (window.introductionWindowTimer) {
    clearTimeout(window.introductionWindowTimer);
    window.introductionWindowTimer = null;
  }

  messages.forEach((m) => {
    if (m.text) {
      window.lastBotMessageText = m.text;
      uiActions.appendMessage(m.text, "received");
    }
    if (m.buttons && m.buttons.length > 0) {
      window.lastBotQuickReplies = (m.buttons || []).map((btn) => ({
        title: btn.title || btn.text || "",
        payload: btn.payload,
      }));
      eventHandlers.renderQuickReplies(m.buttons);
    }
    if (m.custom) {
      eventHandlers.handleCustomPayload(m.custom);
    }
    if (m.json_message) {
      eventHandlers.handleCustomPayload(m.json_message);
    }
  });

  // Optionally, use next_state / expected_input_type to adjust UI in the future
}

// Send introduction message (async: restSendMessage returns a Promise; must await
// before setting introductionSent, otherwise refresh/reopen can skip retries while
// the request is still in flight.)
async function sendIntroduceMessage() {
  if (window.introductionSent) {
    console.log("Introduction already sent, skipping...");
    return;
  }

  const { province, district } = getUrlParams();
  const flaskSessionId = window.flaskSessionId || window.getSessionId();
  const initialMessage =
    province && district
      ? `/introduce{"province": "${province}", "district": "${district}", "flask_session_id": "${flaskSessionId}"}`
      : `/introduce{"flask_session_id": "${flaskSessionId}"}`;

  console.log("Preparing to send initial message:", initialMessage);

  const ok = await restSendMessage(initialMessage, {
    province,
    district,
    flask_session_id: flaskSessionId,
  });

  if (!ok) {
    return;
  }

  console.log("Initial message sent successfully");
  window.introductionSent = true;

  if (!window.hasReceivedResponse) {
    window.introductionWindowTimer = setTimeout(() => {
      console.log("Introduction window closed - no more retries allowed");
      if (window.currentRetryTimer) {
        clearTimeout(window.currentRetryTimer);
        window.currentRetryTimer = null;
      }
      if (messageRetryCount >= MAX_RETRIES) {
        uiActions.showError(get("errors.connection"));
      }
    }, 3000);

    const retryTimer = setTimeout(() => {
      if (messageRetryCount < MAX_RETRIES && !window.hasReceivedResponse) {
        messageRetryCount++;
        console.log(
          `No response received, retrying (${messageRetryCount}/${MAX_RETRIES})...`
        );
        window.introductionSent = false;
        void sendIntroduceMessage();
      }
    }, RETRY_DELAY);

    window.currentRetryTimer = retryTimer;
  }
}

// Make sendIntroduceMessage available globally
window.sendIntroduceMessage = sendIntroduceMessage;

let taskStatusSocket = null;

function setupTaskStatusSocket() {
  // Socket.IO client is loaded via CDN in index.html as global `io`
  if (typeof io === "undefined") {
    console.warn("Socket.IO client not available; task status socket disabled.");
    return;
  }

  try {
    const roomId = window.flaskSessionId || window.getSessionId();
    taskStatusSocket = io("/accessible-socket.io", {
      transports: ["websocket"],
      path: "/accessible-socket.io",
    });

    taskStatusSocket.on("connect", () => {
      console.log("REST_webchat Socket.IO connected, joining room:", roomId);
      taskStatusSocket.emit("join", { room: roomId });
    });

    taskStatusSocket.on("task_status", (data) => {
      console.log("REST_webchat received task_status:", data);
      const { status, data: taskData, grievance_id, task_name } = data || {};

      if (grievance_id) {
        uiActions.setGrievanceId(grievance_id);
      }

      // Only handle LLM grievance classification task here
      if (
        task_name === "classify_and_summarize_grievance_task" &&
        status === "SUCCESS" &&
        taskData
      ) {
        const summary = taskData.grievance_summary;
        const categories = taskData.grievance_categories;

        if (summary || (Array.isArray(categories) && categories.length > 0)) {
          let humanMessage = get("task_status.classification_done");
          if (Array.isArray(categories) && categories.length > 0) {
            humanMessage += `\n\nCategories: ${categories.join(", ")}`;
          }
          if (summary) {
            humanMessage += `\n\nSummary: ${summary}`;
          }
          uiActions.appendMessage(humanMessage, "received");
        } else {
          uiActions.appendMessage(get("task_status.classification_done_fallback"), "received");
        }
      }
    });

    taskStatusSocket.on("connect_error", (err) => {
      console.warn("REST_webchat Socket.IO connect_error:", err.message);
    });
  } catch (e) {
    console.error("Failed to set up task status Socket.IO connection:", e);
  }
}

// Initialize the chat application
async function initializeChat() {
  // Get DOM elements
  chatWidget = document.getElementById("chat-widget");
  chatLauncher = document.getElementById("chat-launcher");
  closeButton = document.querySelector(".close-button");
  messageForm = document.getElementById("form");
  messageInput = document.getElementById("message-input");
  fileInput = document.getElementById("file-input");
  attachmentButton = document.getElementById("attachment-button");
  messages = document.getElementById("messages");

  // Initialize UI Actions with DOM elements (pass refs for attach button, input lock)
  uiActions.initializeUIActions(messages, window.grievanceId, {
    attachmentButton,
    messageInput,
    sendButton: document.querySelector("#form .send-button"),
  });

  // Initialize chat widget visibility
  chatWidget.style.display = "none";
  chatLauncher.style.display = "flex";

  // Initialize Socket.IO connection for task status updates (classification, etc.)
  setupTaskStatusSocket();

  // Send initial introduction message via REST
  await sendIntroduceMessage();

  // Set up event listeners
  setupEventListeners();
}

// Set up UI event listeners
function setupEventListeners() {
  chatLauncher.addEventListener("click", () => {
    chatWidget.style.display = "flex";
    chatLauncher.style.display = "none";
    messageInput.focus();
    if (!window.introductionSent) {
      void sendIntroduceMessage();
    }
  });

  closeButton.addEventListener("click", () => {
    chatWidget.style.display = "none";
    chatLauncher.style.display = "flex";
  });

  // File attachment handling
  attachmentButton.addEventListener("click", () => {
    fileInput.click();
  });

  // Allow backend to open the file picker (e.g. "Add pictures and documents" in Modify grievance)
  window.openFileUploadModal = function () {
    if (fileInput) fileInput.click();
  };

  // Form submission
  messageForm.addEventListener("submit", handleMessageSubmit);

  // File input change
  fileInput.addEventListener("change", handleFileSelection);

  // Enter to send, Shift+Enter for newline (so attached file is sent on Enter instead of form default)
  messageInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      messageForm.requestSubmit();
    }
  });

  // Add auto-resize functionality to message input
  messageInput.addEventListener("input", function () {
    // Reset height to auto to get the correct scrollHeight
    this.style.height = "auto";
    // Set new height based on scrollHeight, but cap it at max-height via CSS
    this.style.height =
      Math.min(this.scrollHeight, parseInt(getComputedStyle(this).maxHeight)) +
      "px";
  });
}

function resetFrontendState() {
  window.grievanceId = null;
  window.hasReceivedResponse = false;
  window.introductionSent = false;
  window.sessionInitialized = false;
  window.lastBotMessageText = "";
  window.lastBotQuickReplies = null;

  if (window.currentRetryTimer) {
    clearTimeout(window.currentRetryTimer);
    window.currentRetryTimer = null;
  }
  if (window.introductionWindowTimer) {
    clearTimeout(window.introductionWindowTimer);
    window.introductionWindowTimer = null;
  }

  selectedFiles = [];
  if (fileInput) fileInput.value = "";
  if (messageInput) {
    messageInput.value = "";
    messageInput.style.height = "44px";
  }

  uiActions.setGrievanceId(null);
  uiActions.setGrievanceCreatedInDb(false);
  uiActions.clearMessages();
}

window.handleClearSessionCommand = function () {
  resetFrontendState();
  chatWidget.style.display = "none";
  chatLauncher.style.display = "flex";

  const storage = localStorage;
  const storageKey = SESSION_CONFIG.STORAGE_KEY;
  storage.setItem(storageKey, generateSessionId());
};

window.handleCloseWindowCommand = function () {
  // Browser may block closing tabs not opened by script.
  window.close();

  setTimeout(() => {
    if (!window.closed) {
      chatWidget.style.display = "none";
      chatLauncher.style.display = "flex";
      uiActions.appendMessage(
        "For security reasons, your browser may block automatic tab closing. Please close this tab manually.",
        "received"
      );
    }
  }, 100);
};

// Handle message submission
async function handleMessageSubmit(e) {
  e.preventDefault();
  const message = messageInput.value.trim();

  if (message) {
    // Once the user has answered (by typing), clear any existing quick replies
    // so older buttons cannot be clicked out of context.
    const quickReplyBlocks = messages.querySelectorAll(".quick-replies");
    quickReplyBlocks.forEach((el) => el.remove());

    uiActions.appendMessage(message, "sent");
    window.safeSendMessage(message);
    messageInput.value = "";
    messageInput.style.height = "44px";
  }

  // Handle file upload if files are selected: lock input, upload, then unlock when done or on failure
  if (selectedFiles.length > 0) {
    uiActions.setInputLocked(true);
    const uploaded = await handleFileUpload(selectedFiles);
    if (!uploaded) {
      uiActions.setInputLocked(false);
      // Keep files in preview so user can retry
      return;
    }
    selectedFiles = [];
    if (fileInput) fileInput.value = "";
    displayFilePreview();
    // Unlock happens when all files report SUCCESS in updateFileStatus (post-upload message + buttons shown)
  }
}

// Handle file selection
function handleFileSelection(e) {
  const files = Array.from(e.target.files);
  if (files.length > 0) {
    handleSelectedFiles(files);
  }
}

// Take snapshot of last bot message and quick replies (before file upload flow)
function takeFileUploadSnapshot() {
  if (fileUploadSnapshot) return; // Keep same snapshot across "Add more files" rounds
  fileUploadSnapshot = {
    lastBotMessageText: window.lastBotMessageText || "",
    lastBotQuickReplies: Array.isArray(window.lastBotQuickReplies)
      ? window.lastBotQuickReplies.map((r) => ({ ...r }))
      : [],
  };
}

// Handle selected files
function handleSelectedFiles(files) {
  selectedFiles = [];

  files.forEach((file) => {
    const maxFileSize = FILE_UPLOAD_CONFIG.MAX_SIZE_MB * 1024 * 1024;
    if (file.size > maxFileSize) {
      compressFile(file).then((compressedFile) => {
        selectedFiles.push(compressedFile);
        takeFileUploadSnapshot();
        displayFilePreview();
      });
    } else {
      selectedFiles.push(file);
    }
  });

  takeFileUploadSnapshot();
  displayFilePreview();
}

// Display file preview
function displayFilePreview() {
  const onFileRemove = (index) => {
    selectedFiles.splice(index, 1);
    displayFilePreview();
  };

  const previewContainer = uiActions.displayFilePreview(
    selectedFiles,
    onFileRemove
  );
  if (previewContainer) {
    messageForm.parentNode.insertBefore(previewContainer, messageForm);
  }
}

// Compress file if needed
function compressFile(file) {
  return new Promise((resolve) => {
    if (file.type.startsWith("image/")) {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = function (e) {
        const img = new Image();
        img.src = e.target.result;
        img.onload = function () {
          const canvas = document.createElement("canvas");
          const ctx = canvas.getContext("2d");

          let width = img.width;
          let height = img.height;
          const maxSize = 1200;

          if (width > height && width > maxSize) {
            height = (height * maxSize) / width;
            width = maxSize;
          } else if (height > maxSize) {
            width = (width * maxSize) / height;
            height = maxSize;
          }

          canvas.width = width;
          canvas.height = height;
          ctx.drawImage(img, 0, 0, width, height);

          canvas.toBlob(
            (blob) => {
              const compressedFile = new File([blob], file.name, {
                type: file.type,
                lastModified: file.lastModified,
              });
              resolve(compressedFile);
            },
            file.type,
            0.7
          );
        };
      };
    } else {
      resolve(file);
    }
  });
}

// Global variables
let selectedFiles = [];

// File upload robustness: snapshot of chat state before user enters file flow (persisted across "Add more" rounds)
let fileUploadSnapshot = null;
// Current upload batch: track file IDs and statuses to know when all are done
let currentUploadFileIds = [];
let currentUploadStatuses = {};

// Handle file upload. Returns true if upload was attempted and succeeded, false otherwise (caller keeps attachment preview when false).
async function handleFileUpload(files) {
  console.log("Starting file upload process...", files);
  console.log("Current window.grievanceId:", window.grievanceId);

  if (!window.grievanceId) {
    uiActions.appendMessage(get("file_upload.no_grievance"), "received");
    return false;
  }

  const formData = new FormData();
  const sessionId = window.getSessionId();
  formData.append("grievance_id", window.grievanceId);
  formData.append("client_type", "webchat-rest");
  formData.append("rasa_session_id", sessionId);
  formData.append("flask_session_id", window.flaskSessionId || sessionId);

  // Check for audio files
  const audioFiles = Array.from(files).filter((file) => {
    const ext = file.name.split(".").pop().toLowerCase();
    return FILE_TYPES.AUDIO.extensions.includes(ext);
  });

  if (audioFiles.length > 0) {
    console.log("Audio files detected:", audioFiles);
    uiActions.appendMessage(get("file_upload.voice_detected"), "received");
  }

  // Check file sizes
  const oversizedFiles = Array.from(files).filter((file) => {
    const ext = file.name.split(".").pop().toLowerCase();
    for (const type of Object.values(FILE_TYPES)) {
      if (type.extensions.includes(ext)) {
        return file.size > type.maxSize;
      }
    }
    return file.size > 10 * 1024 * 1024; // Default 10MB limit
  });

  if (oversizedFiles.length > 0) {
    console.log("Oversized files detected:", oversizedFiles);
    uiActions.appendMessage(
      `${get("file_upload.oversized_prefix")} ${oversizedFiles.map((f) => f.name).join(", ")}`,
      "received"
    );
  }

  // Add valid files to form data
  const validFiles = Array.from(files).filter(
    (file) => !oversizedFiles.includes(file)
  );
  console.log("Valid files to upload:", validFiles);

  for (const file of validFiles) {
    formData.append("files[]", file);
  }

  if (validFiles.length === 0) {
    return false;
  }

  try {
    console.log("Sending file upload request...");
    const response = await fetch(FILE_UPLOAD_CONFIG.URL, {
      method: "POST",
      body: formData,
    });

    let data;
    const contentType = response.headers.get("content-type") || "";
    try {
      data = contentType.includes("application/json")
        ? await response.json()
        : { error: await response.text() || `Server error (${response.status})` };
    } catch (_) {
      data = { error: await response.text().catch(() => `Server error (${response.status})`) };
    }
    console.log("File upload response:", data);

    if (response.ok) {
      eventHandlers.handleFileUploadApiResponse({
        ok: true,
        data: data,
        audioFiles: audioFiles,
      });
      if (data.files && data.files.length > 0) {
        currentUploadFileIds = data.files;
        currentUploadStatuses = {};
        pollFileStatus(data.files);
      } else {
        showPostUploadMessageAndUnlock();
      }
      return true;
    } else {
      const errMsg = data.error || data.detail || data.message || `Upload failed (${response.status})`;
      console.error("Upload failed:", errMsg);
      eventHandlers.handleApiError(errMsg, "File upload");
      return false;
    }
  } catch (error) {
    console.error("Error uploading files:", error);
    eventHandlers.handleApiError(error, "File upload");
    return false;
  }
}

// Poll file status
async function pollFileStatus(fileIds) {
  const maxAttempts = 30; // 5 minutes total (10s * 30)
  let attempts = 0;

  const poll = async () => {
    try {
      console.log(
        `Polling file status (attempt ${attempts + 1}/${maxAttempts}):`,
        fileIds
      );
      const statuses = await Promise.all(
        fileIds.map((fileId) =>
          fetch(`/file-status/${fileId}`).then(async (res) => {
            if (!res.ok) {
              // Try to parse JSON error, or fallback to a default
              try {
                const data = await res.json();
                return data;
              } catch {
                return { status: "NOT_FOUND", message: "File not found" };
              }
            }
            return res.json();
          })
        )
      );
      console.log("File status response:", statuses);

      // Update status for each file
      statuses.forEach((data, index) => {
        if (data.status) {
          updateFileStatus(fileIds[index], data);
        }
      });

      // Check if all files are processed
      const allProcessed = statuses.every(
        (data) => data.status === "SUCCESS" || data.status === "FAILURE"
      );

      if (!allProcessed && attempts < maxAttempts) {
        attempts++;
        // Poll more often at first (2s), then every 10s
        const delayMs = attempts <= 3 ? 2000 : 10000;
        setTimeout(poll, delayMs);
      } else if (!allProcessed) {
        console.log("Max polling attempts reached");
        uiActions.appendMessage(get("file_upload.processing_long"), "received");
        uiActions.setInputLocked(false);
        currentUploadFileIds = [];
        currentUploadStatuses = {};
      }
    } catch (error) {
      console.error("Error polling file status:", error);
    }
  };

  // Start polling
  poll();
}

function showPostUploadMessageAndUnlock() {
  uiActions.appendMessage(get("file_upload.post_upload"), "received");
  uiActions.replaceQuickReplies([
    { title: get("file_upload.buttons.add_more"), payload: ADD_MORE_PAYLOAD },
    { title: get("file_upload.buttons.go_back"), payload: GO_BACK_PAYLOAD },
  ]);
  uiActions.setInputLocked(false);
  currentUploadFileIds = [];
  currentUploadStatuses = {};
}

// Check if all files in current batch are terminal; if all SUCCESS show post-upload and unlock, else if any FAILURE show failure message + same buttons
function checkUploadBatchComplete() {
  if (currentUploadFileIds.length === 0) return;
  const statuses = currentUploadFileIds.map((id) => currentUploadStatuses[id]);
  const allTerminal = statuses.every(
    (s) => s === "SUCCESS" || s === "FAILURE"
  );
  if (!allTerminal) return;
  const allSuccess = statuses.every((s) => s === "SUCCESS");
  if (allSuccess) {
    showPostUploadMessageAndUnlock();
  } else {
    showFailureMessageAndUnlock();
  }
}

// On upload failure: inform user and offer Add more / Go back (same flow as success so user can recover)
function showFailureMessageAndUnlock() {
  uiActions.appendMessage(get("file_upload.failure"), "received");
  uiActions.replaceQuickReplies([
    { title: get("file_upload.buttons.add_more"), payload: ADD_MORE_PAYLOAD },
    { title: get("file_upload.buttons.go_back"), payload: GO_BACK_PAYLOAD },
  ]);
  uiActions.setInputLocked(false);
  currentUploadFileIds = [];
  currentUploadStatuses = {};
}

// Update file status in UI
function updateFileStatus(fileId, data) {
  const { status, progress, result, error } = data;

  currentUploadStatuses[fileId] = status;

  // Get messages container
  const chatMessages = document.getElementById("messages");
  if (!chatMessages) {
    console.error("Messages container not found");
    return;
  }

  // Create or update file status message
  let statusElement = document.getElementById(`file-status-${fileId}`);
  const prevStatus = statusElement
    ? statusElement.getAttribute("data-status")
    : null;
  if (!statusElement) {
    statusElement = document.createElement("div");
    statusElement.id = `file-status-${fileId}`;
    statusElement.className = "file-status";
    chatMessages.appendChild(statusElement);
  }

  // Update status message
  let statusMessage = "";
  switch (status) {
    case "PENDING":
      statusMessage = get("file_upload.processing");
      break;
    case "STARTED":
      if (result && result.file_type === "audio") {
        statusMessage = progress
          ? format(get("file_upload.transcribing_progress"), { progress })
          : get("file_upload.transcribing");
      } else {
        statusMessage = progress
          ? format(get("file_upload.processing_progress"), { progress })
          : get("file_upload.processing");
      }
      break;
    case "SUCCESS":
      if (result && result.file_type === "audio") {
        statusMessage = get("file_upload.voice_success");
      } else {
        statusMessage = get("file_upload.files_success");
      }
      if (result) {
        if (result.grievance_id) {
          window.grievanceId = result.grievance_id;
        }
        if (result.message) {
          uiActions.appendMessage(result.message, "received");
        }
      }
      if (prevStatus !== "SUCCESS" && !(result && result.message)) {
        const notice = (data && data.message) || get("file_upload.file_saved");
        uiActions.appendMessage(notice, "received");
      }
      break;
    case "FAILURE":
      let errorMsg = error || "Unknown error";
      if (result && result.file_type === "audio") {
        statusMessage = `${get("file_upload.voice_failure_prefix")} ${errorMsg}`;
      } else {
        statusMessage = `${get("file_upload.files_failure_prefix")} ${errorMsg}`;
      }
      uiActions.appendMessage(statusMessage, "received");
      console.error("Task failed:", errorMsg);
      break;
    default:
      statusMessage = `${get("file_upload.status_prefix")} ${status}`;
  }

  statusElement.textContent = statusMessage;
  statusElement.setAttribute("data-status", status);

  if (status === "SUCCESS" || status === "FAILURE") {
    checkUploadBatchComplete();
    setTimeout(() => {
      if (statusElement && statusElement.parentNode) {
        statusElement.remove();
      }
    }, 5000);
  }
}

// "Go back to chat": restore snapshot, transition message, unlock (no orchestrator call)
function handleGoBackToChat() {
  uiActions.appendMessage(get("file_upload.transition"), "received");
  if (fileUploadSnapshot) {
    if (fileUploadSnapshot.lastBotMessageText) {
      uiActions.appendMessage(fileUploadSnapshot.lastBotMessageText, "received");
    }
    if (
      Array.isArray(fileUploadSnapshot.lastBotQuickReplies) &&
      fileUploadSnapshot.lastBotQuickReplies.length > 0
    ) {
      uiActions.replaceQuickReplies(fileUploadSnapshot.lastBotQuickReplies);
    }
    fileUploadSnapshot = null;
  } else {
    uiActions.replaceQuickReplies([]); // Clear Add more / Go back buttons
    uiActions.appendMessage(get("file_upload.continue_below"), "received");
  }
  uiActions.setInputLocked(false);
}

// "Add more files": re-open file picker (no orchestrator call)
function handleAddMoreFiles() {
  if (fileInput) fileInput.click();
}

// Set up global handlers (eventHandlers.handleQuickReplyClick will call these for file-upload payloads)
window.handleGoBackToChat = handleGoBackToChat;
window.handleAddMoreFiles = handleAddMoreFiles;
window.handleQuickReplyClick = eventHandlers.handleQuickReplyClick;

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  void initializeChat();
});
