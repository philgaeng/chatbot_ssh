"use client";

import { useEffect, useState } from "react";
import { RefreshCw, X } from "lucide-react";
import { stepSupervisorLabel } from "@/lib/officer-permissions";
import type { TicketDetail } from "@/lib/api";

export type ReassignmentReasonCode = "OUT_OF_PACKAGE_SCOPE" | "OUT_OF_LOCATION" | "OTHER";

const REASON_OPTIONS: { code: ReassignmentReasonCode; label: string }[] = [
  { code: "OUT_OF_PACKAGE_SCOPE", label: "Out of package scope" },
  { code: "OUT_OF_LOCATION", label: "Out of location of responsibility" },
  { code: "OTHER", label: "Other" },
];

export function ReassignmentRequestCard({
  open,
  ticket,
  submitting = false,
  onClose,
  onSubmit,
}: {
  open: boolean;
  ticket: TicketDetail;
  submitting?: boolean;
  onClose: () => void;
  onSubmit: (reasonCode: ReassignmentReasonCode, notes: string) => Promise<void>;
}) {
  const [reasonCode, setReasonCode] = useState<ReassignmentReasonCode>("OUT_OF_PACKAGE_SCOPE");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setReasonCode("OUT_OF_PACKAGE_SCOPE");
    setNotes("");
    setError(null);
  }, [open]);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    if (reasonCode === "OTHER" && !notes.trim()) {
      setError("Notes are required when reason is Other.");
      return;
    }
    setError(null);
    try {
      await onSubmit(reasonCode, notes.trim());
    } catch {
      // parent alerts
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mx-3 mb-2 rounded-xl border border-violet-200 bg-violet-50 shadow-sm overflow-hidden"
      aria-label="Ask for reassignment"
    >
      <div className="flex items-start justify-between gap-2 px-3 py-2.5 border-b border-violet-200 bg-violet-100/60">
        <div className="flex items-center gap-2 min-w-0">
          <RefreshCw size={17} strokeWidth={2} className="text-violet-700 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-gray-900 leading-tight">Ask for reassignment</p>
            <p className="text-[11px] text-violet-800/90 mt-0.5">
              Routes to {stepSupervisorLabel(ticket.current_step)} for reassignment within the team or upward.
            </p>
          </div>
        </div>
        <button type="button" onClick={onClose} disabled={submitting} className="p-1 text-gray-400 hover:text-gray-600 rounded-lg shrink-0" aria-label="Close">
          <X size={18} />
        </button>
      </div>

      <div className="px-3 py-3 space-y-3">
        {error && (
          <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">{error}</div>
        )}

        <fieldset className="space-y-2">
          <legend className="text-[11px] font-semibold text-violet-900/80 uppercase tracking-wide">Reason</legend>
          {REASON_OPTIONS.map((opt) => (
            <label key={opt.code} className="flex items-start gap-2 text-sm text-gray-800 cursor-pointer">
              <input
                type="radio"
                name="reassign-reason"
                value={opt.code}
                checked={reasonCode === opt.code}
                onChange={() => setReasonCode(opt.code)}
                className="mt-0.5"
              />
              {opt.label}
            </label>
          ))}
        </fieldset>

        <label className="block">
          <span className="block text-[11px] font-semibold text-violet-900/80 uppercase tracking-wide mb-1">
            Notes{reasonCode === "OTHER" ? " (required)" : " (optional)"}
          </span>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            className="w-full text-sm border border-violet-200 rounded-lg px-2 py-1.5 bg-white resize-none"
            placeholder="Brief context for your supervisor"
          />
        </label>

        <button type="submit" disabled={submitting} className="w-full bg-violet-600 hover:bg-violet-700 text-white font-semibold py-2.5 rounded-xl text-sm disabled:opacity-50">
          {submitting ? "Submitting…" : "Submit reassignment request"}
        </button>
      </div>
    </form>
  );
}
