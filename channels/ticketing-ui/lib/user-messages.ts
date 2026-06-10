/**
 * Officer-facing error copy — strips API paths/status and maps known validation cases (TP-13).
 */

export type ActionNoticeKind = "validation" | "failure";

export interface ActionNoticeState {
  message: string;
  kind: ActionNoticeKind;
}

export const MSG_IMAGE_BEFORE_ESCALATE =
  "Add at least one photo before escalating. Upload a site photo or ask the complainant to send photos via WhatsApp.";

export const MSG_IMAGE_BEFORE_RESOLVE =
  "Add at least one photo before resolving. Upload a site photo or ask the complainant to send photos via WhatsApp.";

export const MSG_SUPERVISOR_ONLY_ASSIGN =
  "Only a supervisor can assign tickets. Use #reassign if this case is out of scope.";

export const MSG_SUPERVISOR_ONLY_FIELD_REPORT =
  "Only a supervisor can assign field reports.";

const GENERIC_FAILURE = "Something went wrong. Please try again.";

/** Strip `API 422 /path:` prefix and parse FastAPI JSON `detail`. */
export function parseApiErrorDetail(raw: string): string | null {
  const withoutPrefix = raw.replace(/^API \d+ \S+: /, "").trim();
  if (!withoutPrefix) return null;

  if (withoutPrefix.startsWith("{")) {
    try {
      const parsed = JSON.parse(withoutPrefix) as { detail?: unknown };
      const d = parsed.detail;
      if (typeof d === "string") return d;
      if (Array.isArray(d)) {
        const parts = d
          .map((item) => {
            if (typeof item === "string") return item;
            if (item && typeof item === "object" && "msg" in item) {
              return String((item as { msg?: string }).msg ?? "");
            }
            return "";
          })
          .filter(Boolean);
        if (parts.length) return parts.join(" ");
      }
    } catch {
      /* not JSON */
    }
  }

  if (withoutPrefix.includes("/api/") || withoutPrefix.startsWith("API ")) {
    return null;
  }
  return withoutPrefix.slice(0, 500);
}

function mapDetailToNotice(detail: string): ActionNoticeState | null {
  const d = detail.trim();
  if (!d) return null;

  if (d.includes("At least one image attachment is required before escalating")) {
    return { message: MSG_IMAGE_BEFORE_ESCALATE, kind: "validation" };
  }
  if (d.includes("At least one image attachment is required before resolving")) {
    return { message: MSG_IMAGE_BEFORE_RESOLVE, kind: "validation" };
  }
  if (d.includes("escalation_notes is required")) {
    return {
      message: "Add escalation notes explaining why this case should move to the next level.",
      kind: "validation",
    };
  }
  if (d.includes("Cannot perform") && d.includes("ESCALATED") && d.includes("Acknowledge")) {
    return {
      message: "Acknowledge the ticket first to take ownership at this level.",
      kind: "validation",
    };
  }
  if (d.includes("No next step available") || d.includes("final escalation level")) {
    return {
      message: "This case is already at the highest escalation level.",
      kind: "validation",
    };
  }
  if (d.includes("reassignment_notes required when reason is OTHER")) {
    return {
      message: 'Add a short explanation when you choose "Other" as the reassignment reason.',
      kind: "validation",
    };
  }
  if (d.includes("reassignment_reason_code must be")) {
    return { message: "Choose a reassignment reason before submitting.", kind: "validation" };
  }
  if (d.includes("No supervisor configured")) {
    return {
      message: "No supervisor is set up for this step. Contact your admin.",
      kind: "failure",
    };
  }
  if (
    d.includes("Only a supervisor") ||
    (d.toLowerCase().includes("supervisor") && d.toLowerCase().includes("assign"))
  ) {
    return { message: MSG_SUPERVISOR_ONLY_ASSIGN, kind: "validation" };
  }
  if (d.includes("Ticket is already resolved")) {
    return { message: "This case is already resolved.", kind: "validation" };
  }
  if (d.includes("note is required")) {
    return { message: "Add a note before saving.", kind: "validation" };
  }
  if (d.includes("Only the assigned officer")) {
    return {
      message:
        "Only the officer assigned to this inspection can complete it. " +
        "If this is your task, ask an admin to reassign it to your login email.",
      kind: "validation",
    };
  }
  if (d.includes("/complete") && d.includes("403")) {
    return {
      message:
        "Permission denied when completing the inspection task. " +
        "Refresh the page — if the report already appears on the timeline, the visit may be saved.",
      kind: "failure",
    };
  }

  if (d.length > 0 && !d.includes("/api/v1/") && !d.startsWith("API ")) {
    return { message: d, kind: "validation" };
  }
  return null;
}

export type FormatErrorContext = "field_report" | "upload" | "task";

export function formatUserFacingError(
  e: unknown,
  context?: FormatErrorContext,
): ActionNoticeState {
  const raw = e instanceof Error ? e.message : String(e);

  if (raw === MSG_IMAGE_BEFORE_ESCALATE) {
    return { message: MSG_IMAGE_BEFORE_ESCALATE, kind: "validation" };
  }
  if (raw === MSG_IMAGE_BEFORE_RESOLVE) {
    return { message: MSG_IMAGE_BEFORE_RESOLVE, kind: "validation" };
  }
  if (raw === MSG_SUPERVISOR_ONLY_ASSIGN || raw === MSG_SUPERVISOR_ONLY_FIELD_REPORT) {
    return { message: raw, kind: "validation" };
  }

  const detail = parseApiErrorDetail(raw);
  const mapped = detail ? mapDetailToNotice(detail) : mapDetailToNotice(raw);

  if (mapped) {
    if (context === "field_report" && mapped.kind === "failure") {
      return {
        message: "Could not save the field visit report. Please try again.",
        kind: "failure",
      };
    }
    if (context === "field_report") {
      return {
        message: `Could not save the field visit report.\n\n${mapped.message}`,
        kind: mapped.kind,
      };
    }
    if (context === "upload") {
      return {
        message:
          mapped.kind === "validation"
            ? mapped.message
            : "Could not upload the file. Please try again.",
        kind: mapped.kind === "validation" ? "validation" : "failure",
      };
    }
    if (context === "task") {
      return {
        message:
          mapped.kind === "validation"
            ? mapped.message
            : "Could not complete the task. Please try again.",
        kind: mapped.kind === "validation" ? "validation" : "failure",
      };
    }
    return mapped;
  }

  if (context === "field_report") {
    return {
      message: "Could not save the field visit report. Please try again.",
      kind: "failure",
    };
  }
  if (context === "upload") {
    return { message: "Could not upload the file. Please try again.", kind: "failure" };
  }
  if (context === "task") {
    return { message: "Could not complete the task. Please try again.", kind: "failure" };
  }

  return { message: GENERIC_FAILURE, kind: "failure" };
}
