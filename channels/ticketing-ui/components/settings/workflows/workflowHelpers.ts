/**
 * workflowHelpers.ts — shared leaf helpers for the workflows cluster.
 *
 * Badge helpers return Tailwind class strings (not JSX). `workflowTrackOf` and the
 * binding-draft helpers are the seam the Projects cluster's workflow bindings ride on.
 * The NOTIF_* / *_EVENTS consts drive the notifications panel (Spec 12 §4).
 *
 * Extracted verbatim from `app/settings/page.tsx` (T3-05) — no behaviour change.
 */
import { type WorkflowDefinition, type ProjectWorkflowSlot } from "@/lib/api";

export type WorkflowRoleOption = { key: string; label: string; origin?: string };

export function statusBadge(status: string) {
  const map: Record<string, string> = {
    published: "bg-green-100 text-green-700",
    draft:     "bg-amber-100 text-amber-700",
    archived:  "bg-gray-100 text-gray-500",
    template:  "bg-blue-100 text-blue-700",
  };
  return map[status] ?? "bg-gray-100 text-gray-600";
}

export function typeBadge(t: string) {
  return t === "seah" ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-600";
}

export type WorkflowBindingDraft = {
  localId: string;
  display_label: string;
  workflow_id: string;
  classifications: string[];
  intake_route: string | null;
  is_default: boolean;
  sort_order: number;
};

export function emptyBinding(sortOrder: number, isDefault = false): WorkflowBindingDraft {
  return {
    localId: `new-${Date.now()}-${sortOrder}`,
    display_label: "",
    workflow_id: "",
    classifications: [],
    intake_route: isDefault ? null : "new_grievance",
    is_default: isDefault,
    sort_order: sortOrder,
  };
}

export function workflowTrackOf(w: WorkflowDefinition): "standard" | "seah" {
  return (w.workflow_type || "standard").toLowerCase() === "seah" ? "seah" : "standard";
}

export function bindingsFromProject(slots: ProjectWorkflowSlot[]): WorkflowBindingDraft[] {
  if (!slots.length) return [emptyBinding(10, true)];
  return slots.map((s, i) => ({
    localId: s.project_workflow_id,
    display_label: s.display_label,
    workflow_id: s.workflow_id,
    classifications: s.classifications ?? [],
    intake_route: s.intake_route ?? null,
    is_default: s.is_default,
    sort_order: s.sort_order || (i + 1) * 10,
  }));
}

export function publishedWorkflowOptions(
  workflows: WorkflowDefinition[],
  canEditWorkflowTrack: (track: "standard" | "seah") => boolean,
  selectedId?: string,
): WorkflowDefinition[] {
  const published = workflows.filter(
    (w) =>
      !w.is_template
      && (w.status || "").toLowerCase() === "published"
      && canEditWorkflowTrack(workflowTrackOf(w)),
  );
  if (selectedId && !published.some((w) => w.workflow_id === selectedId)) {
    const current = workflows.find((w) => w.workflow_id === selectedId);
    if (current) return [current, ...published];
  }
  return published;
}

export const NOTIFICATION_EVENTS: { key: string; label: string }[] = [
  { key: "ticket_created",   label: "Ticket created"     },
  { key: "ticket_escalated", label: "Ticket escalated"   },
  { key: "ticket_resolved",  label: "Ticket resolved"    },
  { key: "sla_breach",       label: "SLA breach"         },
  { key: "grc_convened",     label: "GRC convened"       },
  { key: "assignment",       label: "Assignment"         },
  { key: "quarterly_report", label: "Quarterly report"   },
];
export const SEAH_EVENTS = new Set(["ticket_created","ticket_escalated","ticket_resolved","sla_breach","assignment"]);
export const NOTIF_TIERS = ["actor","supervisor","informed","observer"] as const;
export const NOTIF_CHANNELS = ["app","email","sms"] as const;
