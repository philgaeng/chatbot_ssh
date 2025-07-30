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

  // Error handling for Rasa socket
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

  // Set up Flask socket event handlers when Flask socket is available
  if (window.flaskSocket) {
    console.log("🔧 Setting up Flask socket event handlers");

    // Set up Flask socket event handlers after connection
    window.flaskSocket.on("connect", () => {
      console.log("🔗 Flask socket connected with ID:", window.flaskSocket.id);
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

    console.log("✅ Flask socket event handlers set up successfully");
  } else {
    console.warn(
      "⚠️ Flask socket not available, file status updates will not be received"
    );
  }
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

    // Check if chat-messages element exists before appending
    const chatMessages = document.querySelector(".chat-messages");
    if (chatMessages) {
      chatMessages.appendChild(statusElement);
    } else {
      console.warn(
        "⚠️ .chat-messages element not found, cannot display task status"
      );
    }
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

      // NEW: Send classification results to Rasa if this is a classification task
      if (task_name === "classify_and_summarize_grievance_task" && taskData) {
        console.log("🎯 Classification completed, sending results to Rasa...");
        console.log("Task data:", taskData);
        sendClassificationResultsToRasa(taskData);
      } else {
        console.log("🔍 Not a classification task or no task data:", {
          task_name,
          taskData,
        });
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

// NEW: Function to send classification results to Rasa
function sendClassificationResultsToRasa(taskData) {
  console.log("🚀 sendClassificationResultsToRasa called with:", taskData);

  try {
    // Prepare the classification data
    const classificationData = {
      grievance_summary: taskData.grievance_summary || "",
      grievance_categories: taskData.grievance_categories || [],
      grievance_description: taskData.grievance_description || "",
      task_name: taskData.task_name || "classify_and_summarize_grievance_task",
      status: taskData.status || "SUCCESS",
    };

    console.log("📋 Prepared classification data:", classificationData);

    // Create the message to send to Rasa (same pattern as /introduce)
    const message = `/classification_results${JSON.stringify(
      classificationData
    )}`;

    console.log("📤 Sending classification results to Rasa:", message);

    // Check if Rasa connection is available
    if (!window.socket || !window.socket.connected) {
      console.error(
        "❌ Rasa socket not connected, cannot send classification results"
      );
      uiActions.appendMessage(
        "⚠️ Unable to send classification results - connection lost. Please refresh the page.",
        "received"
      );
      return false;
    }

    // Check if safeSendMessage function is available
    if (!window.safeSendMessage) {
      console.error("❌ safeSendMessage function not available");
      uiActions.appendMessage(
        "⚠️ System error - unable to send classification results.",
        "received"
      );
      return false;
    }

    // Send to Rasa using the existing safeSendMessage function
    const success = window.safeSendMessage(message);
    if (success) {
      console.log("✅ Classification results sent to Rasa successfully");
      // Show a brief status message to user
      uiActions.appendMessage(
        "🔄 Processing classification results...",
        "received"
      );
      return true;
    } else {
      console.error("❌ Failed to send classification results to Rasa");
      uiActions.appendMessage(
        "⚠️ Failed to send classification results. Please try again.",
        "received"
      );
      return false;
    }
  } catch (error) {
    console.error("❌ Error sending classification results to Rasa:", error);
    uiActions.appendMessage(
      "⚠️ Error processing classification results. Please contact support.",
      "received"
    );
    return false;
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
