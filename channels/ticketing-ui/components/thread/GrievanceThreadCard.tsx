"use client";

import { useEffect, useRef, useState } from "react";
import { CheckCircle2, ChevronDown, ChevronUp, MapPin, Tag } from "lucide-react";
import type { TicketDetail } from "@/lib/api";

interface GrievanceThreadCardProps {
  ticket: TicketDetail;
  onAcknowledge?: () => void;
  acknowledging?: boolean;
}

/** Pinned grievance summary + Acknowledge CTA (TP-09). */
export function GrievanceThreadCard({
  ticket,
  onAcknowledge,
  acknowledging = false,
}: GrievanceThreadCardProps) {
  const [expanded, setExpanded] = useState(true);
  const [reviewed, setReviewed] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);

  const showAck =
    ticket.status_code === "OPEN" &&
    (ticket.current_step?.expected_actions ?? []).includes("ACKNOWLEDGE");

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

  const categories = ticket.grievance_categories?.trim();
  const location = ticket.grievance_location?.trim();

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
        <div className="px-4 py-3 space-y-2.5">
          {ticket.grievance_summary ? (
            <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
              {ticket.grievance_summary}
            </p>
          ) : (
            <p className="text-sm text-gray-500 italic">No summary on file.</p>
          )}
          <div className="flex flex-wrap gap-2 text-xs text-gray-600">
            {categories && (
              <span className="inline-flex items-center gap-1 bg-white/80 border border-blue-100 rounded-full px-2 py-0.5">
                <Tag size={11} className="text-blue-500" />
                {categories}
              </span>
            )}
            {location && (
              <span className="inline-flex items-center gap-1 bg-white/80 border border-blue-100 rounded-full px-2 py-0.5">
                <MapPin size={11} className="text-blue-500" />
                {location}
              </span>
            )}
            {ticket.priority && (
              <span className="inline-flex items-center bg-white/80 border border-blue-100 rounded-full px-2 py-0.5">
                Priority: {ticket.priority}
              </span>
            )}
          </div>
        </div>
      )}

      {showAck && onAcknowledge && (
        <div className="px-4 pb-3 pt-1">
          <button
            type="button"
            onClick={onAcknowledge}
            disabled={!reviewed || acknowledging}
            title={reviewed ? undefined : "Scroll to read the grievance before acknowledging"}
            className="w-full bg-blue-600 active:bg-blue-700 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-3 rounded-xl text-sm flex items-center justify-center gap-2"
          >
            <CheckCircle2 size={16} strokeWidth={2} />
            {acknowledging ? "Acknowledging…" : reviewed ? "Acknowledge — I have read this grievance" : "Read grievance to enable Acknowledge"}
          </button>
        </div>
      )}
    </div>
  );
}
