"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import type { TicketDetail } from "@/lib/api";
import { validateTicketClassification } from "@/lib/api";
import { formatUserFacingError } from "@/lib/user-messages";

function parseCategoriesForEdit(raw: string | null | undefined): string {
  if (!raw?.trim()) return "";
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed.join(", ");
  } catch {
    /* plain string */
  }
  return raw;
}

function categoriesToPayload(text: string): string {
  const parts = text.split(",").map((s) => s.trim()).filter(Boolean);
  return JSON.stringify(parts);
}

interface ClassificationGrievancePanelProps {
  ticket: TicketDetail;
  onUpdated?: () => void;
  className?: string;
}

export function ClassificationGrievancePanel({
  ticket,
  onUpdated,
  className = "",
}: ClassificationGrievancePanelProps) {
  const [summary, setSummary] = useState(ticket.grievance_summary ?? "");
  const [categories, setCategories] = useState(
    parseCategoriesForEdit(ticket.grievance_categories),
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSummary(ticket.grievance_summary ?? "");
    setCategories(parseCategoriesForEdit(ticket.grievance_categories));
  }, [
    ticket.ticket_id,
    ticket.grievance_summary,
    ticket.grievance_categories,
    ticket.grievance_classification_status,
  ]);

  const needsOfficer = ticket.classification_officer_validation_required ?? false;
  const validated = ticket.classification_validated ?? false;

  const statusLabel = useMemo(() => {
    if (ticket.classification_validated_by_complainant) {
      return "Validated by complainant";
    }
    if (ticket.classification_validated_by_officer) {
      return "Validated by officer";
    }
    if (ticket.grievance_classification_status === "LLM_skipped") {
      return "LLM skipped — officer classification required";
    }
    if (ticket.grievance_classification_status === "LLM_failed") {
      return "Classification failed — officer review required";
    }
    if (ticket.grievance_classification_status === "pending") {
      return "Classification pending";
    }
    if (needsOfficer) {
      return "Review summary and categories before acknowledging";
    }
    return null;
  }, [ticket, needsOfficer]);

  async function handleConfirm() {
    setError(null);
    const summaryTrim = summary.trim();
    const catsTrim = categories.trim();
    if (!summaryTrim || !catsTrim) {
      setError("Summary and categories are required.");
      return;
    }
    setSaving(true);
    try {
      await validateTicketClassification(ticket.ticket_id, {
        grievance_summary: summaryTrim,
        grievance_categories: categoriesToPayload(catsTrim),
      });
      onUpdated?.();
    } catch (e) {
      setError(formatUserFacingError(e).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={className}>
      {statusLabel && (
        <div
          className={`mb-3 flex items-start gap-2 rounded-lg px-3 py-2 text-xs ${
            validated
              ? "bg-green-50 text-green-800 border border-green-200"
              : needsOfficer
                ? "bg-amber-50 text-amber-900 border border-amber-200"
                : "bg-gray-50 text-gray-600 border border-gray-200"
          }`}
        >
          {validated ? (
            <CheckCircle2 size={14} className="shrink-0 mt-0.5" />
          ) : needsOfficer ? (
            <AlertTriangle size={14} className="shrink-0 mt-0.5" />
          ) : null}
          <span>{statusLabel}</span>
        </div>
      )}

      {ticket.grievance_description ? (
        <div className="mb-3">
          <p className="text-xs font-medium text-gray-500 uppercase mb-1">Complainant narrative</p>
          <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
            {ticket.grievance_description}
          </p>
        </div>
      ) : null}

      {needsOfficer ? (
        <div className="space-y-3">
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1">Summary</label>
            <textarea
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              rows={4}
              className="w-full text-sm border border-amber-200 rounded-lg px-3 py-2 focus:ring-2 focus:ring-amber-400"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1">
              Categories (comma-separated)
            </label>
            <textarea
              value={categories}
              onChange={(e) => setCategories(e.target.value)}
              rows={2}
              className="w-full text-sm border border-amber-200 rounded-lg px-3 py-2 focus:ring-2 focus:ring-amber-400"
            />
          </div>
          {error && <p className="text-xs text-red-600">{error}</p>}
          <button
            type="button"
            onClick={handleConfirm}
            disabled={saving}
            className="w-full bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white font-semibold py-2.5 rounded-lg text-sm"
          >
            {saving ? (
              <span className="inline-flex items-center gap-2">
                <Loader2 size={14} className="animate-spin" />
                Saving…
              </span>
            ) : (
              "Confirm summary & categories"
            )}
          </button>
        </div>
      ) : (
        <>
          {ticket.grievance_summary ? (
            <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
              {ticket.grievance_summary}
            </p>
          ) : (
            <p className="text-sm text-gray-500 italic">No summary on file.</p>
          )}
          {ticket.grievance_categories && (
            <p className="text-xs text-gray-500 mt-2">
              <span className="font-medium">Categories:</span>{" "}
              {parseCategoriesForEdit(ticket.grievance_categories)}
            </p>
          )}
        </>
      )}
    </div>
  );
}
