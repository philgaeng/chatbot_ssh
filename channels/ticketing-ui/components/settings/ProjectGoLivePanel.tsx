"use client";

import { useCallback, useEffect, useState } from "react";
import { getProjectGoLive, type GoLiveReport } from "@/lib/api";

const GROUP_LABELS: Record<string, string> = {
  routing: "Routing",
  commercial: "Commercial",
  officers: "Officers",
  geography: "Geography",
  metadata: "Metadata",
};

function statusDot(status: string) {
  if (status === "pass") return "bg-green-500";
  if (status === "fail") return "bg-red-500";
  if (status === "warn") return "bg-amber-400";
  return "bg-gray-300";
}

export function ProjectGoLivePanel({
  projectId,
  onJumpSection,
}: {
  projectId: string;
  onJumpSection?: (section: string) => void;
}) {
  const [report, setReport] = useState<GoLiveReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const r = await getProjectGoLive(projectId);
      setReport(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load go-live status");
      setReport(null);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <div className="mb-6 rounded-lg border border-gray-200 bg-slate-50/80 px-4 py-3 text-sm text-gray-500 animate-pulse">
        Checking go-live readiness…
      </div>
    );
  }

  if (error) {
    return (
      <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (!report) return null;

  const groups = [...new Set(report.checks.map((c) => c.group))];

  return (
    <div className="mb-6 rounded-lg border border-gray-200 bg-white overflow-hidden max-w-3xl">
      <div className="px-4 py-3 border-b border-gray-100 flex flex-wrap items-center justify-between gap-2 bg-slate-50/60">
        <div>
          <h3 className="text-sm font-semibold text-gray-800">Go-live status</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            {report.summary.pass} passed · {report.summary.warn} warnings
            {report.summary.fail > 0 ? ` · ${report.summary.fail} blocking` : ""}
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className={report.can_activate ? "text-green-700 font-medium" : "text-red-700 font-medium"}>
            {report.can_activate ? "Can activate" : "Cannot activate yet"}
          </span>
          <span className={report.can_accept_tickets ? "text-green-700 font-medium" : "text-red-700 font-medium"}>
            {report.can_accept_tickets ? "Tickets OK" : "Tickets blocked"}
          </span>
          <button type="button" onClick={() => void load()} className="text-blue-600 hover:underline">
            Refresh
          </button>
        </div>
      </div>

      <div className="divide-y divide-gray-100">
        {groups.map((group) => (
          <div key={group} className="px-4 py-2.5">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
              {GROUP_LABELS[group] ?? group}
            </p>
            <ul className="space-y-1.5">
              {report.checks
                .filter((c) => c.group === group)
                .map((c) => (
                  <li key={c.id} className="flex items-start gap-2 text-sm">
                    <span className={`mt-1.5 h-2 w-2 rounded-full shrink-0 ${statusDot(c.status)}`} />
                    <span className="flex-1 text-gray-700">
                      <span className="font-medium">{c.label}</span>
                      <span className="text-gray-500"> — {c.message}</span>
                    </span>
                    {c.section && onJumpSection && (
                      <button
                        type="button"
                        onClick={() => onJumpSection(c.section!)}
                        className="text-xs text-blue-600 hover:underline shrink-0"
                      >
                        Fix
                      </button>
                    )}
                  </li>
                ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
