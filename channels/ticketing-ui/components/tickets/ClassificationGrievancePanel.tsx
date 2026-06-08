"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import type { GrievanceCategoryOption, TicketDetail } from "@/lib/api";
import { listGrievanceCategories, validateTicketClassification } from "@/lib/api";
import {
  categoriesSelectionEqual,
  grievanceCategoriesToPayload,
  parseGrievanceCategoryList,
} from "@/lib/format-grievance";
import { formatUserFacingError } from "@/lib/user-messages";
import { GrievanceCategoryMultiSelect } from "@/components/tickets/GrievanceCategoryMultiSelect";

function SummaryStatusBadge({ ticket }: { ticket: TicketDetail }) {
  const needsOfficer = ticket.classification_officer_validation_required ?? false;
  const status = ticket.grievance_classification_status;

  let label: string;
  let tone: "green" | "amber" | "gray";

  if (ticket.classification_validated_by_officer) {
    label = "Validated by officer";
    tone = "green";
  } else if (ticket.classification_validated_by_complainant) {
    label = "Validated by complainant";
    tone = "green";
  } else if (status === "LLM_failed") {
    label = "Classification failed — review required";
    tone = "amber";
  } else if (status === "LLM_skipped") {
    label = "LLM skipped — officer must classify";
    tone = "amber";
  } else if (needsOfficer) {
    label = "Review required before acknowledge";
    tone = "amber";
  } else if (status === "pending" && !ticket.grievance_summary?.trim()) {
    label = "Summary pending";
    tone = "gray";
  } else if (status === "LLM_generated") {
    label = "Generated — not yet validated";
    tone = "amber";
  } else {
    label = "Not validated";
    tone = "gray";
  }

  const styles =
    tone === "green"
      ? "bg-green-50 text-green-800 border-green-200"
      : tone === "amber"
        ? "bg-amber-50 text-amber-900 border-amber-200"
        : "bg-gray-50 text-gray-600 border-gray-200";

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${styles}`}
    >
      {tone === "green" ? (
        <CheckCircle2 size={12} className="shrink-0" />
      ) : tone === "amber" ? (
        <AlertTriangle size={12} className="shrink-0" />
      ) : null}
      {label}
    </span>
  );
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
  const [categories, setCategories] = useState<string[]>(() =>
    parseGrievanceCategoryList(ticket.grievance_categories),
  );
  const [categoryOptions, setCategoryOptions] = useState<GrievanceCategoryOption[]>([]);
  const [categoriesLoading, setCategoriesLoading] = useState(true);
  const [categoriesLoadError, setCategoriesLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSummary(ticket.grievance_summary ?? "");
    setCategories(parseGrievanceCategoryList(ticket.grievance_categories));
  }, [
    ticket.ticket_id,
    ticket.grievance_summary,
    ticket.grievance_categories,
    ticket.grievance_classification_status,
  ]);

  useEffect(() => {
    let cancelled = false;
    setCategoriesLoading(true);
    setCategoriesLoadError(null);
    listGrievanceCategories()
      .then((opts) => {
        if (!cancelled) setCategoryOptions(opts);
      })
      .catch(() => {
        if (!cancelled) {
          setCategoriesLoadError("Could not load category list. Retry by refreshing the page.");
        }
      })
      .finally(() => {
        if (!cancelled) setCategoriesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const needsOfficer = ticket.classification_officer_validation_required ?? false;
  const ticketCategories = useMemo(
    () => parseGrievanceCategoryList(ticket.grievance_categories),
    [ticket.grievance_categories],
  );

  const isDirty = useMemo(() => {
    const summaryChanged =
      summary.trim() !== (ticket.grievance_summary ?? "").trim();
    const catsChanged = !categoriesSelectionEqual(categories, ticketCategories);
    return summaryChanged || catsChanged;
  }, [summary, categories, ticket.grievance_summary, ticketCategories]);

  const canSave =
    needsOfficer || isDirty || !(ticket.grievance_summary ?? "").trim();

  async function handleSave() {
    setError(null);
    const summaryTrim = summary.trim();
    if (!summaryTrim) {
      setError("Summary is required.");
      return;
    }
    if (categories.length === 0) {
      setError("Select at least one category.");
      return;
    }
    setSaving(true);
    try {
      await validateTicketClassification(ticket.ticket_id, {
        grievance_summary: summaryTrim,
        grievance_categories: grievanceCategoriesToPayload(categories),
      });
      onUpdated?.();
    } catch (e) {
      setError(formatUserFacingError(e).message);
    } finally {
      setSaving(false);
    }
  }

  const originalText = ticket.grievance_description?.trim() ?? "";
  const saveLabel = needsOfficer
    ? "Confirm summary & categories"
    : "Save changes";

  return (
    <div className={`space-y-4 ${className}`}>
      <div className="rounded-lg border border-gray-200 bg-gray-50/80 px-3 py-2.5">
        <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">
          Original grievance
        </p>
        {originalText ? (
          <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
            {originalText}
          </p>
        ) : (
          <p className="text-sm text-gray-500 italic">No original narrative on file.</p>
        )}
      </div>

      <div
        className={`rounded-lg border px-3 py-2.5 ${
          needsOfficer ? "border-amber-200 bg-amber-50/40" : "border-slate-200 bg-white"
        }`}
      >
        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
          <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide">
            Summary
          </p>
          <SummaryStatusBadge ticket={ticket} />
        </div>
        <textarea
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          rows={4}
          placeholder="LLM or officer summary of the grievance…"
          className={`w-full text-sm rounded-lg px-3 py-2 leading-relaxed focus:ring-2 ${
            needsOfficer
              ? "border border-amber-200 focus:ring-amber-400"
              : "border border-slate-200 focus:ring-blue-400"
          }`}
        />
        {!summary.trim() && (
          <p className="text-xs text-gray-500 mt-1 italic">
            No summary yet — enter one or wait for classification to finish.
          </p>
        )}
      </div>

      <div className="rounded-lg border border-slate-200 bg-white px-3 py-2.5">
        <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-2">
          Categories
        </p>
        <GrievanceCategoryMultiSelect
          value={categories}
          onChange={setCategories}
          options={categoryOptions}
          loading={categoriesLoading}
          loadError={categoriesLoadError}
        />
      </div>

      {error && <p className="text-xs text-red-600">{error}</p>}

      <button
        type="button"
        onClick={() => void handleSave()}
        disabled={saving || !canSave}
        title={
          !canSave && !needsOfficer
            ? "No changes to save"
            : undefined
        }
        className={`w-full font-semibold py-2.5 rounded-lg text-sm disabled:opacity-50 ${
          needsOfficer
            ? "bg-amber-600 hover:bg-amber-700 text-white"
            : "bg-slate-700 hover:bg-slate-800 text-white"
        }`}
      >
        {saving ? (
          <span className="inline-flex items-center justify-center gap-2">
            <Loader2 size={14} className="animate-spin" />
            Saving…
          </span>
        ) : (
          saveLabel
        )}
      </button>

      {needsOfficer && (
        <p className="text-xs text-amber-800">
          Confirm summary and categories before acknowledging this case.
        </p>
      )}
    </div>
  );
}
