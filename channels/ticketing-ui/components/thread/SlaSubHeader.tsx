"use client";

import { urgencyDotCls, urgencyTextCls, stepShortLabel, type SlaUrgency } from "@/lib/mobile-constants";
import { UrgencyDot } from "@/lib/icons";
import type { TicketDetail, SlaStatus, WorkflowStepBrief } from "@/lib/api";

// ── SLA strip ─────────────────────────────────────────────────────────────────

export function SlaSubHeader({ ticket, sla }: { ticket: TicketDetail; sla: SlaStatus | null }) {
  const urgency: SlaUrgency = ticket.sla_breached ? "overdue" : (sla?.urgency ?? "none");
  const cls = urgencyTextCls(urgency);

  let timeText = "Active";
  if (ticket.sla_breached) timeText = "Overdue";
  else if (sla?.remaining_hours) {
    const h = sla.remaining_hours;
    timeText = h < 24 ? `${Math.round(h)}h left` : `${Math.round(h / 24)}d left`;
  }

  const step = ticket.current_step?.display_name ?? ticket.status_code;
  const loc = ticket.location_code ?? "";

  return (
    <div className={`flex items-center gap-1.5 px-4 py-1.5 bg-gray-50 border-b border-gray-200 text-xs ${cls}`}>
      <UrgencyDot urgency={urgency} />
      <span className="font-medium">{step}</span>
      {loc && <><span className="text-gray-300">·</span><span className="text-gray-500">{loc}</span></>}
      <span className="text-gray-300">·</span>
      <span>{timeText}</span>
    </div>
  );
}

// ── Workflow mini-stepper (mobile) ────────────────────────────────────────────
// Shows: preceding → current → next ··· last
// Ellipsis only when lastIdx - nextIdx > 1.

interface StepNode {
  step: WorkflowStepBrief;
  state: "done" | "current" | "future";
  ellipsisAfter?: boolean; // render ··· after this node before the next
}

export function WorkflowMiniStepper({ steps, currentStepKey }: {
  steps: WorkflowStepBrief[];
  currentStepKey: string;
}) {
  if (!steps.length) return null;

  const currentIdx = steps.findIndex((s) => s.step_key === currentStepKey);
  if (currentIdx === -1) return null;

  const lastIdx = steps.length - 1;

  // Build the visible nodes: preceding, current, next, last (deduped)
  const visibleIdxSet = new Set<number>();
  if (currentIdx > 0) visibleIdxSet.add(currentIdx - 1);       // preceding
  visibleIdxSet.add(currentIdx);                                // current
  if (currentIdx < lastIdx) visibleIdxSet.add(currentIdx + 1); // next
  visibleIdxSet.add(lastIdx);                                   // last

  const visibleIdxs = Array.from(visibleIdxSet).sort((a, b) => a - b);

  const nodes: StepNode[] = visibleIdxs.map((idx, pos) => {
    const nextVisibleIdx = visibleIdxs[pos + 1];
    const ellipsisAfter = nextVisibleIdx !== undefined && nextVisibleIdx - idx > 1;
    return {
      step: steps[idx],
      state: idx < currentIdx ? "done" : idx === currentIdx ? "current" : "future",
      ellipsisAfter,
    };
  });

  return (
    <div className="flex items-center gap-0 px-4 py-2 bg-white border-b border-gray-100 overflow-x-auto scrollbar-none">
      {nodes.map(({ step, state, ellipsisAfter }, i) => (
        <div key={step.step_key} className="flex items-center min-w-0">
          {/* Connecting line before node (skip for first) */}
          {i > 0 && (
            <div className={`h-px w-4 flex-shrink-0 ${
              state === "done" ? "bg-blue-400" : "bg-gray-200"
            }`} />
          )}

          {/* Node */}
          <div className="flex flex-col items-center flex-shrink-0">
            <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
              state === "done"
                ? "bg-blue-500 border-blue-500"
                : state === "current"
                  ? "bg-blue-600 border-blue-600 ring-2 ring-blue-200"
                  : "bg-white border-gray-300"
            }`}>
              {state === "done" && (
                <svg className="w-2 h-2 text-white" fill="currentColor" viewBox="0 0 8 8">
                  <path d="M1.5 4l2 2 3-3" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round"/>
                </svg>
              )}
            </div>
            <span className={`text-[10px] mt-0.5 whitespace-nowrap ${
              state === "current" ? "text-blue-700 font-semibold" : "text-gray-400"
            }`}>
              {stepShortLabel(step.step_key)}
            </span>
          </div>

          {/* Ellipsis connector after node */}
          {ellipsisAfter && (
            <div className="flex items-center flex-shrink-0 mb-3">
              <div className="h-px w-2 bg-gray-200" />
              <span className="text-[10px] text-gray-300 leading-none mx-0.5">···</span>
              <div className="h-px w-2 bg-gray-200" />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
