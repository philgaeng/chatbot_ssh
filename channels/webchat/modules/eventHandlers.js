// Event Handlers Module - Handles both socket events and API responses
// Centralized event handling for all external communications

import * as uiActions from "./uiActions.js";

// Socket event handlers
export function setupSocketEventHandlers(socket, sessionState) {
  socket.on("connect", () => {
    handleSocketConnect(socket, sessionState);
  });

  socket.on("session_confirm", () => {
    handleSessionConfirm(sessionState);
  });

  socket.on("bot_uttered", (response) => {
    handleBotResponse(response, sessionState);
  });

  socket.on("task_status", (data) => {
    handleTaskStatusEvent(data);
  });

  // Listen for file status updates on the Flask socket
  if (window.flaskSocket) {
    window.flaskSocket.on("connect", () => {
      console.log("🔗 Flask socket connected with ID:", window.flaskSocket.id);

      // Store Flask session ID globally for use in API calls
      window.flaskSessionId = window.flaskSocket.id;
      console.log("🔗 Flask session ID stored:", window.flaskSessionId);
    });

    window.flaskSocket.on("file_status_update", (data) => {
      console.log(
        "🎉 FLASK WEBSOCKET EVENT RECEIVED: file_status_update",
        data
      );
      console.log("Flask socket ID:", window.flaskSocket.id);
      console.log("Session ID from data:", data.session_id);
      handleFileStatusUpdate(data);
    });

    window.flaskSocket.on("task_status", (data) => {
      console.log("🎉 FLASK WEBSOCKET EVENT RECEIVED: task_status", data);
      handleTaskStatusEvent(data);
    });
  } else {
    console.warn(
      "⚠️ Flask socket not available, file status updates will not be received"
    );
  }

  // Error handling
  socket.on("error", (error) => {
    console.error("Socket error:", error);
  });

  socket.on("connect_error", (error) => {
    console.error("Connection error:", error);
    uiActions.showConnectionError();
  });

  socket.on("connect_timeout", () => {
    console.error("Connection timeout");
    uiActions.showTimeoutError();
  });

  socket.on("reconnect_attempt", (attemptNumber) => {
    console.log("Reconnection attempt:", attemptNumber);
  });

  socket.on("reconnect", (attemptNumber) => {
    console.log("Reconnected after", attemptNumber, "attempts");
  });

  socket.on("reconnect_error", (error) => {
    console.error("Reconnection error:", error);
  });

  socket.on("reconnect_failed", () => {
    console.error("Reconnection failed");
    uiActions.showReconnectError();
  });

  socket.on("complainant_uttered", (message) => {
    console.log("📩 User message sent:", message);
  });

  // Error handling
  socket.on("error", (error) => {
    console.error("Socket error:", error);
  });

  socket.on("connect_error", (error) => {
    console.error("Connection error:", error);
    uiActions.showConnectionError();
  });

  socket.on("connect_timeout", () => {
    console.error("Connection timeout");
    uiActions.showTimeoutError();
  });

  socket.on("reconnect_attempt", (attemptNumber) => {
    console.log("Reconnection attempt:", attemptNumber);
  });

  socket.on("reconnect", (attemptNumber) => {
    console.log("Reconnected after", attemptNumber, "attempts");
  });

  socket.on("reconnect_error", (error) => {
    console.error("Reconnection error:", error);
  });

  socket.on("reconnect_failed", () => {
    console.error("Reconnection failed");
    uiActions.showReconnectError();
  });
}

// Socket event handler functions
function handleSocketConnect(socket, sessionState) {
  console.log("Socket connected with ID:", socket.id);
  const storage = localStorage;
  const storageKey = "session_id"; // This should come from config
  storage.setItem(storageKey, socket.id);

  // Reset session state
  sessionState.confirmed = false;
  sessionState.started = false;
  sessionState.retryCount = 0;

  // Request a session
  socket.emit("session_request", { session_id: socket.id });
  console.log("Sent session_request with ID:", socket.id);
}

function handleSessionConfirm(sessionState) {
  sessionState.confirmed = true;
  console.log("Session confirmed with ID:", window.socket?.id);

  setTimeout(() => {
    sessionState.started = true;
    // Also update the global session state
    if (window.sessionState) {
      window.sessionState.started = true;
    }
    console.log("Session fully initialized, sending initial message...");
    if (!window.sessionInitialized) {
      window.sendIntroduceMessage();
    }
  }, 1000);
}

function handleBotResponse(response, sessionState) {
  console.log("Bot uttered:", response);

  window.lastBotQuickReplies = null;

  // Clear timers
  if (window.currentRetryTimer) {
    clearTimeout(window.currentRetryTimer);
    window.currentRetryTimer = null;
  }

  if (window.introductionWindowTimer) {
    clearTimeout(window.introductionWindowTimer);
    window.introductionWindowTimer = null;
  }

  sessionState.retryCount = 0;
  window.hasReceivedResponse = true;

  // Handle custom events
  if (response.event_type === "grievance_id_set") {
    console.log("Setting grievance ID from event:", response.grievance_id);
    uiActions.setGrievanceId(response.grievance_id);
    return; // Don't display custom events to user
  }

  // Handle task status updates
  if (response.task_status) {
    handleTaskStatusEvent(response.task_status);
    return;
  }

  // Handle the response text
  if (response.text && !response.custom?.hidden) {
    uiActions.appendMessage(response.text, "received");
    window.lastBotMessageText = response.text;
  }

  // Handle quick replies
  if (response.quick_replies) {
    uiActions.appendQuickReplies(response.quick_replies);
    window.lastBotQuickReplies = response.quick_replies;
  }

  if (response.attachment) {
    console.log("Attachment received:", response.attachment);
  }
}

