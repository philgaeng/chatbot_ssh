"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getTicket, getSla, performAction, markSeen, replyToComplainant, getGrievancePii,
  listTicketFiles, listOfficers, listOfficerRoster, patchTicket,
  listOfficerAttachments, uploadOfficerAttachment,
  complainantFilePath, officerAttachmentPath,
  generateFindings, listTicketTasks, completeTask, createTask,
  type TicketDetail, type SlaStatus, type GrievancePii, type TicketFile,
  type OfficerBrief, type OfficerAttachment, type RevealSession, type TicketTask, type TicketEvent,
} from "@/lib/api";
import { useAuth } from "@/app/providers/AuthProvider";
import { assigneeIsCurrentUser, canonicalUserId } from "@/lib/auth/token-storage";
import { RevealModal, RevealOverlay } from "@/components/ui/VaultReveal";
import { StatusBadge, PriorityBadge, SeahBadge } from "@/components/ui/Badge";

import { NoteBubble }                        from "@/components/thread/NoteBubble";
import { SystemPill }                         from "@/components/thread/SystemPill";
import { TaskCard, AssignTaskSheet }          from "@/components/thread/TaskCard";
import { FilterChips, type FilterChip }       from "@/components/thread/FilterChips";
import { ViewersBar }                         from "@/components/thread/ViewersBar";
import { ComposeBar }                         from "@/components/thread/ComposeBar";
import { FieldReportComposeCard }             from "@/components/thread/FieldReportComposeCard";
import { EscalationFormCard }                 from "@/components/thread/EscalationFormCard";
import { ReassignmentRequestCard, type ReassignmentReasonCode } from "@/components/thread/ReassignmentRequestCard";
import { CallReportComposeCard } from "@/components/thread/CallReportComposeCard";
import { ResolutionSheet }                    from "@/components/ResolutionSheet";
import { ActionNotice }                       from "@/components/ActionNotice";
import { hasImageAttachment }                 from "@/lib/attachments";
import {
  canAssignTicket,
  canSupervisorAssign,
  getReassignMode,
} from "@/lib/officer-permissions";
import {
  formatUserFacingError,
  MSG_IMAGE_BEFORE_ESCALATE,
  MSG_IMAGE_BEFORE_RESOLVE,
  MSG_SUPERVISOR_ONLY_ASSIGN,
  type ActionNoticeState,
} from "@/lib/user-messages";
import type { ResolutionCategoryCode }        from "@/lib/resolution";
import {
  formatCallReportNote,
  isSiteVisitTask,
  parseInspectAssignCommand,
  type CallReportFormData,
  type FieldVisitFormData,
} from "@/lib/field-visit";
import { submitStructuredFieldReport } from "@/lib/submit-field-report";
import { formatGrievanceCategories } from "@/lib/format-grievance";
import { ensureTicketAcknowledged } from "@/lib/ticket-ack";
import { shouldRenderTaskCardInThread } from "@/lib/thread-tasks";
import { ComplainantContactFields } from "@/components/tickets/ComplainantContactFields";
import { ComplainantEditForm } from "@/components/tickets/ComplainantEditForm";
import {
  SYSTEM_EVENT_TYPES, TASK_EVENT_TYPES, NOTIFICATION_ONLY_EVENT_TYPES, COMPLAINANT_EVENT_TYPES, getTaskTypeInfo, AUTHORITY_ROLES,
  isThreadTaskEvent,
  type HashCommand,
} from "@/lib/mobile-constants";
import {
  IconAcknowledge, IconEscalateAction, IconResolve, IconGrcConvene,
  IconReply, IconTask, IconAssign, IconTranslations,
  IconEdit,
  IconFileImage, IconFilePdf, IconFileOther, IconUpload,
  IconFindings, IconRegenerate, IconWarning, IconClose,
  TaskTypeIcon,
} from "@/lib/icons";
import { Check, RefreshCw } from "lucide-react";
import { ClassificationGrievancePanel } from "@/components/tickets/ClassificationGrievancePanel";

// ── SLA urgency helpers ───────────────────────────────────────────────────────

function slaColorCls(hours: number | null | undefined, breached: boolean): string {
  if (breached || (hours != null && hours < 24))
    return "text-red-600 bg-red-50 border border-red-200";
  if (hours != null && hours < 72)
    return "text-amber-600 bg-amber-50 border border-amber-200";
  if (hours != null)
    return "text-green-600 bg-green-50 border border-green-200";
  return "text-gray-500 bg-gray-50 border border-gray-200";
}

function slaTimeLabel(
  hours: number | null | undefined,
  breached: boolean,
  resolutionDays?: number | null,
): string | null {
  if (breached) return "Overdue";
  if (hours != null)
    return hours < 24 ? `${Math.round(hours)}h left` : `${Math.round(hours / 24)}d left`;
  if (resolutionDays) return `${resolutionDays}d target`;
  return null;
}

// ── Translation review panel ───────────────────────────────────────────────────

function TranslationPanel({
  events,
  onClose,
}: {
  events: TicketDetail["events"];
  onClose: () => void;
}) {
  const notes = [...events]
    .filter((e) => e.event_type === "NOTE_ADDED" && e.note)
    .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());

  return (
    <div className="w-full h-full flex flex-col border-l border-gray-200 bg-gray-50 overflow-y-auto">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-white sticky top-0 z-10">
        <span className="text-sm font-semibold text-blue-700 flex items-center gap-1.5">
          <IconTranslations size={14} strokeWidth={2} />
          Translation Review
        </span>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 p-0.5">
          <IconClose size={16} strokeWidth={2} />
        </button>
      </div>
      <div className="flex-1 p-3 space-y-4">
        {notes.length === 0 ? (
          <p className="text-xs text-gray-400 italic p-2">No notes in this case yet.</p>
        ) : notes.map((e) => {
          const payload = e.payload as Record<string, unknown> | null;
          const translationEn = payload?.translation_en as string | undefined;
          const isSame = translationEn === e.note;
          return (
            <div key={e.event_id} className="space-y-1.5">
              <div className="text-xs text-gray-400">
                {new Date(e.created_at).toLocaleDateString()} · {e.created_by_user_id ?? "—"}
              </div>
              <div className="rounded border border-gray-200 bg-white p-2">
                <div className="text-xs font-medium text-gray-400 mb-1">Original</div>
                <div className="text-sm text-gray-700 italic">{e.note}</div>
              </div>
              <div className={`rounded border p-2 ${
                !translationEn ? "border-amber-200 bg-amber-50" :
                isSame ? "border-gray-200 bg-white" : "border-blue-100 bg-blue-50"
              }`}>
                <div className="text-xs font-medium text-gray-400 mb-1">English</div>
                {!translationEn
                  ? <div className="text-xs text-amber-600 flex items-center gap-1"><RefreshCw size={11} strokeWidth={2} className="animate-spin" /> Translation pending</div>
                  : isSame
                    ? <div className="text-xs text-gray-500">= Same (already English)</div>
                    : <div className="text-sm text-blue-800">{translationEn}</div>
                }
              </div>
            </div>
          );
        })}
      </div>
      <div className="px-3 py-2 border-t border-gray-100 text-xs text-gray-400">
        Translations are AI-generated. Bilingual officers may verify accuracy above.
      </div>
    </div>
  );
}

import { AttachmentListSection } from "@/components/AttachmentListSection";

