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

/**
 * Setup order (Philippe, 2026-08-04) — the order the work is actually done in:
 * decide what the project is, where it works, which lots it has, **then** who is involved.
 * You cannot name the contractor of a lot before the lot exists, and organizations are set up
 * once while officers change often, so they are the last two and they are separate.
 *
 * Group headings were dropped in the same pass: with eight sections in the right order the
 * headings only added noise, and "Geography" was a poor fit for a contract lot anyway.
 */
export const PROJECT_SECTIONS: {
  key: SectionKey;
  label: string;
  /** Shown in the rail under the label when the section has nothing to fix. */
  restingHint?: string;
}[] = [
  { key: "overview",  label: "Overview & go-live" },
  { key: "identity",  label: "Identity",              restingHint: "Name & code set" },
  { key: "workflows", label: "Grievance workflows" },
  { key: "messaging", label: "Officer messaging",     restingHint: "Optional" },
  { key: "locations", label: "Locations" },
  { key: "packages",  label: "Packages (lots)" },
  { key: "actors",    label: "Partner organizations" },
  { key: "staffing",  label: "Staffing" },
];

export const SECTION_ORDER: SectionKey[] = PROJECT_SECTIONS.map((s) => s.key);

/**
 * The pane that fixes a check. Every check the service reports names its own section — E1
 * (name + short code) was the last one patched here on the client, and is stamped `identity`
 * server-side since 2026-08-07. One taxonomy, one place: the rail, the go-live list and the
 * "Fix →" jumps all read this, so they cannot drift apart.
 */
export function sectionOfCheck(check: GoLiveCheck): SectionKey | null {
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
