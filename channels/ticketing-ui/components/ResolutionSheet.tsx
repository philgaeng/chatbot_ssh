"use client";

import { useEffect, useState } from "react";
import {
  RESOLUTION_CATEGORIES,
  RESOLUTION_MIN_NOTE_LEN,
  type ResolutionCategoryCode,
} from "@/lib/resolution";

export function ResolutionSheet({
  open,
  onClose,
  onSubmit,
  submitting,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (category: ResolutionCategoryCode, note: string) => Promise<void>;
  submitting: boolean;
}) {
  const [category, setCategory] = useState<ResolutionCategoryCode>("ACCEPTED_OTHER");
  const [note, setNote] = useState(RESOLUTION_CATEGORIES[4].defaultWording);

  useEffect(() => {
    if (!open) return;
    const def = RESOLUTION_CATEGORIES.find((c) => c.code === category);
    if (def) setNote(def.defaultWording);
  }, [category, open]);

  if (!open) return null;

  const valid = note.trim().length >= RESOLUTION_MIN_NOTE_LEN;

  return (
    <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center bg-black/40">
      <div className="bg-white w-full md:max-w-lg rounded-t-2xl md:rounded-2xl shadow-xl p-5 max-h-[90vh] overflow-y-auto">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Resolve case</h2>
        <p className="text-sm text-gray-500 mb-4">
          Choose an outcome category and describe what was decided. This will appear in the case thread.
        </p>
        <label className="block text-xs font-medium text-gray-600 mb-1">Resolution category</label>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value as ResolutionCategoryCode)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-4"
        >
          {RESOLUTION_CATEGORIES.map((c) => (
            <option key={c.code} value={c.code}>{c.label}</option>
          ))}
        </select>
        <label className="block text-xs font-medium text-gray-600 mb-1">
          Resolution text (min {RESOLUTION_MIN_NOTE_LEN} characters)
        </label>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={6}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-4"
        />
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="flex-1 py-2.5 rounded-xl border border-gray-300 text-gray-700 text-sm font-medium"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={!valid || submitting}
            onClick={() => onSubmit(category, note.trim())}
            className="flex-1 py-2.5 rounded-xl bg-green-600 text-white text-sm font-semibold disabled:opacity-50"
          >
            {submitting ? "Resolving…" : "Confirm resolve"}
          </button>
        </div>
      </div>
    </div>
  );
}