function handleTaskStatusEvent(data) {
  console.log("Received task status update:", data);

  // Handle different task statuses
  const { status, data: taskData, grievance_id, task_name } = data;

  // Update grievance ID if provided
  if (grievance_id) {
    uiActions.setGrievanceId(grievance_id);
  }

  // Create or update task status message
  let statusElement = document.getElementById(`task-status-${task_name}`);
  if (!statusElement) {
    statusElement = document.createElement("div");
    statusElement.id = `task-status-${task_name}`;
    statusElement.className = "task-status";
    document.querySelector(".chat-messages").appendChild(statusElement);
  }

  // Update status message
  let statusMessage = "";
  let statusClass = "";

  switch (status) {
    case "SUCCESS":
      statusMessage = `✅ ${task_name} completed successfully`;
      statusClass = "success";
      if (taskData && taskData.message) {
        uiActions.appendMessage(taskData.message, "received");
      }
      break;

    case "FAILED":
      statusMessage = `❌ ${task_name} failed`;
      statusClass = "error";
      if (taskData && taskData.error) {
        statusMessage += `: ${taskData.error}`;
      }
      break;

    case "IN_PROGRESS":
      statusMessage = `⏳ ${task_name} is processing...`;
      statusClass = "progress";
      if (taskData && taskData.message) {
        statusMessage += ` ${taskData.message}`;
      }
      break;

    default:
      statusMessage = `ℹ️ ${task_name}: ${status}`;
      statusClass = "info";
  }

  statusElement.textContent = statusMessage;
  statusElement.className = `task-status ${statusClass}`;

  // Remove status message after success/failure
  if (status === "SUCCESS" || status === "FAILED") {
    setTimeout(() => {
      if (statusElement.parentNode) {
        statusElement.remove();
      }
    }, 5000);
  }
}

function handleFileStatusUpdate(data) {
  console.log("🎯 handleFileStatusUpdate called with data:", data);

  const { status, data: fileData, task_name, grievance_id } = data;

  // Show status message to user
  let statusMessage = "";

  switch (status) {
    case "SUCCESS":
      if (fileData && fileData.file_name) {
        statusMessage = `✅ File "${fileData.file_name}" processed successfully`;
      } else {
        statusMessage = "✅ File processing completed successfully";
      }
      break;

    case "FAILED":
      statusMessage = "❌ File processing failed";
      break;

    case "IN_PROGRESS":
      statusMessage = "⏳ File is being processed...";
      break;

    default:
      statusMessage = `ℹ️ File status: ${status}`;
  }

  // Show the status message in the chat
  uiActions.appendMessage(statusMessage, "received");

  // Update grievance ID if provided
  if (grievance_id) {
    uiActions.setGrievanceId(grievance_id);
  }
}

// API response handlers
export function handleTaskStatusApiResponse(response) {
  console.log("Task status API response:", response);

  // Handle the HTTP response from /task-status endpoint
  const { status, data, grievance_id, message } = response;

  if (grievance_id) {
    uiActions.setGrievanceId(grievance_id);
  }

  if (message) {
    uiActions.appendMessage(message, "received");
  }

  // Update UI based on status
  switch (status) {
    case "SUCCESS":
      uiActions.appendMessage("Task completed successfully", "received");
      break;
    case "FAILED":
      uiActions.appendMessage("Task failed", "received");
      break;
    case "IN_PROGRESS":
      uiActions.appendMessage("Task is processing...", "received");
      break;
  }
}

export function handleFileUploadApiResponse(response) {
  console.log("File upload API response:", response);

  if (response.ok) {
    const data = response.data;

    // Show initial status
    let statusMessage = "Files uploaded successfully. Processing...";
    if (data.audio_files && data.audio_files.length > 0) {
      statusMessage =
        "Voice recordings uploaded. Processing and transcribing...";
    }
    uiActions.appendMessage(statusMessage, "received");

    // Handle oversized files warning
    if (data.oversized_files && data.oversized_files.length > 0) {
      uiActions.appendMessage(
        `Some files were too large and could not be processed: ${data.oversized_files.join(
          ", "
        )}`,
        "received"
      );
    }
  } else {
    console.error("Upload failed:", response.error);
    uiActions.showError(`Error uploading files: ${response.error}`);
  }
}

export function handleApiError(error, context = "API call") {
  console.error(`${context} error:`, error);
  uiActions.showError(`Error: ${error.message || error}`);
}

// Quick reply handler (called from UI Actions)
export function handleQuickReplyClick(payload) {
  window.safeSendMessage(payload);
}
