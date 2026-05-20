/** Structured field visit / inspection report note formatting. */

export interface FieldVisitFormData {
  visitDate: string;
  location: string;
  personMet: string;
  notes: string;
}

export function todayIsoDate(): string {
  return new Date().toISOString().slice(0, 10);
}

export function formatFieldVisitNote(data: FieldVisitFormData): string {
  const lines = [
    `Field visit — ${data.visitDate}`,
    `Location: ${data.location.trim() || "—"}`,
    `Person met: ${data.personMet.trim() || "—"}`,
  ];
  const notes = data.notes.trim();
  if (notes) {
    lines.push("", "Notes:", notes);
  }
  return lines.join("\n");
}

export function isSiteVisitTask(taskType: string): boolean {
  return taskType === "SITE_VISIT";
}

export function isFieldReportEvent(event: {
  event_type: string;
  payload?: Record<string, unknown> | null;
}): boolean {
  return (
    event.event_type === "NOTE_ADDED" &&
    (event.payload as Record<string, unknown> | null)?.is_field_report === true
  );
}

/** User-facing message when field visit save fails (includes API detail when present). */
export function fieldVisitSaveErrorMessage(e: unknown): string {
  const raw = e instanceof Error ? e.message : String(e);
  if (raw.includes("Only the assigned officer")) {
    return (
      "Only the officer assigned to this inspection can complete it. " +
      "If this is your task, ask an admin to reassign it to your login email."
    );
  }
  if (raw.includes("/complete") && raw.includes("403")) {
    return (
      "Permission denied when completing the inspection task. " +
      "Refresh the page — if the report already appears on the timeline, the visit may be saved."
    );
  }
  const detail = raw.replace(/^API \d+ \S+: /, "").trim();
  return detail
    ? `Could not save the field visit report.\n\n${detail.slice(0, 320)}`
    : "Could not save the field visit report. Please try again.";
}
