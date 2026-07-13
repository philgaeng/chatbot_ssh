"use client";

/**
 * <SetupOverview> — R8 (BUILD-REVIEW M6 / DESIGN §2.3/§7.A): the Setup & go-live landing.
 * Mode 1 (empty system) — the first-run ordered spine (Organisation → Workflows & roles →
 * Project → Officers → Go live). Mode 2 (projects exist) — a per-project go-live spine that
 * always names the next blocker. Composes existing data (listProjects + go-live report); no
 * new backend.
 */
import { useEffect, useState } from "react";

import { listProjects, type ProjectItem } from "@/lib/api";
import { text as textTokens } from "@/lib/design-tokens";
import { ErrorNotice } from "@/components/shared/ErrorNotice";
import { GoLiveSpine } from "./GoLiveSpine";

const FIRST_RUN_STEPS: { title: string; detail: string }[] = [
  { title: "Add your organisation", detail: "Create the reporting-line ministry/department and any partners." },
  { title: "Set up workflows & roles", detail: "Define the escalation levels and who handles / oversees each step." },
  { title: "Create a project", detail: "Set the implementing agency, link workflows, and add locations." },
  { title: "Invite officers", detail: "Staff each level — invite officers by their position." },
  { title: "Go live", detail: "Clear the go-live checklist and activate the project." },
];

export function SetupOverview({
  onOpenProject,
}: {
  onOpenProject?: (projectId: string) => void;
}) {
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [err, setErr] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const list = await listProjects();
        if (alive) setProjects(list);
      } catch (e) {
        if (alive) setErr(e);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="space-y-4">
      <div>
        <h2 className={`text-lg font-semibold ${textTokens.heading}`}>Setup &amp; go-live</h2>
        <p className={`text-sm ${textTokens.secondary} mt-0.5`}>
          The one thing between you and accepting grievances — per project.
        </p>
      </div>

      <ErrorNotice error={err} />

      {loading ? (
        <p className={`text-sm ${textTokens.muted}`}>Loading…</p>
      ) : projects.length === 0 ? (
        // Mode 1 — first-run ordered spine.
        <ol className="space-y-2">
          {FIRST_RUN_STEPS.map((s, i) => (
            <li key={s.title} className="flex items-start gap-3 rounded-lg border border-gray-200 p-3">
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-100 text-xs font-semibold text-blue-700">
                {i + 1}
              </span>
              <div>
                <div className={`text-sm font-medium ${textTokens.heading}`}>{s.title}</div>
                <div className={`text-xs ${textTokens.secondary}`}>{s.detail}</div>
              </div>
            </li>
          ))}
        </ol>
      ) : (
        // Mode 2 — per-project go-live spine.
        <div className="space-y-3">
          {projects.map((p) => (
            <GoLiveSpine key={p.project_id} project={p} onOpenProject={onOpenProject} />
          ))}
        </div>
      )}
    </div>
  );
}
