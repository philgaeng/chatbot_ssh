"use client";

import { useEffect, useState } from "react";
import { ArrowUpCircle, Plus, X } from "lucide-react";
import { todayIsoDate } from "@/lib/field-visit";

export interface EscalationFormData {
  escalationDate: string;
  personsInvolved: string[];
  notes: string;
}

export function EscalationFormCard({
  open,
  currentUserId,
  rosterIds,
  submitting = false,
  onClose,
  onSubmit,
}: {
  open: boolean;
  currentUserId: string;
  rosterIds?: string[];
  submitting?: boolean;
  onClose: () => void;
  onSubmit: (data: EscalationFormData) => Promise<void>;
}) {
  const [escalationDate, setEscalationDate] = useState(todayIsoDate());
  const [persons, setPersons] = useState<string[]>([]);
  const [addPerson, setAddPerson] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setEscalationDate(todayIsoDate());
    setPersons([currentUserId]);
    setAddPerson("");
    setNotes("");
    setError(null);
  }, [open, currentUserId]);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    if (!notes.trim()) {
      setError("Escalation notes are required.");
      return;
    }
    setError(null);
    try {
      await onSubmit({
        escalationDate,
        personsInvolved: persons.length ? persons : [currentUserId],
        notes: notes.trim(),
      });
    } catch {
      // parent alerts
    }
  }

  function addPersonFromInput() {
    const p = addPerson.trim().replace(/^@/, "");
    if (!p || persons.includes(p)) return;
    setPersons((prev) => [...prev, p]);
    setAddPerson("");
  }

  const suggestions = (rosterIds ?? []).filter(
    (id) => id !== currentUserId && !persons.includes(id),
  );

  return (
    <form
      onSubmit={handleSubmit}
      className="mx-3 mb-2 rounded-xl border border-amber-300 bg-amber-50 shadow-sm overflow-hidden"
      aria-label="Escalation review"
    >
      <div className="flex items-start justify-between gap-2 px-3 py-2.5 border-b border-amber-200 bg-amber-100/60">
        <div className="flex items-center gap-2 min-w-0">
          <ArrowUpCircle size={17} strokeWidth={2} className="text-amber-700 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-gray-900 leading-tight">Escalate ticket</p>
            <p className="text-[11px] text-amber-800/90 mt-0.5">
              Date, people involved, and why escalation is needed.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          disabled={submitting}
          className="p-1 text-gray-400 hover:text-gray-600 rounded-lg shrink-0"
          aria-label="Close escalation form"
        >
          <X size={18} />
        </button>
      </div>

      <div className="px-3 py-3 space-y-3">
        {error && (
          <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">
            {error}
          </div>
        )}

        <label className="block">
          <span className="block text-[11px] font-semibold text-amber-900/80 uppercase tracking-wide mb-1">
            Escalation date
          </span>
          <input
            type="date"
            value={escalationDate}
            onChange={(e) => setEscalationDate(e.target.value)}
            className="w-full text-sm border border-amber-200 rounded-lg px-2 py-1.5 bg-white"
            required
          />
        </label>

        <div>
          <span className="block text-[11px] font-semibold text-amber-900/80 uppercase tracking-wide mb-1">
            Person(s) involved
          </span>
          <div className="flex flex-wrap gap-1.5 mb-2">
            {persons.map((p) => (
              <span
                key={p}
                className="inline-flex items-center gap-1 text-xs bg-white border border-amber-200 rounded-full px-2 py-0.5"
              >
                @{p}
                {p !== currentUserId && (
                  <button
                    type="button"
                    onClick={() => setPersons((prev) => prev.filter((x) => x !== p))}
                    className="text-gray-400 hover:text-gray-600"
                    aria-label={`Remove ${p}`}
                  >
                    ×
                  </button>
                )}
              </span>
            ))}
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={addPerson}
              onChange={(e) => setAddPerson(e.target.value)}
              placeholder="Add officer @email"
              className="flex-1 text-sm border border-amber-200 rounded-lg px-2 py-1.5 bg-white"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addPersonFromInput();
                }
              }}
            />
            <button
              type="button"
              onClick={addPersonFromInput}
              className="px-2 py-1.5 rounded-lg bg-amber-100 text-amber-800 hover:bg-amber-200"
              aria-label="Add person"
            >
              <Plus size={16} />
            </button>
          </div>
          {suggestions.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1">
              {suggestions.slice(0, 4).map((id) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setPersons((prev) => [...prev, id])}
                  className="text-[10px] text-blue-600 hover:underline"
                >
                  + @{id}
                </button>
              ))}
            </div>
          )}
        </div>

        <label className="block">
          <span className="block text-[11px] font-semibold text-amber-900/80 uppercase tracking-wide mb-1">
            Escalation notes (required)
          </span>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            required
            placeholder="Why is this case being escalated?"
            className="w-full text-sm border border-amber-200 rounded-lg px-2 py-1.5 bg-white resize-none"
          />
        </label>

        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-amber-600 hover:bg-amber-700 text-white font-semibold py-2.5 rounded-xl text-sm disabled:opacity-50"
        >
          {submitting ? "Escalating…" : "Confirm escalation"}
        </button>
      </div>
    </form>
  );
}
