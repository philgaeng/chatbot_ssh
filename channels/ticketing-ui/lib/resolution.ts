import type { TicketEvent } from "@/lib/api";

export const RESOLUTION_CATEGORIES = [
  { code: "CLASSIFIED", label: "Grievance classified", defaultWording: "This grievance has been reviewed and classified. No specific remedial action is required beyond continued monitoring under the project GRM procedure." },
  { code: "DEMAND_REJECTED", label: "Complainant demand rejected", defaultWording: "After investigation, the grievance was found not to be substantiated. The complainant's request is not accepted. The case is closed with this determination." },
  { code: "ACCEPTED_MONETARY", label: "Grievance accepted — monetary compensation", defaultWording: "The grievance is substantiated. Remedial action includes monetary compensation as agreed with the complainant / per contract and GRM procedure." },
  { code: "ACCEPTED_RELOCATION", label: "Grievance accepted — relocation", defaultWording: "The grievance is substantiated. Remedial action includes relocation / resettlement support as applicable under project safeguards." },
  { code: "ACCEPTED_OTHER", label: "Grievance accepted — other remedy", defaultWording: "The grievance is substantiated. Remedial action has been agreed (other than monetary compensation or relocation). Details are recorded below." },
] as const;

export type ResolutionCategoryCode = (typeof RESOLUTION_CATEGORIES)[number]["code"];

export function resolutionCategoryLabel(code: string): string {
  return RESOLUTION_CATEGORIES.find((c) => c.code === code)?.label ?? code;
}

export function isResolutionRecordEvent(event: {
  event_type: string;
  payload?: Record<string, unknown> | null;
}): boolean {
  return (
    event.event_type === "NOTE_ADDED" &&
    !!(event.payload as Record<string, unknown> | null)?.is_resolution_record
  );
}

export const RESOLUTION_MIN_NOTE_LEN = 12;
