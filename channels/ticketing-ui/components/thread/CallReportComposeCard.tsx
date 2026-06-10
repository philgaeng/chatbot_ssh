"use client";

import { useEffect, useState } from "react";
import { Phone, X } from "lucide-react";
import { nowIsoTime, todayIsoDate, type CallReportFormData } from "@/lib/field-visit";

export function CallReportComposeCard({
  open,
  submitting = false,
  mobileDialHint = false,
  onClose,
  onSubmit,
}: {
  open: boolean;
  submitting?: boolean;
  /** Mobile: point officers to the green dial button above this form. */
  mobileDialHint?: boolean;
  onClose: () => void;
  onSubmit: (data: CallReportFormData) => Promise<void>;
}) {
  const [callDate, setCallDate] = useState(todayIsoDate());
  const [callTime, setCallTime] = useState(nowIsoTime());
  const [personContacted, setPersonContacted] = useState("Complainant");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setCallDate(todayIsoDate());
    setCallTime(nowIsoTime());
    setPersonContacted("Complainant");
    setNotes("");
    setError(null);
  }, [open]);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setError(null);
    try {
      await onSubmit({ callDate, callTime, personContacted, notes });
    } catch {
      // parent handles
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mx-3 mb-2 rounded-xl border border-sky-200 bg-sky-50 shadow-sm overflow-hidden"
      aria-label="Call report"
    >
      <div className="flex items-start justify-between gap-2 px-3 py-2.5 border-b border-sky-200 bg-sky-100/60">
        <div className="flex items-center gap-2 min-w-0">
          <Phone size={17} strokeWidth={2} className="text-sky-700 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-gray-900 leading-tight">Call complainant</p>
            <p className="text-[11px] text-sky-800/90 mt-0.5">
              {mobileDialHint
                ? "Use the SMS or call buttons above, then log the contact here."
                : "Log phone contact on the case timeline."}
            </p>
          </div>
        </div>
        <button type="button" onClick={onClose} disabled={submitting} className="p-1 text-gray-400 hover:text-gray-600 rounded-lg shrink-0" aria-label="Close call report form">
          <X size={18} />
        </button>
      </div>

      <div className="px-3 py-3 space-y-3">
        {error && (
          <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">{error}</div>
        )}

        <div className="flex gap-2">
          <label className="flex-1 block">
            <span className="block text-[11px] font-semibold text-sky-900/80 uppercase tracking-wide mb-1">Date</span>
            <input type="date" value={callDate} onChange={(e) => setCallDate(e.target.value)} className="w-full text-sm border border-sky-200 rounded-lg px-2 py-1.5 bg-white" required />
          </label>
          <label className="w-28 block">
            <span className="block text-[11px] font-semibold text-sky-900/80 uppercase tracking-wide mb-1">Time</span>
            <input type="time" value={callTime} onChange={(e) => setCallTime(e.target.value)} className="w-full text-sm border border-sky-200 rounded-lg px-2 py-1.5 bg-white" />
          </label>
        </div>

        <label className="block">
          <span className="block text-[11px] font-semibold text-sky-900/80 uppercase tracking-wide mb-1">Person contacted</span>
          <input type="text" value={personContacted} onChange={(e) => setPersonContacted(e.target.value)} className="w-full text-sm border border-sky-200 rounded-lg px-2 py-1.5 bg-white" />
        </label>

        <label className="block">
          <span className="block text-[11px] font-semibold text-sky-900/80 uppercase tracking-wide mb-1">Notes</span>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} placeholder="Call outcome, follow-up needed…" className="w-full text-sm border border-sky-200 rounded-lg px-2 py-1.5 bg-white resize-none" />
        </label>

        <button type="submit" disabled={submitting} className="w-full bg-sky-600 hover:bg-sky-700 text-white font-semibold py-2.5 rounded-xl text-sm disabled:opacity-50">
          {submitting ? "Saving…" : "Save call report"}
        </button>
      </div>
    </form>
  );
}
