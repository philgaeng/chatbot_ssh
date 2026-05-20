"use client";

import { useEffect, useState } from "react";
import { MapPin, X } from "lucide-react";
import { formatFieldVisitNote, todayIsoDate, type FieldVisitFormData } from "@/lib/field-visit";

export function FieldVisitReportModal({
  open,
  defaultLocation,
  submitting,
  onClose,
  onSubmit,
}: {
  open: boolean;
  defaultLocation?: string | null;
  submitting?: boolean;
  onClose: () => void;
  onSubmit: (note: string) => Promise<void>;
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
    if (!visitDate) {
      setError("Visit date is required.");
      return;
    }
    setError(null);
    const payload: FieldVisitFormData = { visitDate, location, personMet, notes };
    await onSubmit(formatFieldVisitNote(payload));
  }

  const panel = (
    <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-xl w-full max-w-md max-h-[90vh] overflow-y-auto">
      <div className="flex items-start justify-between gap-3 px-5 pt-5 pb-3 border-b border-gray-100">
        <div>
          <div className="flex items-center gap-2 text-amber-700">
            <MapPin size={18} strokeWidth={2} />
            <h2 className="text-base font-semibold text-gray-900">Field visit report</h2>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Complete the visit and save a structured note on this case.
          </p>
        </div>
        <button type="button" onClick={onClose} className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg" aria-label="Close">
          <X size={18} />
        </button>
      </div>

      <div className="px-5 py-4 space-y-4">
        {error && (
          <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            {error}
          </div>
        )}

        <label className="block">
          <span className="block text-xs font-medium text-gray-600 mb-1.5">Visit date</span>
          <div className="flex gap-2">
            <input
              type="date"
              required
              value={visitDate}
              onChange={(e) => setVisitDate(e.target.value)}
              className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
            />
            <button
              type="button"
              onClick={() => setVisitDate(todayIsoDate())}
              className="shrink-0 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800 hover:bg-amber-100"
            >
              Today
            </button>
          </div>
        </label>

        <label className="block">
          <span className="block text-xs font-medium text-gray-600 mb-1.5">Location</span>
          <input
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="Village, ward, site marker…"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
          />
        </label>

        <label className="block">
          <span className="block text-xs font-medium text-gray-600 mb-1.5">Person met</span>
          <input
            type="text"
            value={personMet}
            onChange={(e) => setPersonMet(e.target.value)}
            placeholder="Name and role (e.g. complainant, contractor rep)"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
          />
        </label>

        <label className="block">
          <span className="block text-xs font-medium text-gray-600 mb-1.5">Notes</span>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={4}
            placeholder="Observations, agreements, follow-up needed…"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-amber-400"
          />
        </label>
      </div>

      <div className="px-5 py-4 border-t border-gray-100 flex gap-2">
        <button
          type="button"
          onClick={onClose}
          disabled={submitting}
          className="flex-1 rounded-xl border border-gray-200 py-2.5 text-sm font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={submitting}
          className="flex-1 rounded-xl bg-amber-500 hover:bg-amber-600 disabled:opacity-60 py-2.5 text-sm font-semibold text-white"
        >
          {submitting ? "Saving…" : "Save & complete visit"}
        </button>
      </div>
    </form>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 p-0 sm:p-4" onClick={onClose}>
      <div className="w-full sm:max-w-md" onClick={(e) => e.stopPropagation()}>
        {panel}
      </div>
    </div>
  );
}
