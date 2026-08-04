"use client";

/**
 * <ProjectGoLivePanel> — the console's "Overview & go-live" pane (ui/04).
 *
 * The report is owned by <ProjectEditor> because the rail needs it too — one fetch, two
 * consumers, so the dots and the checklist can never disagree. Checks are grouped, and a
 * blocked one carries the words "Blocks go-live" as well as the red mark (ui/05 §2 rule 6).
 */
import type { GoLiveReport } from "@/lib/api";

const GROUP_LABELS: Record<string, string> = {
  routing: "Routing",
  commercial: "Organizations & lots",
  officers: "Officers",
  geography: "Geography",
  metadata: "Project details",
};

export function ProjectGoLivePanel({
  report,
  loading,
  error,
  onRefresh,
  onJumpSection,
}: {
  report: GoLiveReport | null;
  loading: boolean;
  error: string;
  onRefresh: () => void;
  onJumpSection?: (section: string) => void;
}) {
  if (loading) {
    return (
      <div className="rounded-lg border border-gray-200 bg-slate-50/80 px-4 py-3 text-sm text-gray-500 animate-pulse">
        Checking go-live readiness…
      </div>
    );
  }
  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
    );
  }
  if (!report) return null;

  const groups = [...new Set(report.checks.map((c) => c.group))];
  const blockers = report.checks.filter((c) => c.severity === "block" && c.status === "fail");

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <p className="text-sm text-gray-600 max-w-xl">
          {blockers.length === 0
            ? "Everything needed to accept grievances is in place."
            : blockers.length === 1
              ? "One check must pass before this project can accept grievances."
              : `${blockers.length} checks must pass before this project can accept grievances.`}
        </p>
        <button type="button" onClick={onRefresh} className="text-xs text-blue-600 hover:underline shrink-0">
          Check again
        </button>
      </div>

      <div className="space-y-5">
        {groups.map((group) => (
          <div key={group}>
            <p className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-2">
              {GROUP_LABELS[group] ?? group}
            </p>
            <ul className="space-y-1.5">
              {report.checks
                .filter((c) => c.group === group)
                .map((c) => {
                  const blocked = c.severity === "block" && c.status === "fail";
                  const ok = c.status === "pass";
                  return (
                    <li
                      key={c.id}
                      className={`flex items-start gap-3 rounded-md border px-3 py-2.5 ${
                        blocked ? "border-red-200 bg-red-50" : "border-gray-200 bg-white"
                      }`}
                    >
                      <span
                        className={`mt-0.5 grid h-[18px] w-[18px] shrink-0 place-items-center rounded-full text-[11px] font-bold text-white ${
                          ok ? "bg-green-600" : blocked ? "bg-red-600" : "bg-amber-400"
                        }`}
                        aria-hidden
                      >
                        {ok ? "✓" : blocked ? "✕" : "!"}
                      </span>
                      <span className="flex-1 min-w-0">
                        <span className="block text-[13.5px] font-semibold text-gray-900">
                          {c.label}
                          {blocked && (
                            <span className="ml-2 text-[11px] font-bold text-red-600 uppercase tracking-wide">
                              Blocks go-live
                            </span>
                          )}
                        </span>
                        <span className="block text-xs text-gray-600">{c.message}</span>
                      </span>
                      {c.section && onJumpSection && !ok && (
                        <button
                          type="button"
                          onClick={() => onJumpSection(c.section!)}
                          className="text-xs font-semibold text-blue-600 hover:underline shrink-0 px-1"
                        >
                          Fix →
                        </button>
                      )}
                    </li>
                  );
                })}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