function FilesPanel({
  ticketId,
  refreshKey,
  onBeforeDownload,
  isAssigned,
  onUpload,
}: {
  ticketId: string;
  refreshKey: number;
  onBeforeDownload: () => Promise<void>;
  isAssigned: boolean;
  onUpload: () => void;
}) {
  const [complainantFiles, setComplainantFiles] = useState<TicketFile[]>([]);
  const [officerFiles, setOfficerFiles]         = useState<OfficerAttachment[]>([]);
  const [loading, setLoading]                   = useState(true);
  const [selectedFile, setSelectedFile]         = useState<File | null>(null);
  const [caption, setCaption]                   = useState("");
  const [uploading, setUploading]               = useState(false);
  const [uploadError, setUploadError]           = useState<string | null>(null);

  async function loadFiles() {
    try {
      const [cf, of_] = await Promise.all([
        listTicketFiles(ticketId).catch(() => [] as TicketFile[]),
        listOfficerAttachments(ticketId).catch(() => [] as OfficerAttachment[]),
      ]);
      setComplainantFiles(cf);
      setOfficerFiles(of_);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { loadFiles(); }, [ticketId, refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const fmt = (bytes: number) =>
    bytes < 1024 ? `${bytes} B` : bytes < 1024 ** 2 ? `${(bytes / 1024).toFixed(0)} KB` : `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  const FileIcon = ({ type }: { type: string | null }) =>
    type === "image" ? <IconFileImage size={13} strokeWidth={2} className="shrink-0" /> :
    type === "pdf"   ? <IconFilePdf   size={13} strokeWidth={2} className="shrink-0" /> :
                       <IconFileOther size={13} strokeWidth={2} className="shrink-0" />;

  async function handleUpload() {
    if (!selectedFile) return;
    setUploading(true);
    setUploadError(null);
    try {
      await onBeforeDownload();
      await uploadOfficerAttachment(ticketId, selectedFile, caption);
      setSelectedFile(null);
      setCaption("");
      await loadFiles();
      onUpload();
    } catch (e) {
      setUploadError(formatUserFacingError(e, "upload").message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-4">
      <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide border-l-[3px] border-blue-500 pl-3">Attachments</h2>

      <AttachmentListSection
        complainantFiles={complainantFiles}
        officerFiles={officerFiles}
        complainantFilePath={complainantFilePath}
        officerFilePath={officerAttachmentPath}
        onBeforeDownload={onBeforeDownload}
      />

      {isAssigned && (
        <div className="border-t border-gray-100 pt-3 space-y-2">
          <div className="text-xs font-medium text-gray-600">Attach a document</div>
          <input type="file" onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)} className="text-xs text-gray-600 w-full" />
          <input type="text" value={caption} onChange={(e) => setCaption(e.target.value)}
            placeholder="Caption (optional)…"
            className="w-full text-xs border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
          {uploadError && <div className="text-xs text-red-500">{uploadError}</div>}
          <button onClick={handleUpload} disabled={!selectedFile || uploading}
            className="w-full text-xs bg-gray-100 text-gray-700 hover:bg-gray-200 rounded-lg px-2 py-1.5 disabled:opacity-50 transition font-medium"
          >
            {uploading ? "Uploading…" : <><IconUpload size={12} strokeWidth={2} className="inline mr-1" />Upload</>}
          </button>
        </div>
      )}
    </div>
  );
}

// ── Complainant edit sheet (desktop modal) ────────────────────────────────────

function EditComplainantSheet({
  ticket,
  pii,
  onClose,
  onSaved,
}: {
  ticket: TicketDetail;
  pii: GrievancePii | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-white w-full sm:max-w-md rounded-t-2xl sm:rounded-2xl shadow-2xl p-6 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-800">Edit complainant info</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">✕</button>
        </div>
        <ComplainantEditForm
          ticket={ticket}
          pii={pii}
          variant="desktop"
          onSaved={onSaved}
          onCancel={onClose}
        />
      </div>
    </div>
  );
}

// ── Complainant card ───────────────────────────────────────────────────────────

function ComplainantCard({
  ticket,
  onRevealOriginal,
  onComplainantUpdated,
}: {
  ticket: TicketDetail;
  onRevealOriginal: () => void;
  onComplainantUpdated?: () => void;
}) {
  const [pii, setPii]               = useState<GrievancePii | null>(null);
  const [piiLoading, setPiiLoading] = useState(false);
  const [piiError, setPiiError]     = useState<string | null>(null);
  const [editOpen, setEditOpen]     = useState(false);

  function loadPii() {
    setPiiLoading(true);
    setPiiError(null);
    getGrievancePii(ticket.ticket_id)
      .then(setPii)
      .catch(() => setPiiError("Could not load complainant details"))
      .finally(() => setPiiLoading(false));
  }

  useEffect(() => { loadPii(); }, [ticket.ticket_id]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleSaved() {
    loadPii();
    onComplainantUpdated?.();
  }

  return (
    <>
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide border-l-[3px] border-blue-500 pl-3">Complainant</h2>
          {ticket.complainant_id && (
            <button
              onClick={() => setEditOpen(true)}
              className="text-xs text-blue-600 hover:text-blue-800 font-medium"
            >
              <IconEdit size={13} strokeWidth={2} className="inline mr-1" />
              Edit
            </button>
          )}
        </div>
        {piiLoading ? (
          <div className="text-xs text-gray-400">Loading…</div>
        ) : piiError ? (
          <div className="text-xs space-y-2">
            <div className="text-gray-600">
              <span className="text-gray-400">Ref:</span> {ticket.complainant_id ?? "—"}
            </div>
            <div className="text-gray-400 italic">{piiError}</div>
            <button onClick={loadPii} className="text-xs text-blue-500 hover:text-blue-700 underline">
              ↺ Retry
            </button>
          </div>
        ) : (
          <ComplainantContactFields
            ticket={ticket}
            pii={pii}
            variant="desktop"
            onRevealOriginal={onRevealOriginal}
          />
        )}
      </div>

      {editOpen && (
        <EditComplainantSheet
          ticket={ticket}
          pii={pii}
          onClose={() => setEditOpen(false)}
          onSaved={handleSaved}
        />
      )}
    </>
  );
}

// ── AI findings card ──────────────────────────────────────────────────────────

const FINDINGS_ROLES = new Set([
  "grc_chair", "adb_hq_safeguards", "adb_hq_project", "adb_hq_exec",
  "adb_national_project_director", "super_admin", "local_admin",
]);

function FindingsCard({
  ticket,
  roleKeys,
  onRefresh,
}: {
  ticket: TicketDetail;
  roleKeys: string[];
  onRefresh: () => void;
}) {
  const canView = roleKeys.some((r) => FINDINGS_ROLES.has(r));
  const [regenerating, setRegenerating] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const categoryLabel = formatGrievanceCategories(ticket.grievance_categories);
  const validatedSummary = ticket.grievance_summary?.trim() ?? "";

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  useEffect(() => {
    if (ticket.ai_summary_en) {
      setStatusMsg(null);
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }
  }, [ticket.ai_summary_en]);

  if (!canView) return null;

  function startPolling() {
    if (pollRef.current) clearInterval(pollRef.current);
    let attempts = 0;
    pollRef.current = setInterval(() => {
      attempts += 1;
      void onRefresh();
      if (attempts >= 15) {
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = null;
        setStatusMsg((prev) =>
          prev?.includes("Generating")
            ? "Still generating — try Refresh in the case header or click Regenerate again."
            : prev,
        );
      }
    }, 2000);
  }

  async function handleRegenerate() {
    setRegenerating(true);
    setStatusMsg(null);
    try {
      await generateFindings(ticket.ticket_id);
      if (!ticket.ai_summary_en) {
        setStatusMsg("Generating AI case summary…");
        startPolling();
      } else {
        await onRefresh();
      }
    } catch (e) {
      setStatusMsg(formatUserFacingError(e).message);
    } finally {
      setRegenerating(false);
    }
  }

  return (
    <div className="bg-white rounded-xl border border-blue-100 p-4">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide border-l-[3px] border-indigo-400 pl-3 flex items-center gap-1.5">
          <IconFindings size={14} strokeWidth={2} className="text-indigo-500" />
          Findings
        </h2>
        <button
          type="button"
          onClick={() => void handleRegenerate()}
          disabled={regenerating}
          className="text-xs text-blue-500 hover:text-blue-700 disabled:opacity-50 inline-flex items-center gap-1"
        >
          <IconRegenerate size={11} strokeWidth={2} className={regenerating ? "animate-spin" : ""} />
          {regenerating ? "Queuing…" : ticket.ai_summary_en ? "Regenerate" : "Generate"}
        </button>
      </div>

      {(categoryLabel || validatedSummary) && (
        <div className="mb-3 rounded-lg border border-indigo-100 bg-indigo-50/60 px-3 py-2 space-y-1">
          <p className="text-[11px] font-semibold text-indigo-800 uppercase tracking-wide">
            Validated in chatbot
          </p>
          {categoryLabel && (
            <p className="text-sm text-indigo-900">
              <span className="font-medium">Category:</span> {categoryLabel}
            </p>
          )}
          {validatedSummary && (
            <p className="text-sm text-gray-800 leading-snug">{validatedSummary}</p>
          )}
        </div>
      )}

      {statusMsg && (
        <div className="text-xs text-blue-700 bg-blue-50 rounded px-2 py-1.5 mb-2">{statusMsg}</div>
      )}

      {ticket.ai_summary_en ? (
        <>
          <p className="text-[11px] font-medium text-gray-500 uppercase mb-1">AI case summary</p>
          <p className="text-sm text-gray-700 leading-relaxed">{ticket.ai_summary_en}</p>
          {ticket.ai_summary_updated_at && (
            <p className="text-xs text-gray-400 mt-2">
              Last generated {new Date(ticket.ai_summary_updated_at).toLocaleString()}
            </p>
          )}
        </>
      ) : (
        <p className="text-xs text-gray-500">
          No AI summary yet. It is generated automatically for new cases; use Generate if this case
          was filed before that was enabled.
        </p>
      )}
    </div>
  );
}

// ── Field reports card ────────────────────────────────────────────────────────

function FieldReportsCard({ ticket }: { ticket: TicketDetail }) {
  const reports = (ticket.events ?? []).filter(
    (e) => e.event_type === "NOTE_ADDED" && (e.payload as Record<string, unknown> | null)?.is_field_report === true
  );

  return (
    <div className="bg-white rounded-xl border border-amber-100 p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide border-l-[3px] border-amber-400 pl-3 flex items-center gap-1.5">
          📋 Field Reports
        </h2>
        <span className="text-[11px] text-gray-400">{reports.length} report{reports.length !== 1 ? "s" : ""}</span>
      </div>
      {reports.length === 0 ? (
        <p className="text-xs text-gray-400 italic">
          No field reports yet. Assign an inspection visit with <span className="font-mono bg-gray-100 px-1 rounded">#inspect</span> and complete the visit to add one.
        </p>
      ) : (
        <div className="space-y-3">
          {[...reports].reverse().map((r) => (
            <div key={r.event_id} className="border-l-2 border-amber-200 pl-3">
              <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">{r.note}</p>
              <p className="text-[11px] text-gray-400 mt-1">
                {r.created_by_user_id ?? "Officer"} · {new Date(r.created_at).toLocaleString()}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Workflow progress card ────────────────────────────────────────────────────

const WORKFLOW_STEPS: Record<string, { key: string; label: string }[]> = {
  standard: [
    { key: "LEVEL_1_SITE",   label: "L1 Site"   },
    { key: "LEVEL_2_PIU",    label: "L2 PIU"    },
    { key: "LEVEL_3_GRC",    label: "L3 GRC"    },
    { key: "LEVEL_4_LEGAL",  label: "L4 Legal"  },
  ],
  seah: [
    { key: "SEAH_LEVEL_1_NATIONAL", label: "L1 National" },
    { key: "SEAH_LEVEL_2_HQ",       label: "L2 HQ"       },
  ],
};

function WorkflowCard({ currentStepKey, displayName }: {
  currentStepKey: string;
  displayName: string;
}) {
  const steps = currentStepKey.startsWith("SEAH")
    ? WORKFLOW_STEPS.seah
    : WORKFLOW_STEPS.standard;
  const currentIdx = steps.findIndex((s) => s.key === currentStepKey);

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide border-l-[3px] border-blue-500 pl-3">Workflow</h2>
        <span className="text-xs text-gray-500 font-medium">{displayName}</span>
      </div>
      <div className="flex items-start">
        {steps.map((step, i) => {
          const done   = i < currentIdx;
          const active = i === currentIdx;
          return (
            <div key={step.key} className="flex items-start flex-1">
              {/* Connecting line before node */}
              {i > 0 && (
                <div className={`flex-1 h-0.5 mt-3 ${done || active ? "bg-blue-400" : "bg-gray-200"}`} />
              )}
              <div className="flex flex-col items-center shrink-0">
                {/* Node */}
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                  done   ? "bg-blue-500 text-white" :
                  active ? "bg-blue-600 text-white ring-2 ring-blue-200" :
                           "bg-gray-100 text-gray-400 border border-gray-200"
                }`}>
                  {done ? (
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  ) : i + 1}
                </div>
                {/* Label */}
                <span className={`text-xs font-medium mt-1.5 text-center whitespace-nowrap ${
                  active ? "text-blue-700 font-semibold" :
                  done   ? "text-blue-500"               : "text-gray-500"
                }`}>
                  {step.label}
                </span>
              </div>
              {/* Connecting line after last node */}
              {i === steps.length - 1 && (
                <div className="flex-1 h-0.5 mt-3 bg-gray-200" />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Open tasks card ───────────────────────────────────────────────────────────

function TasksCard({ tasks, user, onComplete, onAddTask }: {
  tasks: TicketTask[];
  user: ReturnType<typeof useAuth>["user"];
  onComplete: (task: TicketTask) => void;
  onAddTask?: () => void;
}) {
  const pending   = tasks.filter((t) => t.status === "PENDING");
  const done      = tasks.filter((t) => t.status === "DONE");

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <div className="flex items-center gap-2 mb-3">
        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide border-l-[3px] border-blue-500 pl-3">Tasks</h2>
        {pending.length > 0 && (
          <span className="bg-amber-100 text-amber-700 text-[10px] font-bold px-1.5 py-0.5 rounded-full">
            {pending.length} pending
          </span>
        )}
        {tasks.length > 0 && pending.length === 0 && (
          <span className="bg-green-100 text-green-700 text-[10px] font-bold px-1.5 py-0.5 rounded-full">
            All done
          </span>
        )}
        {onAddTask && (
          <button onClick={onAddTask}
            className="ml-auto text-[11px] text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1">
            + Task
          </button>
        )}
      </div>
      {tasks.length === 0 && (
        <p className="text-xs text-gray-400 italic">No tasks yet. Use <span className="font-mono bg-gray-100 px-1 rounded">#inspect @me</span> or <span className="font-mono bg-gray-100 px-1 rounded">#call</span> to assign one.</p>
      )}

      <div className="space-y-2">
        {pending.map((task) => {
          const typeInfo = getTaskTypeInfo(task.task_type);
          const isAssignedToMe = assigneeIsCurrentUser(task.assigned_to_user_id, user);
          const assigneeLabel = assigneeIsCurrentUser(task.assigned_to_user_id, user)
            ? "You"
            : task.assigned_to_user_id;
          const siteVisit = isSiteVisitTask(task.task_type);
          return (
            <div key={task.task_id} className="flex items-start gap-3 p-2.5 bg-amber-50 rounded-lg border border-amber-100">
              <TaskTypeIcon name={typeInfo?.icon ?? "ClipboardList"} size={15} strokeWidth={2} className="shrink-0 text-amber-600" />
              <div className="flex-1 min-w-0">
                <div className="text-xs font-medium text-gray-800">
                  {typeInfo?.label ?? task.task_type.replace(/_/g, " ")}
                </div>
                {task.description && (
                  <div className="text-xs text-gray-500 mt-0.5 truncate italic">&ldquo;{task.description}&rdquo;</div>
                )}
                <div className="text-[11px] text-gray-400 mt-1 flex items-center gap-1">
                  <span>→ {assigneeLabel}</span>
                  {task.due_date && <><span>·</span><span>Due {new Date(task.due_date).toLocaleDateString()}</span></>}
                </div>
              </div>
              {isAssignedToMe && (
                <button
                  type="button"
                  onClick={() => onComplete(task)}
                  className={
                    siteVisit
                      ? "shrink-0 text-[11px] text-white bg-amber-500 hover:bg-amber-600 rounded-lg px-2.5 py-1 transition font-medium"
                      : "shrink-0 text-[11px] text-green-700 bg-green-50 border border-green-200 rounded-lg px-2 py-1 hover:bg-green-100 transition font-medium"
                  }
                >
                  {!siteVisit && <Check size={11} strokeWidth={2.5} className="inline mr-0.5" />}
                  {siteVisit ? "Complete visit" : "Done"}
                </button>
              )}
            </div>
          );
        })}

        {done.length > 0 && (
          <div className="pt-1 border-t border-gray-100 space-y-1.5">
            {done.map((task) => {
              const typeInfo = getTaskTypeInfo(task.task_type);
              return (
                <div key={task.task_id} className="flex items-center gap-2 text-xs text-gray-400">
                  <Check size={12} strokeWidth={2.5} className="text-green-500 shrink-0" />
                  <span className="line-through">{typeInfo?.label ?? task.task_type.replace(/_/g, " ")}</span>
                  <span className="no-underline">→ {task.assigned_to_user_id}</span>
                  {task.completed_at && (
                    <span className="ml-auto">{new Date(task.completed_at).toLocaleDateString()}</span>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function TicketDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user, roleKeys, canSeeSeah, isAdmin, effectiveLang } = useAuth();

  // ── Core data ──────────────────────────────────────────────────────────
  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [sla, setSla]       = useState<SlaStatus | null>(null);
  const [tasks, setTasks]   = useState<TicketTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState<string | null>(null);

  // ── Thread ─────────────────────────────────────────────────────────────
  const [activeFilter, setActiveFilter] = useState<FilterChip>("all");
  const [noteText, setNoteText]         = useState("");
  const [submitting, setSubmitting]     = useState(false);
  const threadEndRef = useRef<HTMLDivElement>(null);
  const [filesRefreshKey, setFilesRefreshKey] = useState(0);
  const fieldVisitSubmitLock = useRef(false);
  const [complainantFiles, setComplainantFiles] = useState<TicketFile[]>([]);
  const [officerFiles, setOfficerFiles]         = useState<OfficerAttachment[]>([]);
  const [rosterIds, setRosterIds]               = useState<string[]>([]);
  const [actionNotice, setActionNotice]       = useState<ActionNoticeState | null>(null);
  const [escalationOpen, setEscalationOpen]   = useState(false);
  const [reassignOpen, setReassignOpen]         = useState(false);
  const [callReportOpen, setCallReportOpen]     = useState(false);

  // ── Top bar actions ────────────────────────────────────────────────────
  const [actLoading, setActLoading]     = useState(false);
  const [resolutionOpen, setResolutionOpen] = useState(false);
  const [showReply, setShowReply]       = useState(false);
  const [replyText, setReplyText]       = useState("");
  const [showAssign, setShowAssign]     = useState(false);
  const [officers, setOfficers]         = useState<OfficerBrief[]>([]);
  const [assignSelected, setAssignSelected] = useState("");
  const [savingAssign, setSavingAssign] = useState(false);
  const [showAssignTask, setShowAssignTask] = useState(false);
  const [grcHearingDate, setGrcHearingDate] = useState("");

  // ── Translation panel ──────────────────────────────────────────────────
  const PANEL_KEY = "grm_translation_panel_open";
  const [panelOpen, setPanelOpen] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(PANEL_KEY) === "true";
  });
  const togglePanel = () => {
    setPanelOpen((prev) => { const next = !prev; localStorage.setItem(PANEL_KEY, String(next)); return next; });
  };
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.key === "t" || e.key === "T") togglePanel();
      if (e.key === "Escape" && panelOpen) setPanelOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [panelOpen]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Vault reveal ───────────────────────────────────────────────────────
  const [revealModalOpen, setRevealModalOpen] = useState(false);
  const [revealSession, setRevealSession]     = useState<RevealSession | null>(null);

  // ── Data loading ───────────────────────────────────────────────────────
  const refreshFiles = useCallback(async () => {
    const [cf, of_] = await Promise.all([
      listTicketFiles(id).catch(() => [] as TicketFile[]),
      listOfficerAttachments(id).catch(() => [] as OfficerAttachment[]),
    ]);
    setComplainantFiles(cf);
    setOfficerFiles(of_);
  }, [id]);

  const load = useCallback(async () => {
    try {
      const [t, s, tk] = await Promise.all([
        getTicket(id),
        getSla(id),
        listTicketTasks(id).catch(() => [] as TicketTask[]),
      ]);
      setTicket(t);
      setSla(s);
      setTasks(tk);
      setAssignSelected(t.assigned_to_user_id ?? "");
      setFilesRefreshKey((k) => k + 1);
      await refreshFiles();
      markSeen(id).catch(() => {});
    } catch (e) {
      setError(formatUserFacingError(e).message);
    } finally {
      setLoading(false);
    }
  }, [id, refreshFiles]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    listOfficerRoster().then((r) => setRosterIds(r.map((o) => o.user_id))).catch(() => {});
  }, []);

  useEffect(() => {
    if (showAssign && officers.length === 0) {
      listOfficers().then(setOfficers).catch(() => {});
    }
  }, [showAssign]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Derived ────────────────────────────────────────────────────────────
  const currentUserId = canonicalUserId(user);
  const isAssigned    = isAdmin || !ticket?.assigned_to_user_id
    || assigneeIsCurrentUser(ticket.assigned_to_user_id, user);

  const status       = ticket?.status_code ?? "";
  const isClosed     = ["RESOLVED", "CLOSED"].includes(status);
  const isOpen       = status === "OPEN";
  const isEscalated  = status === "ESCALATED";
  const isGrcHearing = status === "GRC_HEARING_SCHEDULED";
  const stepKey      = ticket?.current_step?.step_key ?? "";
  const isGrcChair   = roleKeys.includes("grc_chair") || roleKeys.includes("super_admin");

  const slaBreached = (ticket?.sla_breached ?? false) || (sla?.breached ?? false);
  const slaHours    = sla?.remaining_hours ?? null;
  const timeLabel   = slaTimeLabel(slaHours, slaBreached, sla?.resolution_time_days);
  const slaCls      = slaColorCls(slaHours, slaBreached);

  const viewerIds         = useMemo(() => new Set((ticket?.viewers ?? []).map((v) => v.user_id)), [ticket]);
  const viewerTiers       = useMemo(() => {
    const m = new Map<string, "informed" | "observer">();
    (ticket?.viewers ?? []).forEach(v => m.set(v.user_id, v.tier as "informed" | "observer"));
    return m;
  }, [ticket]);

  const filteredEvents = useMemo(() => {
    if (!ticket) return [];
    switch (activeFilter) {
      case "all":         return ticket.events;
      case "mine":        return ticket.events.filter((e) => e.created_by_user_id === currentUserId);
      case "owner":       return ticket.events.filter((e) => e.created_by_user_id === ticket.assigned_to_user_id);
      case "supervisor":  return ticket.events.filter((e) => e.actor_role && AUTHORITY_ROLES.has(e.actor_role) && e.created_by_user_id !== ticket.assigned_to_user_id);
      case "observers":   return ticket.events.filter((e) => e.created_by_user_id && viewerIds.has(e.created_by_user_id));
      case "tasks":       return ticket.events.filter((e) => isThreadTaskEvent(e.event_type));
      case "complainant": return ticket.events.filter((e) => COMPLAINANT_EVENT_TYPES.has(e.event_type));
      case "system":      return ticket.events.filter((e) => SYSTEM_EVENT_TYPES.has(e.event_type));
      default:            return ticket.events;
    }
  }, [ticket, activeFilter, currentUserId, viewerIds]);

  const pendingTaskCount  = useMemo(() => tasks.filter((t) => t.status === "PENDING").length, [tasks]);
  const canManageViewers  = useMemo(() => !!ticket && ticket.assigned_to_user_id === currentUserId, [ticket, currentUserId]);
  const hasResolutionRecord = useMemo(() => {
    if (!ticket) return false;
    return ticket.events.some((event) => {
      if (event.event_type === "RESOLUTION_RECORDED") return true;
      if (event.event_type === "NOTE_ADDED") {
        const payload = (event.payload ?? {}) as Record<string, unknown>;
        if (payload.is_resolution_record === true) return true;
      }
      if (event.event_type !== "RESOLVED") return false;
      const payload = (event.payload ?? {}) as Record<string, unknown>;
      return typeof payload.resolution_category === "string" && payload.resolution_category.trim().length > 0;
    });
  }, [ticket]);

  const mentionParticipants = useMemo(() => {
    if (!ticket) return [];
    const ids = new Set<string>();
    if (ticket.assigned_to_user_id) ids.add(ticket.assigned_to_user_id);
    (ticket.viewers ?? []).forEach((v) => ids.add(v.user_id));
    ids.delete(currentUserId);
    const list = Array.from(ids).map((uid) => ({ user_id: uid, label: `@${uid}` }));
    list.unshift({ user_id: "all", label: "@all" });
    return list;
  }, [ticket, currentUserId]);

  const hasImages = useMemo(
    () => hasImageAttachment(complainantFiles, officerFiles),
    [complainantFiles, officerFiles],
  );

  const userCanSupervisorAssign = useMemo(
    () => !!ticket && canSupervisorAssign(roleKeys, ticket, isAdmin),
    [ticket, roleKeys, isAdmin],
  );
  const userCanAssign = useMemo(
    () => !!ticket && canAssignTicket(roleKeys, ticket, isAdmin, currentUserId),
    [ticket, roleKeys, isAdmin, currentUserId],
  );
  const reassignMode = useMemo(
    () => (ticket ? getReassignMode(roleKeys, ticket, currentUserId, isAdmin) : null),
    [ticket, roleKeys, currentUserId, isAdmin],
  );

  // ── Actions ────────────────────────────────────────────────────────────
  const ensureAcknowledged = useCallback(async () => {
    await ensureTicketAcknowledged(ticket, isAssigned, id, load);
  }, [ticket, isAssigned, id, load]);

  const handleSimpleAction = useCallback(async (
    action_type: string,
    extra?: Record<string, string>,
  ) => {
    setActLoading(true);
    setActionNotice(null);
    try {
      if (action_type !== "ACKNOWLEDGE") await ensureAcknowledged();
      await performAction(id, { action_type, ...extra });
      await load();
    } catch (e) {
      console.error("Action failed", e);
      setActionNotice(formatUserFacingError(e));
    } finally {
      setActLoading(false);
    }
  }, [id, load, ensureAcknowledged]);

  const openEscalationFlow = useCallback(() => {
    if (!hasImages) {
      setActionNotice({ message: MSG_IMAGE_BEFORE_ESCALATE, kind: "validation" });
      return;
    }
    setEscalationOpen(true);
  }, [hasImages]);

  const submitEscalation = useCallback(async (data: {
    escalationDate: string;
    personsInvolved: string[];
    notes: string;
  }) => {
    setActLoading(true);
    setActionNotice(null);
    try {
      await ensureAcknowledged();
      await performAction(id, {
        action_type: "ESCALATE",
        escalation_date: data.escalationDate,
        persons_involved: data.personsInvolved,
        escalation_notes: data.notes,
      });
      setEscalationOpen(false);
      await load();
    } catch (e) {
      console.error("Escalation failed", e);
      setActionNotice(formatUserFacingError(e));
      throw e;
    } finally {
      setActLoading(false);
    }
  }, [id, load, ensureAcknowledged]);

  const openResolveFlow = useCallback(() => {
    if (!hasImages) {
      setActionNotice({ message: MSG_IMAGE_BEFORE_RESOLVE, kind: "validation" });
      return;
    }
    setResolutionOpen(true);
  }, [hasImages]);

  const submitResolve = useCallback(async (category: ResolutionCategoryCode, note: string) => {
    setActLoading(true);
    setActionNotice(null);
    try {
      await ensureAcknowledged();
      await performAction(id, {
        action_type: "RESOLVE",
        resolution_category: category,
        note,
      });
      setResolutionOpen(false);
      await load();
    } catch (e) {
      console.error("Resolve failed", e);
      setActionNotice(formatUserFacingError(e));
    } finally {
      setActLoading(false);
    }
  }, [id, load, ensureAcknowledged]);

  const sendReply = useCallback(async () => {
    if (!replyText.trim()) return;
    setActLoading(true);
    setActionNotice(null);
    try {
      await ensureAcknowledged();
      await replyToComplainant(id, replyText);
      setReplyText("");
      setShowReply(false);
      await load();
    } catch (e) {
      console.error("Reply failed", e);
      setActionNotice(formatUserFacingError(e));
    } finally {
      setActLoading(false);
    }
  }, [replyText, id, load, ensureAcknowledged]);

  const handleAssign = useCallback(async () => {
    if (!assignSelected || assignSelected === ticket?.assigned_to_user_id) return;
    if (!userCanAssign) {
      setActionNotice({ message: MSG_SUPERVISOR_ONLY_ASSIGN, kind: "validation" });
      return;
    }
    setSavingAssign(true);
    setActionNotice(null);
    try {
      await patchTicket(id, { assign_to_user_id: assignSelected });
      setShowAssign(false);
      await load();
    } catch (e) {
      console.error("Assign failed", e);
      setActionNotice(formatUserFacingError(e));
    } finally {
      setSavingAssign(false);
    }
  }, [assignSelected, ticket?.assigned_to_user_id, userCanAssign, id, load]);

  const handleNote = useCallback(async () => {
    if (!noteText.trim() || submitting) return;
    setSubmitting(true);
    const text = noteText.trim();
    setNoteText("");
    try {
      await ensureAcknowledged();
      await performAction(id, { action_type: "NOTE", note: text });
      await load();
      threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
    } catch (e) {
      console.error("Note failed", e);
      setNoteText(text);
    } finally {
      setSubmitting(false);
    }
  }, [noteText, submitting, id, load, ensureAcknowledged]);

  // ── Report mode + field visit + attach ─────────────────────────────────
  const [fieldReportOpen, setFieldReportOpen] = useState(false);
  const [fieldReportLinkedTask, setFieldReportLinkedTask] = useState<TicketTask | null>(null);
  const [fieldReportSubmitting, setFieldReportSubmitting] = useState(false);
  const [attachUploading, setAttachUploading] = useState(false);

  const openFieldReport = useCallback((linkedTask?: TicketTask | null) => {
    setFieldReportLinkedTask(linkedTask ?? null);
    setFieldReportOpen(true);
    requestAnimationFrame(() => {
      threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
    });
  }, []);

  const closeFieldReport = useCallback(() => {
    setFieldReportOpen(false);
    setFieldReportLinkedTask(null);
  }, []);

  const handleCompleteTask = useCallback(async (task: TicketTask) => {
    if (isSiteVisitTask(task.task_type) && task.status === "PENDING") {
      openFieldReport(task);
      return;
    }
    try {
      await completeTask(id, task.task_id);
      await load();
    } catch (e) {
      console.error("Complete task failed", e);
      setActionNotice(formatUserFacingError(e, "task"));
    }
  }, [id, load, openFieldReport]);

  const submitFieldReportForm = useCallback(async (data: FieldVisitFormData) => {
    if (fieldVisitSubmitLock.current) return;
    fieldVisitSubmitLock.current = true;
    setFieldReportSubmitting(true);
    try {
      await submitStructuredFieldReport({
        ticketId: id,
        data,
        linkedTask: fieldReportLinkedTask,
        ensureAcknowledged,
      });
      closeFieldReport();
      await load();
      threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
    } catch (e) {
      console.error("Field report failed", e);
      setActionNotice(formatUserFacingError(e, "field_report"));
      throw e;
    } finally {
      fieldVisitSubmitLock.current = false;
      setFieldReportSubmitting(false);
    }
  }, [id, fieldReportLinkedTask, load, ensureAcknowledged, closeFieldReport]);

  const handleAttachFile = useCallback(async (file: File) => {
    setAttachUploading(true);
    setActionNotice(null);
    try {
      await ensureAcknowledged();
      await uploadOfficerAttachment(id, file, "");
      await refreshFiles();
      await load();
    } catch (e) {
      console.error("Upload failed", e);
      setActionNotice(formatUserFacingError(e, "upload"));
    } finally {
      setAttachUploading(false);
    }
  }, [ensureAcknowledged, id, load, refreshFiles]);

  const submitReassignment = useCallback(async (reasonCode: ReassignmentReasonCode, notes: string) => {
    setActLoading(true);
    setActionNotice(null);
    try {
      await performAction(id, {
        action_type: "REASSIGNMENT_REQUESTED",
        reassignment_reason_code: reasonCode,
        reassignment_notes: notes,
      });
      setReassignOpen(false);
      await load();
    } catch (e) {
      setActionNotice(formatUserFacingError(e));
      throw e;
    } finally {
      setActLoading(false);
    }
  }, [id, load]);

  const submitCallReport = useCallback(async (data: CallReportFormData) => {
    setActLoading(true);
    setActionNotice(null);
    try {
      await ensureAcknowledged();
      await performAction(id, {
        action_type: "NOTE",
        note: formatCallReportNote(data),
        is_call_report: true,
      });
      setCallReportOpen(false);
      await load();
    } catch (e) {
      setActionNotice(formatUserFacingError(e));
      throw e;
    } finally {
      setActLoading(false);
    }
  }, [id, load, ensureAcknowledged]);

  const handleHashCommand = useCallback(async (cmd: HashCommand) => {
    if (cmd.kind === "call_report") {
      setCallReportOpen(true);
      return;
    }
    if (cmd.kind === "reassign_request" && reassignMode === "supervisor") {
      setReassignOpen(true);
      return;
    }
    if (cmd.kind === "action" && cmd.action === "ESCALATE") {
      openEscalationFlow();
      return;
    }
    if (cmd.kind === "action" && cmd.action) {
      await handleSimpleAction(cmd.action);
      return;
    }
    if (cmd.kind === "task" && cmd.taskKey) {
      // instant self-assign task
      try {
        await createTask(id, { task_type: cmd.taskKey, assigned_to_user_id: currentUserId });
        await load();
      } catch (e) { console.error("Create task failed", e); }
      return;
    }
    if (cmd.kind === "assign" && !userCanAssign) {
      setActionNotice({ message: MSG_SUPERVISOR_ONLY_ASSIGN, kind: "validation" });
    }
    // #assign / peer #reassign handled inline in ComposeBar (text becomes "#assign @…")
  }, [id, currentUserId, load, openFieldReport, openEscalationFlow, handleSimpleAction, userCanAssign, reassignMode]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleNoteOrReport = useCallback(async () => {
    const text = noteText.trim();
    if (!text || submitting) return;
    setSubmitting(true);

    const assignMatch = text.match(/^#assign\s+@([A-Za-z0-9][A-Za-z0-9._@-]*)/);
    const inspectAssignee = parseInspectAssignCommand(text);

    setNoteText("");
    try {
      if (inspectAssignee !== undefined) {
        const assignee = inspectAssignee ?? currentUserId;
        await createTask(id, {
          task_type: "SITE_VISIT",
          assigned_to_user_id: assignee,
        });
      } else if (assignMatch) {
        if (!userCanAssign) {
          setActionNotice({ message: MSG_SUPERVISOR_ONLY_ASSIGN, kind: "validation" });
          setNoteText(text);
          return;
        }
        await patchTicket(id, { assign_to_user_id: assignMatch[1] });
      } else {
        await ensureAcknowledged();
        await performAction(id, { action_type: "NOTE", note: text });
      }
      await load();
      threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
    } catch (e) {
      console.error("Submit failed", e);
      setNoteText(text);
      setActionNotice(formatUserFacingError(e));
    } finally {
      setSubmitting(false);
    }
  }, [noteText, submitting, id, load, ensureAcknowledged, currentUserId, userCanAssign]);

  // ── Render ─────────────────────────────────────────────────────────────
  if (loading) return (
    <div className="flex items-center justify-center h-full min-h-[200px]">
      <div className="text-sm text-gray-400 animate-pulse">Loading…</div>
    </div>
  );
  if (error) return (
    <div className="flex flex-col items-center gap-3 py-16 text-sm text-gray-500">
      <IconWarning size={32} strokeWidth={1.5} className="text-amber-400" /><span>{error}</span>
      <button onClick={load} className="text-blue-600">Retry</button>
    </div>
  );
  if (!ticket) return null;
  if (ticket.is_seah && !canSeeSeah) return <div className="p-8 text-red-500 text-sm">Access denied.</div>;

  const btnBase = "px-3 py-1.5 rounded-lg text-sm font-medium transition disabled:opacity-50";
  const showTranslations = effectiveLang !== "ne";

  return (
    <div className="flex flex-col h-full bg-gray-50">

      {/* ── Compact top bar ──────────────────────────────────────────── */}
      <div className="flex-shrink-0 bg-white border-b border-gray-200 px-6">

        {/* Row 1: identity + primary action buttons */}
        <div className="flex items-center gap-2.5 py-2.5 min-w-0">
          <button
            onClick={() => router.back()}
            className="text-sm text-gray-400 hover:text-gray-600 shrink-0"
          >
            ← Back
          </button>
          <div className="w-px h-4 bg-gray-200 shrink-0" />
          <h1 className="text-base font-semibold text-gray-900 shrink-0">{ticket.grievance_id}</h1>
          {ticket.is_seah && <SeahBadge />}
          <StatusBadge code={ticket.status_code} />
          <PriorityBadge priority={ticket.priority} />

          {/* Primary actions — right side of row 1 */}
          {isAssigned && !isClosed && (
            <div className="ml-auto flex items-center gap-2 shrink-0">
              {(isOpen || isEscalated) && (
                <button
                  onClick={() => handleSimpleAction("ACKNOWLEDGE")}
                  disabled={actLoading || ticket.classification_officer_validation_required}
                  title={
                    ticket.classification_officer_validation_required
                      ? "Confirm summary and categories in Original Grievance first"
                      : undefined
                  }
                  className={`${btnBase} inline-flex items-center gap-1.5 bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50`}
                >
                  <IconAcknowledge size={15} strokeWidth={2} />
                  Acknowledge
                </button>
              )}
              {!isOpen && !isEscalated && (
                <>
                  <button onClick={openEscalationFlow} disabled={actLoading}
                    className={`${btnBase} inline-flex items-center gap-1.5 border border-amber-300 text-amber-700 bg-amber-50 hover:bg-amber-100`}>
                    <IconEscalateAction size={15} strokeWidth={2} />
                    Escalate
                  </button>
                  <button onClick={openResolveFlow} disabled={actLoading}
                    className={`${btnBase} inline-flex items-center gap-1.5 bg-green-600 text-white hover:bg-green-700`}>
                    <IconResolve size={15} strokeWidth={2} />
                    Resolve
                  </button>
                </>
              )}
              {isGrcChair && stepKey === "LEVEL_3_GRC" && !isGrcHearing && (
                <>
                  <input type="date" value={grcHearingDate} onChange={(e) => setGrcHearingDate(e.target.value)}
                    className="text-sm border border-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-purple-400"
                    placeholder="Hearing date" />
                  <button onClick={() => handleSimpleAction("GRC_CONVENE", { grc_hearing_date: grcHearingDate })} disabled={actLoading || !grcHearingDate}
                    className={`${btnBase} inline-flex items-center gap-1.5 bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-40`}>
                    <IconGrcConvene size={15} strokeWidth={2} />
                    Convene GRC
                  </button>
                </>
              )}
            </div>
          )}
        </div>

        {/* Row 2: meta strip + secondary action toggles */}
        <div className="flex items-center gap-x-2 pb-2.5 text-xs text-gray-500 flex-wrap min-w-0">
          <span className="shrink-0">{ticket.organization_id}</span>
          {ticket.location_code && <><span className="text-gray-300">·</span><span className="shrink-0">{ticket.location_code}</span></>}
          {ticket.project_code  && <><span className="text-gray-300">·</span><span className="shrink-0">{ticket.project_code}</span></>}
          <span className="text-gray-300">·</span>
          <span className="shrink-0">Created {new Date(ticket.created_at).toLocaleDateString()}</span>
          {timeLabel && (
            <>
              <span className="text-gray-300">·</span>
              <span className={`shrink-0 px-1.5 py-0.5 rounded text-[11px] font-medium ${slaCls}`}>
                {timeLabel}
              </span>
            </>
          )}
          {ticket.current_step && (
            <>
              <span className="text-gray-300">·</span>
              <span className="shrink-0 text-gray-600 font-medium">{ticket.current_step.display_name}</span>
            </>
          )}

          {/* Not assigned warning */}
          {!isAssigned && (
            <>
              <span className="text-gray-300">·</span>
              <span className="shrink-0 text-amber-600 text-[11px] font-medium inline-flex items-center gap-1">
                <IconWarning size={11} strokeWidth={2} />
                Assigned to {ticket.assigned_to_user_id}
              </span>
            </>
          )}

          {/* Reply owner indicator (spec 12) */}
          {ticket.complainant_reply_owner_id && ticket.complainant_reply_owner_id !== ticket.assigned_to_user_id && (
            <>
              <span className="text-gray-300">·</span>
              <span className="shrink-0 text-blue-500 text-[11px] inline-flex items-center gap-1" title="Officer who replies to the complainant">
                <IconReply size={11} strokeWidth={2} />
                Reply: {ticket.complainant_reply_owner_id === currentUserId ? "You" : ticket.complainant_reply_owner_id}
              </span>
            </>
          )}

          {/* Secondary toggles — far right */}
          <div className="ml-auto flex items-center gap-1.5 shrink-0">
            {isAssigned && (
              <>
                <button
                  onClick={() => { setShowReply((v) => !v); setShowAssign(false); }}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition ${
                    showReply
                      ? "bg-blue-100 border-blue-300 text-blue-700"
                      : "border-gray-200 text-gray-600 hover:border-gray-300 bg-white"
                  }`}
                >
                  <IconReply size={12} strokeWidth={2} className="inline mr-1" />
                  Reply
                </button>
                <button
                  onClick={() => setShowAssignTask(true)}
                  className="px-2.5 py-1 rounded-lg text-xs font-medium border border-gray-200 text-gray-600 hover:border-gray-300 bg-white transition inline-flex items-center gap-1"
                >
                  <IconTask size={12} strokeWidth={2} />
                  Task
                </button>
                {userCanAssign && (
                <button
                  onClick={() => { setShowAssign((v) => !v); setShowReply(false); }}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition inline-flex items-center gap-1 ${
                    showAssign
                      ? "bg-blue-100 border-blue-300 text-blue-700"
                      : "border-gray-200 text-gray-600 hover:border-gray-300 bg-white"
                  }`}
                >
                  <IconAssign size={12} strokeWidth={2} />
                  {reassignMode === "peer" ? "Reassign" : "Assign"}
                </button>
                )}
              </>
            )}
            {showTranslations && (
              <button
                onClick={togglePanel}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition ${
                  panelOpen
                    ? "bg-blue-100 border-blue-300 text-blue-700"
                    : "border-gray-200 text-gray-500 hover:border-blue-300 bg-white"
                }`}
              >
                <IconTranslations size={12} strokeWidth={2} className="inline mr-1" />
                Translations
              </button>
            )}
          </div>
        </div>

        {/* Expandable: Reply panel */}
        {showReply && (
          <div className="border-t border-gray-100 py-3 space-y-2">
            <textarea
              value={replyText}
              onChange={(e) => setReplyText(e.target.value)}
              rows={2}
              placeholder="Message sent via chatbot (SMS fallback if session expired)…"
              className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-1 focus:ring-blue-400"
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => { setShowReply(false); setReplyText(""); }}
                className="text-xs text-gray-500 hover:text-gray-700 px-3 py-1.5">
                Cancel
              </button>
              <button onClick={sendReply} disabled={!replyText.trim() || actLoading}
                className="text-xs bg-blue-600 text-white rounded-lg px-3 py-1.5 hover:bg-blue-700 disabled:opacity-50 transition font-medium">
                {actLoading ? "Sending…" : "→ Send Reply"}
              </button>
            </div>
          </div>
        )}

        {/* Expandable: Assign officer panel */}
        {showAssign && (
          <div className="border-t border-gray-100 py-3 flex items-center gap-2 flex-wrap">
            <span className="text-xs text-gray-500 shrink-0">Assign to:</span>
            <select
              value={assignSelected}
              onChange={(e) => setAssignSelected(e.target.value)}
              className="flex-1 min-w-[200px] text-sm border border-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
            >
              <option value="">— Unassigned —</option>
              {officers.map((o) => (
                <option key={o.user_id} value={o.user_id}>
                  {o.user_id}{o.role_keys.length > 0 ? ` (${o.role_keys[0].replace(/_/g, " ")})` : ""}
                </option>
              ))}
            </select>
            <button
              onClick={handleAssign}
              disabled={savingAssign || !assignSelected || assignSelected === ticket.assigned_to_user_id}
              className="text-xs bg-blue-600 text-white rounded-lg px-3 py-1.5 hover:bg-blue-700 disabled:opacity-50 transition font-medium"
            >
              {savingAssign ? "Saving…" : "Save"}
            </button>
            <button onClick={() => setShowAssign(false)}
              className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1.5">
              Cancel
            </button>
          </div>
        )}
      </div>

      <ActionNotice
        notice={actionNotice}
        onDismiss={() => setActionNotice(null)}
        className="mx-6 mt-2"
      />

      {isClosed && !hasResolutionRecord && (
        <div className="mx-4 mt-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
          <p className="font-medium">Resolution record missing for this closed ticket.</p>
          <p className="mt-1 text-red-800">
            Closure summary generation is blocked until resolution details are saved.
          </p>
          <div className="mt-3">
            <button
              type="button"
              onClick={openResolveFlow}
              disabled={!isAssigned}
              className="rounded border border-red-300 bg-white px-3 py-1.5 text-red-700 hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Add resolution details
            </button>
          </div>
        </div>
      )}
      {isClosed && hasResolutionRecord && (
        <div className="mx-4 mt-3 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-900">
          <p className="font-medium">Resolution details are saved.</p>
          <p className="mt-1 text-green-800">You can now open the case closure summary.</p>
          <div className="mt-3">
            <button
              type="button"
              onClick={() => router.push(`/tickets/${id}/closure`)}
              className="rounded border border-green-300 bg-white px-3 py-1.5 text-green-700 hover:bg-green-100"
            >
              Open closure summary
            </button>
          </div>
        </div>
      )}

      {/* ── Main: thread (2/5) + info (3/5) ─────────────────────────── */}
      <div className="flex-1 min-h-0 grid grid-cols-5 gap-4 p-4">

        {/* Thread column */}
        <div className="col-span-2 bg-white rounded-xl border border-gray-200 flex flex-col min-h-0 overflow-hidden">
          <div className="flex-shrink-0 border-b border-gray-200">
            <FilterChips
              events={ticket.events}
              currentUserId={currentUserId}
              assignedToUserId={ticket.assigned_to_user_id ?? null}
              viewerIds={viewerIds}
              active={activeFilter}
              pendingTaskCount={pendingTaskCount}
              onChange={setActiveFilter}
            />
            <ViewersBar
              viewers={ticket.viewers ?? []}
              canManage={canManageViewers}
              isActor={ticket.assigned_to_user_id === currentUserId}
              ticketId={ticket.ticket_id}
              onChanged={load}
            />
          </div>

          <div className="flex-1 overflow-y-auto py-2">
            {filteredEvents.length === 0 ? (
              <div className="flex justify-center py-8 text-xs text-gray-400">No messages in this view</div>
            ) : (
              filteredEvents
                .filter((e: TicketEvent) => !NOTIFICATION_ONLY_EVENT_TYPES.has(e.event_type))
                .filter(
                  (e: TicketEvent) =>
                    !isThreadTaskEvent(e.event_type) ||
                    shouldRenderTaskCardInThread(e, ticket.events, tasks),
                )
                .map((event: TicketEvent) => {
                  const isMine = event.created_by_user_id === currentUserId;
                  if (SYSTEM_EVENT_TYPES.has(event.event_type))
                    return <SystemPill key={event.event_id} event={event} />;
                  if (isThreadTaskEvent(event.event_type))
                    return (
                      <TaskCard
                        key={event.event_id}
                        event={event}
                        tasks={tasks}
                        currentUserId={currentUserId}
                        ticketId={ticket.ticket_id}
                        onComplete={handleCompleteTask}
                      />
                    );
                  return <NoteBubble key={event.event_id} event={event} isMine={isMine} assignedToUserId={ticket.assigned_to_user_id} viewerIds={viewerIds} viewerTiers={viewerTiers} />;
                })
            )}
            <div ref={threadEndRef} />
          </div>

          <div className={`flex-shrink-0 border-t ${fieldReportOpen || escalationOpen ? "border-amber-200" : "border-gray-100"}`}>
            <EscalationFormCard
              open={escalationOpen}
              currentUserId={currentUserId}
              rosterIds={rosterIds}
              submitting={actLoading}
              onClose={() => setEscalationOpen(false)}
              onSubmit={submitEscalation}
            />
            <FieldReportComposeCard
              open={fieldReportOpen}
              defaultLocation={ticket.grievance_location}
              completeVisit={!!fieldReportLinkedTask}
              submitting={fieldReportSubmitting}
              onClose={closeFieldReport}
              onSubmit={submitFieldReportForm}
            />
            <ReassignmentRequestCard
              open={reassignOpen}
              ticket={ticket}
              submitting={actLoading}
              onClose={() => setReassignOpen(false)}
              onSubmit={submitReassignment}
            />
            <CallReportComposeCard
              open={callReportOpen}
              submitting={actLoading}
              onClose={() => setCallReportOpen(false)}
              onSubmit={submitCallReport}
            />
            <ComposeBar
              value={noteText}
              onChange={setNoteText}
              onSubmit={handleNoteOrReport}
              onHashCommand={handleHashCommand}
              onFileSelected={handleAttachFile}
              attachUploading={attachUploading}
              fieldReportOpen={fieldReportOpen}
              canAssign={userCanSupervisorAssign}
              canReassign={!!reassignMode}
              reassignMode={reassignMode}
              disabled={submitting || fieldReportSubmitting}
              participants={mentionParticipants}
            />
          </div>
        </div>

        {/* ── Right info column — Option C layout ──────────────── */}
        <div className="col-span-3 overflow-y-auto space-y-3 pb-4">

          {/* Row 1: Workflow + Tasks side by side (both are "case state" cards) */}
          <div className="grid grid-cols-2 gap-3">
            {ticket.current_step ? (
              <WorkflowCard
                currentStepKey={ticket.current_step.step_key}
                displayName={ticket.current_step.display_name}
              />
            ) : (
              <div className="bg-white rounded-xl border border-gray-200 p-4 flex items-center justify-center text-xs text-gray-400 italic">
                No workflow assigned
              </div>
            )}
            <TasksCard
              tasks={tasks}
              user={user}
              onComplete={handleCompleteTask}
              onAddTask={() => setShowAssignTask(true)}
            />
          </div>

          {/* Row 2: Original Grievance — full width (TP-14 classification) */}
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide border-l-[3px] border-blue-500 pl-3 mb-3">
              Original Grievance
            </h2>
            <ClassificationGrievancePanel ticket={ticket} onUpdated={load} />
          </div>

          {/* Row 3: Field Reports — full width (officer-written, always visible) */}
          <FieldReportsCard ticket={ticket} />

          {/* Row 4: AI Findings — full width (supervisors+ only) */}
          <FindingsCard ticket={ticket} roleKeys={roleKeys} onRefresh={load} />

          {/* Row 5: Complainant + Attachments side by side */}
          <div className="grid grid-cols-2 gap-3">
            <ComplainantCard ticket={ticket} onRevealOriginal={() => setRevealModalOpen(true)} onComplainantUpdated={load} />
            <FilesPanel
              ticketId={ticket.ticket_id}
              refreshKey={filesRefreshKey}
              onBeforeDownload={ensureAcknowledged}
              isAssigned={isAssigned}
              onUpload={load}
            />
          </div>
        </div>
      </div>

      {/* ── Translation overlay (fixed right panel, T to toggle) ─────── */}
      {panelOpen && (
        <div className="fixed right-0 top-0 bottom-0 w-80 z-40 shadow-2xl">
          <TranslationPanel
            events={ticket.events}
            onClose={() => { setPanelOpen(false); localStorage.setItem(PANEL_KEY, "false"); }}
          />
        </div>
      )}

      {/* ── Vault reveal ──────────────────────────────────────────────── */}
      {revealModalOpen && (
        <RevealModal
          ticketId={ticket.ticket_id}
          isSeah={ticket.is_seah}
          onClose={() => setRevealModalOpen(false)}
          onGranted={(session) => { setRevealModalOpen(false); setRevealSession(session); }}
        />
      )}
      {revealSession && (
        <RevealOverlay
          session={revealSession}
          ticketId={ticket.ticket_id}
          onClose={() => setRevealSession(null)}
        />
      )}

      {/* ── Assign task sheet ──────────────────────────────────────────── */}
      {showAssignTask && (
        <AssignTaskSheet
          ticketId={ticket.ticket_id}
          variant="modal"
          onClose={() => setShowAssignTask(false)}
          onAssigned={() => { setShowAssignTask(false); load(); }}
        />
      )}

      <ResolutionSheet
        open={resolutionOpen}
        onClose={() => setResolutionOpen(false)}
        onSubmit={submitResolve}
        submitting={actLoading}
      />

    </div>
  );
}
