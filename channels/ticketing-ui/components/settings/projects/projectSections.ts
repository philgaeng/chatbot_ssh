/**
 * projectSections.ts — the project editor's section model (doc 13 §5, ui/04).
 *
 * One list drives the rail, the router and the "Save & next" order, so a section can never
 * appear in the nav and not in the console (or vice versa). Section keys match the `section`
 * field the go-live service stamps on each check (`project_go_live.py`), which is how a check
 * knows which pane fixes it.
 */
import type { GoLiveCheck, GoLiveReport } from "@/lib/api";

export type SectionKey =
  | "overview"
  | "identity"
  | "workflows"
  | "messaging"
  | "actors"
  | "staffing"
  | "locations"
  | "packages";

export type SectionGroup = "Setup" | "Routing" | "People" | "Geography";

export const PROJECT_SECTIONS: {
  key: SectionKey;
  label: string;
  group: SectionGroup;
  /** Shown in the rail under the label when the section has nothing to fix. */
  restingHint?: string;
}[] = [
  { key: "overview",  label: "Overview & go-live",  group: "Setup" },
  { key: "identity",  label: "Identity",            group: "Setup",     restingHint: "Name & code set" },
  { key: "workflows", label: "Grievance workflows", group: "Routing" },
  { key: "messaging", label: "Officer messaging",   group: "Routing",   restingHint: "Optional" },
  { key: "actors",    label: "Partner organizations", group: "People" },
  { key: "staffing",  label: "Project-wide staffing", group: "People" },
  { key: "locations", label: "Locations",           group: "Geography" },
  { key: "packages",  label: "Packages (lots)",     group: "Geography" },
];

export const SECTION_ORDER: SectionKey[] = PROJECT_SECTIONS.map((s) => s.key);

export const SECTION_GROUPS: SectionGroup[] = ["Setup", "Routing", "People", "Geography"];

/** Checks E1 (name + short code) carry no section — they belong to Identity. */
const CHECK_ID_SECTION: Record<string, SectionKey> = { E1: "identity" };

export function sectionOfCheck(check: GoLiveCheck): SectionKey | null {
  if (CHECK_ID_SECTION[check.id]) return CHECK_ID_SECTION[check.id];
  const s = check.section as SectionKey | null;
  return s && SECTION_ORDER.includes(s) ? s : null;
}

export type SectionStatus = "block" | "warn" | "pass" | "none";

/** Worst status among a section's checks — a red dot beats amber beats green. */
export function sectionStatuses(report: GoLiveReport | null): Record<SectionKey, SectionStatus> {
  const out = Object.fromEntries(SECTION_ORDER.map((k) => [k, "none"])) as Record<SectionKey, SectionStatus>;
  if (!report) return out;
  for (const c of report.checks) {
    const key = sectionOfCheck(c);
    if (!key) continue;
    // Binary (Q-GL-1/2): a check either blocks go-live or it is optional. An optional check
    // that hasn't passed is NOT a problem — it must not read as one, or people learn to
    // ignore amber and miss the real blocker.
    const rank = (s: SectionStatus) => ({ none: 0, pass: 1, warn: 2, block: 3 }[s]);
    const asStatus: SectionStatus =
      c.severity === "block" && c.status === "fail" ? "block"
      : c.status === "pass" ? "pass"
      : "none";
    if (rank(asStatus) > rank(out[key])) out[key] = asStatus;
  }
  return out;
}

/** The first unresolved thing in each section — the rail's one-line "what's wrong". */
export function sectionHints(report: GoLiveReport | null): Partial<Record<SectionKey, string>> {
  const out: Partial<Record<SectionKey, string>> = {};
  if (!report) return out;
  for (const c of report.checks) {
    const key = sectionOfCheck(c);
    if (!key || out[key]) continue;
    if (c.severity === "block" && c.status === "fail") out[key] = c.message;
  }
  return out;
}

export function blockerCount(report: GoLiveReport | null): number {
  if (!report) return 0;
  return report.checks.filter((c) => c.severity === "block" && c.status === "fail").length;
}

export function passingCount(report: GoLiveReport | null): { passed: number; total: number } {
  if (!report) return { passed: 0, total: 0 };
  return {
    passed: report.checks.filter((c) => c.status === "pass").length,
    total: report.checks.length,
  };
}
