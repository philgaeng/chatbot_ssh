"use client";

/**
 * <GoLiveSpine> — R8 (BUILD-REVIEW M6 / DESIGN §7.A): the per-project go-live surface that
 * always names "the one thing blocking go-live". Reads the existing go-live report
 * (no new backend). Shows the single next blocker prominently, then the full checklist with
 * text severity beside colour.
 */
import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, ChevronRight } from "lucide-react";

import { getProjectGoLive, type GoLiveCheck, type GoLiveReport, type ProjectItem } from "@/lib/api";
import { text as textTokens } from "@/lib/design-tokens";
import { ErrorNotice } from "@/components/shared/ErrorNotice";
import { SeverityBadge, type Severity } from "@/components/shared/SeverityBadge";

function severityOf(c: GoLiveCheck): Severity {
  if (c.status === "pass") return "pass";
  if (c.severity === "block") return "block";
  if (c.severity === "warn") return "warn";
  return "info";
}

/** The single next blocker: first block-severity check that failed. */
export function nextBlocker(report: GoLiveReport | null): GoLiveCheck | null {
  if (!report) return null;
  return report.checks.find((c) => c.severity === "block" && c.status === "fail") ?? null;
}

export function GoLiveSpine({
  project,
  onOpenProject,
}: {
  project: ProjectItem;
  onOpenProject?: (projectId: string) => void;
}) {
  const [report, setReport] = useState<GoLiveReport | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setReport(await getProjectGoLive(project.project_id));
      setErr(null);
    } catch (e) {
      setErr(e);
    } finally {
      setLoading(false);
    }
  }, [project.project_id]);

  useEffect(() => {
    void load();
  }, [load]);

  const blocker = nextBlocker(report);
  const ready = report != null && report.can_activate;

  return (
    <div className="rounded-lg border border-gray-200 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className={`font-medium ${textTokens.heading}`}>{project.name}</div>
          <div className={`text-xs ${textTokens.muted} font-mono`}>{project.short_code}</div>
        </div>
        {onOpenProject && (
          <button
            type="button"
            onClick={() => onOpenProject(project.project_id)}
            className="inline-flex items-center gap-0.5 text-xs text-blue-600 hover:underline shrink-0"
          >
            Open project <ChevronRight size={13} />
          </button>
        )}
      </div>

      <ErrorNotice error={err} className="mt-3" />

      {!loading && !err && (
        <div className="mt-3">
          {/* The one thing blocking go-live (DESIGN §7.A thesis). */}
          {ready ? (
            <div className="flex items-center gap-2 text-sm text-green-700">
              <CheckCircle2 size={16} aria-hidden />
              Ready to go live — all blocking checks pass.
            </div>
          ) : blocker ? (
            <div className="flex items-start gap-2 text-sm">
              <SeverityBadge severity="block" label="Next" />
              <span className={textTokens.body}>{blocker.message}</span>
            </div>
          ) : (
            <div className={`text-sm ${textTokens.secondary}`}>Not ready — see the checklist below.</div>
          )}

          {/* Full checklist. */}
          <ul className="mt-3 space-y-1.5">
            {report?.checks.map((c) => (
              <li key={c.id} className="flex items-start gap-2 text-sm">
                <SeverityBadge severity={severityOf(c)} />
                <span className={c.status === "pass" ? textTokens.muted : textTokens.body}>
                  {c.label} — {c.message}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
