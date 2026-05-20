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
