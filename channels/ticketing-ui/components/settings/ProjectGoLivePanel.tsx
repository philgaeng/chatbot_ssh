"use client";

/**
 * <ProjectGoLivePanel> — the console's "Overview & go-live" pane (ui/04).
 *
 * The report is owned by <ProjectEditor> because the rail needs it too — one fetch, two
 * consumers, so the dots and the checklist can never disagree.
 *
 * **The checks are listed in the rail's own order** (2026-08-07, Philippe). A check's `section`
 * is the pane that fixes it, so reading down this list is reading down the rail, and a red dot
 * beside "Staffing" has its checks where the eye already is. This pane used to group by a
 * *second* taxonomy — "Routing / Organizations & lots / Officers / Geography / Project details" —
 * which answered a different question than the nav and put "Package locations" under a heading
 * three away from Packages. Two orders on one screen, and neither of them the one you navigate
 * by. The headings went with it: with the order right they only named what the rail already says.
 *
 * A blocked check carries the words "Blocks go-live" as well as the red mark (ui/05 §2 rule 6).
 */
import type { GoLiveCheck, GoLiveReport } from "@/lib/api";
import { SECTION_ORDER, sectionOfCheck } from "@/components/settings/projects/projectSections";

/** Rail position of the pane that fixes this check; unplaceable checks sink to the bottom. */
function railRank(c: GoLiveCheck): number {
  const section = sectionOfCheck(c);
  const i = section ? SECTION_ORDER.indexOf(section) : -1;
  return i < 0 ? SECTION_ORDER.length : i;
}

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

  const blockers = report.checks.filter((c) => c.severity === "block" && c.status === "fail");
  // Stable sort: checks that fix in the same pane keep the order the service reports them in.
  const ordered = [...report.checks].sort((a, b) => railRank(a) - railRank(b));

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

      <ul className="space-y-1.5">
        {ordered.map((c) => {
          const blocked = c.severity === "block" && c.status === "fail";
          const ok = c.status === "pass";
          const target = sectionOfCheck(c);
          return (
            <li
              key={c.id}
              className={`flex items-start gap-3 rounded-md border px-3 py-2.5 ${
                blocked ? "border-red-200 bg-red-50" : "border-gray-200 bg-white"
              }`}
            >
              <span
                className={`mt-0.5 grid h-[18px] w-[18px] shrink-0 place-items-center rounded-full text-[11px] font-bold ${
                  ok
                    ? "bg-green-600 text-white"
                    : blocked
                      ? "bg-red-600 text-white"
                      : "border border-gray-300 bg-white text-gray-400"
                }`}
                aria-hidden
              >
                {ok ? "✓" : blocked ? "✕" : "○"}
              </span>
              <span className="flex-1 min-w-0">
                <span className="block text-[13.5px] font-semibold text-gray-900">
                  {c.label}
                  {blocked && (
                    <span className="ml-2 text-[11px] font-bold text-red-600 uppercase tracking-wide">
                      Blocks go-live
                    </span>
                  )}
                  {!blocked && !ok && (
                    <span className="ml-2 text-[11px] font-normal text-gray-400">— optional</span>
                  )}
                </span>
                <span className="block text-xs text-gray-600">{c.message}</span>
              </span>
              {target && onJumpSection && !ok && (
                <button
                  type="button"
                  onClick={() => onJumpSection(target)}
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
  );
}
