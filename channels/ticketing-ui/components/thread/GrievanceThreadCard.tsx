"use client";

import { useEffect, useRef, useState } from "react";
import { CheckCircle2, ChevronDown, ChevronUp } from "lucide-react";
import type { TicketDetail } from "@/lib/api";
import { ClassificationGrievancePanel } from "@/components/tickets/ClassificationGrievancePanel";

interface GrievanceThreadCardProps {
  ticket: TicketDetail;
  onAcknowledge?: () => void;
  acknowledging?: boolean;
  onClassificationUpdated?: () => void;
}

/** Pinned grievance summary + Acknowledge CTA (TP-09 / TP-14). */
export function GrievanceThreadCard({
  ticket,
  onAcknowledge,
  acknowledging = false,
  onClassificationUpdated,
}: GrievanceThreadCardProps) {
  const [expanded, setExpanded] = useState(true);
  const [reviewed, setReviewed] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);

  const needsOfficer = ticket.classification_officer_validation_required ?? false;

  const showAck =
    ticket.status_code === "OPEN" &&
    (ticket.current_step?.expected_actions ?? []).includes("ACKNOWLEDGE");

  const ackBlocked = needsOfficer;

  useEffect(() => {
    if (!cardRef.current || reviewed) return;
    const el = cardRef.current;
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setReviewed(true);
      },
      { threshold: 0.6 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [reviewed]);

  return (
    <div
      ref={cardRef}
      className="mx-3 my-3 rounded-xl border border-blue-200 bg-blue-50/80 shadow-sm overflow-hidden"
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between gap-2 px-4 py-2.5 text-left border-b border-blue-100 bg-blue-100/50"
      >
        <span className="text-xs font-semibold text-blue-800 uppercase tracking-wide">
          Original grievance
        </span>
        {expanded ? (
          <ChevronUp size={16} className="text-blue-600 shrink-0" />
        ) : (
          <ChevronDown size={16} className="text-blue-600 shrink-0" />
        )}
      </button>

      {expanded && (
        <div className="px-4 py-3">
          <ClassificationGrievancePanel
            ticket={ticket}
            onUpdated={onClassificationUpdated}
          />
        </div>
      )}

      {showAck && onAcknowledge && (
        <div className="px-4 pb-3 pt-1">
          {ackBlocked && (
            <p className="text-xs text-amber-800 mb-2">
              Confirm summary and categories above before acknowledging.
            </p>
          )}
          <button
            type="button"
            onClick={onAcknowledge}
            disabled={!reviewed || acknowledging || ackBlocked}
            title={
              ackBlocked
                ? "Complete classification review first"
                : reviewed
                  ? undefined
                  : "Scroll to read the grievance before acknowledging"
            }
            className="w-full bg-blue-600 active:bg-blue-700 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-3 rounded-xl text-sm flex items-center justify-center gap-2"
          >
            <CheckCircle2 size={16} strokeWidth={2} />
            {acknowledging
              ? "Acknowledging…"
              : ackBlocked
                ? "Confirm classification to enable Acknowledge"
                : reviewed
                  ? "Acknowledge — I have read this grievance"
                  : "Read grievance to enable Acknowledge"}
          </button>
        </div>
      )}
    </div>
  );
}
