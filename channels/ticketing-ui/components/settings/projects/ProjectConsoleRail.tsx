"use client";

/**
 * <ProjectConsoleRail> — the sticky left rail of the project console (ui/04).
 *
 * Go-live status and section navigation are ONE control, not two: the dot beside each
 * section is that section's readiness, so "what's left to do" and "where do I go" are the
 * same glance. Severity is carried in words as well as colour (ui/05 §2 rule 6) — the FIX
 * flag and the hint line, not the red dot alone.
 */
import type { GoLiveReport } from "@/lib/api";
import {
  PROJECT_SECTIONS,
  SECTION_GROUPS,
  blockerCount,
  passingCount,
  sectionHints,
  sectionStatuses,
  type SectionKey,
} from "./projectSections";

const DOT: Record<string, string> = {
  block: "bg-red-500",
  warn: "bg-amber-400",
  pass: "bg-green-500",
  none: "bg-gray-300",
};

export function ProjectConsoleRail({
  report,
  active,
  onSelect,
  loading,
}: {
  report: GoLiveReport | null;
  active: SectionKey;
  onSelect: (key: SectionKey) => void;
  loading?: boolean;
}) {
  const statuses = sectionStatuses(report);
  const hints = sectionHints(report);
  const blockers = blockerCount(report);
  const { passed, total } = passingCount(report);
  const pct = total ? Math.round((passed / total) * 100) : 0;

  return (
    <nav
      aria-label="Project setup sections"
      className="w-[248px] shrink-0 self-start sticky top-4 rounded-lg border border-gray-200 bg-white overflow-hidden"
    >
      <div className="px-4 py-3 border-b border-gray-100">
        <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400">Setup progress</div>
        {loading ? (
          <div className="mt-2 text-sm text-gray-400 animate-pulse">Checking…</div>
        ) : (
          <>
            <div className="mt-1 flex items-baseline gap-2">
              <span className={`text-2xl font-bold ${blockers ? "text-red-600" : "text-green-600"}`}>
                {blockers || "0"}
              </span>
              <span className="text-xs text-gray-600">
                {blockers === 1 ? "blocker before go-live" : "blockers before go-live"}
              </span>
            </div>
            <div className="mt-2.5 h-1.5 rounded-full bg-gray-100 overflow-hidden">
              <div className="h-full rounded-full bg-green-500" style={{ width: `${pct}%` }} />
            </div>
            <div className="mt-2 text-[11px] font-mono text-gray-400">
              {passed} of {total} checks passing
            </div>
          </>
        )}
      </div>

      {SECTION_GROUPS.map((group) => (
        <div key={group} className="px-2 py-2">
          <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-gray-400">{group}</div>
          {PROJECT_SECTIONS.filter((s) => s.group === group).map((s) => {
            const st = statuses[s.key];
            const isActive = active === s.key;
            const hint = hints[s.key] ?? s.restingHint ?? "";
            return (
              <button
                key={s.key}
                type="button"
                onClick={() => onSelect(s.key)}
                aria-current={isActive ? "page" : undefined}
                className={`w-full flex items-center gap-2.5 px-2 py-2 rounded text-left transition ${
                  isActive ? "bg-blue-50" : "hover:bg-gray-50"
                }`}
              >
                <span className={`h-2 w-2 rounded-full shrink-0 ${DOT[st]}`} />
                <span className="flex-1 min-w-0">
                  <span className={`block text-[13px] leading-tight ${isActive ? "text-blue-700 font-semibold" : "text-gray-700"}`}>
                    {s.label}
                  </span>
                  {hint && (
                    <span className="block text-[11px] text-gray-400 truncate leading-tight" title={hint}>
                      {hint}
                    </span>
                  )}
                </span>
                {st === "block" && (
                  <span className="text-[10px] font-bold text-red-600 shrink-0">FIX</span>
                )}
              </button>
            );
          })}
        </div>
      ))}

      <div className="border-t border-gray-100 px-4 py-2.5 text-[11px] text-gray-400 leading-snug">
        Each dot is a section&apos;s status: <span className="text-green-600 font-bold">●</span> ready ·{" "}
        <span className="text-red-500 font-bold">●</span> blocks go-live ·{" "}
        <span className="text-amber-400 font-bold">●</span> to review.
      </div>
    </nav>
  );
}
