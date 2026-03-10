import * as uiActions from "./uiActions.js";
import { get } from "../utterances.js";

// REST-specific helpers for rendering orchestrator responses

export function renderQuickReplies(buttons) {
  if (!Array.isArray(buttons) || buttons.length === 0) {
    return;
  }

  const quickReplies = buttons.map((btn) => ({
    title: btn.title || btn.text || "",
    payload: btn.payload,
  }));

  // Always replace existing quick replies with the latest set so only one
  // step's options are active at a time.
  uiActions.replaceQuickReplies(quickReplies);
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
  // Orchestrator sends json_message with event_type inside data
  if (custom.data?.event_type === "grievance_id_set" && custom.data?.grievance_id) {
    uiActions.setGrievanceId(custom.data.grievance_id);
  }

  // Grievance created in DB: enable file upload button
  if (custom.event_type === "grievance_saved_in_db" && custom.data?.grievance_id) {
    uiActions.setGrievanceId(custom.data.grievance_id);
    uiActions.setGrievanceCreatedInDb(true);
  }
  if (custom.data?.event_type === "grievance_saved_in_db" && custom.data?.grievance_id) {
    uiActions.setGrievanceId(custom.data.grievance_id);
    uiActions.setGrievanceCreatedInDb(true);
  }

  // Modify grievance – Add pictures: set grievance for uploads and open file picker (same as clicking attach button)
  if (custom.event_type === "open_upload_modal" && custom.grievance_id) {
    uiActions.setGrievanceId(custom.grievance_id);
    uiActions.setGrievanceCreatedInDb(true);
    if (typeof window.openFileUploadModal === "function") {
      window.openFileUploadModal();
    }
  }
  if (custom.data?.event_type === "open_upload_modal" && custom.data?.grievance_id) {
    uiActions.setGrievanceId(custom.data.grievance_id);
    uiActions.setGrievanceCreatedInDb(true);
    if (typeof window.openFileUploadModal === "function") {
      window.openFileUploadModal();
    }
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
      uiActions.appendMessage(get("task_status.task_success"), "received");
      break;
    case "FAILED":
      uiActions.appendMessage(get("task_status.task_failed"), "received");
      break;
    case "IN_PROGRESS":
      uiActions.appendMessage(get("task_status.task_in_progress"), "received");
      break;
    default:
      break;
  }
}

export function handleFileUploadApiResponse(response) {
  console.log("File upload API response:", response);

  if (response.ok) {
    const data = response.data;

    let statusMessage = get("file_upload.uploaded_processing");
    if (data.audio_files && data.audio_files.length > 0) {
      statusMessage = get("file_upload.voice_uploaded_processing");
    }
    uiActions.appendMessage(statusMessage, "received");

    if (data.oversized_files && data.oversized_files.length > 0) {
      uiActions.appendMessage(
        `${get("file_upload.oversized_api_prefix")} ${data.oversized_files.join(", ")}`,
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

// Payloads for file-upload flow (handled locally, no orchestrator call)
const ADD_MORE_PAYLOAD = "__add_more_files__";
const GO_BACK_PAYLOAD = "__go_back_to_chat__";

// Quick reply handler (called from UI Actions). Returns true if handled locally (caller should not remove quick replies).
export function handleQuickReplyClick(payload) {
  if (payload === ADD_MORE_PAYLOAD) {
    if (typeof window.handleAddMoreFiles === "function") {
      window.handleAddMoreFiles();
    }
    return true;
  }
  if (payload === GO_BACK_PAYLOAD) {
    if (typeof window.handleGoBackToChat === "function") {
      window.handleGoBackToChat();
    }
    return true;
  }
  window.safeSendMessage(payload);
  return false;
}

