import * as uiActions from "./uiActions.js";

// REST-specific helpers for rendering orchestrator responses

export function renderQuickReplies(buttons) {
  if (!Array.isArray(buttons) || buttons.length === 0) {
    return;
  }

  const quickReplies = buttons.map((btn) => ({
    title: btn.title || btn.text || "",
    payload: btn.payload,
  }));

  uiActions.appendQuickReplies(quickReplies);
}

export function handleCustomPayload(custom) {
  if (!custom) {
    return;
  }

  if (custom.grievance_id) {
    uiActions.setGrievanceId(custom.grievance_id);
  }

  if (custom.text) {
    uiActions.appendMessage(custom.text, "received");
  }

  if (custom.event_type === "grievance_id_set" && custom.data?.grievance_id) {
    uiActions.setGrievanceId(custom.data.grievance_id);
  }
}

// Task status updates from HTTP APIs (if used)

export function handleTaskStatusApiResponse(response) {
  console.log("Task status API response:", response);

  const { status, grievance_id, message } = response;

  if (grievance_id) {
    uiActions.setGrievanceId(grievance_id);
  }

  if (message) {
    uiActions.appendMessage(message, "received");
  }

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
    default:
      break;
  }
}

export function handleFileUploadApiResponse(response) {
  console.log("File upload API response:", response);

  if (response.ok) {
    const data = response.data;

    let statusMessage = "Files uploaded successfully. Processing...";
    if (data.audio_files && data.audio_files.length > 0) {
      statusMessage =
        "Voice recordings uploaded. Processing and transcribing...";
    }
    uiActions.appendMessage(statusMessage, "received");

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

