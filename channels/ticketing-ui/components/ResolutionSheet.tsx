// SPDX-License-Identifier: Apache-2.0

"use client";

import { useState } from "react";
import type { ResolutionOption } from "@/lib/api";
import { RESOLUTION_MIN_NOTE_LEN, resolutionFormState } from "@/lib/resolution";

/**
 * Resolve form (spec 08 §2.6). What an officer can choose comes from the case's workflow
 * (`TicketDetail.resolution_options`, GRM-116). **No options means a sensitive workflow**: the
 * case records no action, so the form is the resolution text alone.
 */
export function ResolutionSheet(props: {
  open: boolean;
  onClose: () => void;
  onSubmit: (category: string | null, note: string) => Promise<void>;
  submitting: boolean;
  options: ResolutionOption[];
  /** Why the last submit was refused — shown inside the sheet, which covers the page's notice. */
  error?: string | null;
}) {
  // Mounting the form only while open gives every opening fresh state, with no effect to seed it.
  if (!props.open) return null;
  return <ResolutionForm {...props} />;
}

function ResolutionForm({
  onClose,
  onSubmit,
  submitting,
  options,
  error,
}: Parameters<typeof ResolutionSheet>[0]) {
  const [chosen, setChosen] = useState<string | null>(null);
  const [typed, setTyped] = useState<string | null>(null);
  const { textOnly, category, note, valid } = resolutionFormState(options, chosen, typed);

  return (
    <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center bg-black/40">
      <div className="bg-white w-full md:max-w-lg rounded-t-2xl md:rounded-2xl shadow-xl p-5 max-h-[90vh] overflow-y-auto">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Resolve case</h2>
        <p className="text-sm text-gray-500 mb-4">
          {textOnly
            ? "Describe what was decided. This will appear in the case thread."
            : "Choose what was done and describe what was decided. This will appear in the case thread."}
        </p>
        {!textOnly && (
          <>
            <label htmlFor="resolution-action" className="block text-xs font-medium text-gray-600 mb-1">
              What was done
            </label>
            <select
              id="resolution-action"
              value={category ?? ""}
              onChange={(e) => setChosen(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-4"
            >
              {options.map((o) => (
                <option key={o.code} value={o.code}>{o.label}</option>
              ))}
            </select>
          </>
        )}
        <label htmlFor="resolution-text" className="block text-xs font-medium text-gray-600 mb-1">
          Resolution text (at least {RESOLUTION_MIN_NOTE_LEN} characters)
        </label>
        <textarea
          id="resolution-text"
          value={note}
          onChange={(e) => setTyped(e.target.value)}
          rows={6}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-4"
        />
        {error && (
          <p role="alert" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2 mb-4">
            {error}
          </p>
        )}
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
            onClick={() => onSubmit(textOnly ? null : category, note.trim())}
            className="flex-1 py-2.5 rounded-xl bg-green-600 text-white text-sm font-semibold disabled:opacity-50"
          >
            {submitting ? "Resolving…" : "Confirm resolve"}
          </button>
        </div>
      </div>
    </div>
  );
}
