"use client";

import { useEffect, useState } from "react";
import { ClipboardList, MapPin, X } from "lucide-react";
import { type FieldVisitFormData, todayIsoDate } from "@/lib/field-visit";

export function FieldReportComposeCard({
  open,
  defaultLocation,
  completeVisit,
  submitting = false,
  onClose,
  onSubmit,
}: {
  open: boolean;
  defaultLocation?: string | null;
  completeVisit?: boolean;
  submitting?: boolean;
  onClose: () => void;
  onSubmit: (data: FieldVisitFormData) => Promise<void>;
}) {
  const [visitDate, setVisitDate] = useState(todayIsoDate());
  const [location, setLocation] = useState("");
  const [personMet, setPersonMet] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setVisitDate(todayIsoDate());
    setLocation(defaultLocation?.trim() ?? "");
    setPersonMet("");
    setNotes("");
    setError(null);
  }, [open, defaultLocation]);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    if (!visitDate) {
      setError("Visit date is required.");
      return;
    }
    setError(null);
    try {
      await onSubmit({ visitDate, location, personMet, notes });
    } catch {
      // Parent shows alert
    }
  }

  const title = completeVisit ? "Complete inspection visit" : "Field report";
  const TitleIcon = completeVisit ? MapPin : ClipboardList;

  return (
    <form
      onSubmit={handleSubmit}
      className="mx-3 mb-2 rounded-xl border border-amber-200 bg-amber-50 shadow-sm overflow-hidden"
      aria-label={title}
    >
      <div className="flex items-start justify-between gap-2 px-3 py-2.5 border-b border-amber-200 bg-amber-100/60">
        <div className="flex items-center gap-2 min-w-0">
          <TitleIcon size={17} strokeWidth={2} className="text-amber-700 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-gray-900 leading-tight">{title}</p>
            <p className="text-[11px] text-amber-800/90 mt-0.5">
              {completeVisit
                ? "Saved as a field report on this case."
                : "Date, location, who you met, and notes."}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          disabled={submitting}
          className="p-1 text-gray-400 hover:text-gray-600 rounded-lg shrink-0"
          aria-label="Close field report form"
        >
          <X size={18} />
        </button>
      </div>

      <div className="px-3 py-3 space-y-3">
        {error && (
          <div
            role="alert"
            className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800"
          >
            {error}
          </div>
        )}

        <label className="block">
          <span className="block text-[11px] font-semibold text-amber-900/80 uppercase tracking-wide mb-1">
            Visit date
          </span>
          <div className="flex gap-2">
            <input
              type="date"
              required
              value={visitDate}
              onChange={(e) => setVisitDate(e.target.value)}
              className="flex-1 min-w-0 rounded-lg border border-amber-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
            />
            <button
              type="button"
              onClick={() => setVisitDate(todayIsoDate())}
              className="shrink-0 rounded-lg border border-amber-300 bg-white px-2.5 py-2 text-xs font-semibold text-amber-800 hover:bg-amber-100"
            >
              Today
            </button>
          </div>
        </label>

        <label className="block">
          <span className="block text-[11px] font-semibold text-amber-900/80 uppercase tracking-wide mb-1">
            Location
          </span>
          <input
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="Village, ward, site…"
            className="w-full rounded-lg border border-amber-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
          />
        </label>

        <label className="block">
          <span className="block text-[11px] font-semibold text-amber-900/80 uppercase tracking-wide mb-1">
            Person met
          </span>
          <input
            type="text"
            value={personMet}
            onChange={(e) => setPersonMet(e.target.value)}
            placeholder="Name and role"
            className="w-full rounded-lg border border-amber-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
          />
        </label>

        <label className="block">
          <span className="block text-[11px] font-semibold text-amber-900/80 uppercase tracking-wide mb-1">
            Notes
          </span>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            placeholder="Observations, agreements, follow-up…"
            className="w-full rounded-lg border border-amber-200 bg-white px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-amber-400"
          />
        </label>
      </div>

      <div className="px-3 py-2.5 border-t border-amber-200 flex gap-2 bg-amber-100/50">
        <button
          type="button"
          onClick={onClose}
          disabled={submitting}
          className="flex-1 rounded-lg border border-amber-200 bg-white py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={submitting}
          className="flex-[1.35] rounded-lg bg-amber-500 hover:bg-amber-600 active:bg-amber-700 disabled:opacity-60 py-2 text-sm font-semibold text-white"
        >
          {submitting
            ? "Saving…"
            : completeVisit
              ? "Save & complete visit"
              : "Save field report"}
        </button>
      </div>
    </form>
  );
}
