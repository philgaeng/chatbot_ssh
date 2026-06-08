"use client";

/**
 * /m/tickets/[id] — Mobile thread screen.
 *
 * Layout (WhatsApp-style):
 *   sticky header (back · title · SLA · stepper · ⋮)
 *   filter chips
 *   scrollable full-width thread
 *   fixed bottom: PrimaryCtaBar + ComposeBar
 *
 * The ⋮ button opens an info-menu bottom sheet:
 *   Tasks · Original Grievance · Field Reports · Complainant Info · Attachments
 * Each item slides up its own bottom sheet.
 * Nothing is shown in a side-by-side column — thread always takes full width.
 */

import React, { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  getTicket, getSla, performAction, markSeen, listTicketTasks, completeTask, createTask, patchTicket,
  listTicketFiles, listOfficerAttachments, getFileDownloadUrl, getOfficerAttachmentUrl, uploadOfficerAttachment,
  listOfficerRoster, getGrievancePii,
  type TicketDetail, type TicketEvent, type SlaStatus, type TicketTask,
  type TicketFile, type OfficerAttachment, type GrievancePii, type RevealSession,
} from "@/lib/api";
import { ComplainantEditForm } from "@/components/tickets/ComplainantEditForm";
import { RevealModal, RevealOverlay } from "@/components/ui/VaultReveal";
import { useAuth } from "@/app/providers/AuthProvider";
import { assigneeIsCurrentUser, canonicalUserId } from "@/lib/auth/token-storage";
import {
  SYSTEM_EVENT_TYPES, NOTIFICATION_ONLY_EVENT_TYPES, isThreadTaskEvent,
  COMPLAINANT_EVENT_TYPES, AUTHORITY_ROLES, type HashCommand,
} from "@/lib/mobile-constants";
import { hasImageAttachment } from "@/lib/attachments";
import { canAssignTicket, canRequestReassignment } from "@/lib/officer-permissions";
import {
  AlertTriangle, ArrowUpCircle, Flag, Lock, ClipboardList, CheckCircle2,
  MoreVertical, User, FileText, Paperclip, ChevronLeft, Download, FileIcon,
  ClipboardCheck, BookOpen, X,
} from "lucide-react";

import { NoteBubble }                        from "@/components/thread/NoteBubble";
import { ResolutionSheet }                   from "@/components/ResolutionSheet";
import type { ResolutionCategoryCode }       from "@/lib/resolution";
import { SystemPill }                         from "@/components/thread/SystemPill";
import { TaskCard, AssignTaskSheet }          from "@/components/thread/TaskCard";
import { FilterChips, type FilterChip }       from "@/components/thread/FilterChips";
import { ViewersBar }                         from "@/components/thread/ViewersBar";
import { ComposeBar }                         from "@/components/thread/ComposeBar";
import { FieldReportComposeCard }             from "@/components/thread/FieldReportComposeCard";
import { GrievanceThreadCard }                from "@/components/thread/GrievanceThreadCard";
import { EscalationFormCard }                 from "@/components/thread/EscalationFormCard";
import { CallReportComposeCard }              from "@/components/thread/CallReportComposeCard";
import { ReassignmentRequestCard, type ReassignmentReasonCode } from "@/components/thread/ReassignmentRequestCard";
import { AttachmentListSection }              from "@/components/AttachmentListSection";
import {
  formatCallReportNote, isSiteVisitTask, parseInspectAssignCommand, type FieldVisitFormData, type CallReportFormData,
} from "@/lib/field-visit";
import { submitStructuredFieldReport } from "@/lib/submit-field-report";
import { ActionNotice } from "@/components/ActionNotice";
import {
  formatUserFacingError,
  MSG_IMAGE_BEFORE_ESCALATE,
  MSG_IMAGE_BEFORE_RESOLVE,
  MSG_SUPERVISOR_ONLY_ASSIGN,
  MSG_SUPERVISOR_ONLY_FIELD_REPORT,
  type ActionNoticeState,
} from "@/lib/user-messages";
import { ensureTicketAcknowledged } from "@/lib/ticket-ack";
import { shouldRenderTaskCardInThread } from "@/lib/thread-tasks";
import { SlaSubHeader, WorkflowMiniStepper }  from "@/components/thread/SlaSubHeader";

// ── Reusable bottom sheet shell ───────────────────────────────────────────────
// All info panels use this — 80 % height, rounded top, drag handle, scrollable.

function BottomSheet({
  title,
  onClose,
  children,
  badge,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  badge?: string | number;
}) {
  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end" onClick={onClose}>
      {/* Scrim */}
      <div className="absolute inset-0 bg-black/30" />
      <div
        className="relative bg-white rounded-t-2xl shadow-2xl flex flex-col"
        style={{ maxHeight: "82dvh" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Drag handle */}
        <div className="flex-shrink-0 pt-3 pb-1 flex justify-center">
          <div className="w-10 h-1 bg-gray-300 rounded-full" />
        </div>
        {/* Sheet header */}
        <div className="flex-shrink-0 flex items-center justify-between px-5 py-2.5 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-gray-900">{title}</h3>
            {badge !== undefined && badge !== 0 && (
              <span className="bg-blue-100 text-blue-700 text-xs font-bold px-2 py-0.5 rounded-full">
                {badge}
              </span>
            )}
          </div>
          <button onClick={onClose} className="p-1.5 text-gray-400 active:bg-gray-100 rounded-lg">
            <X size={18} strokeWidth={2} />
          </button>
        </div>
        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto">
          {children}
        </div>
      </div>
    </div>
  );
}

// ── Info menu bottom sheet (⋮ press) ──────────────────────────────────────────

type InfoPanel = "tasks" | "grievance" | "field_reports" | "complainant" | "attachments";

function InfoMenuSheet({
  ticket,
  tasks,
  onSelect,
  onClose,
}: {
  ticket: TicketDetail;
  tasks: TicketTask[];
  onSelect: (panel: InfoPanel) => void;
  onClose: () => void;
}) {
  const pendingTaskCount   = tasks.filter((t) => t.status === "PENDING").length;
  const fieldReportCount   = (ticket.events ?? []).filter(
    (e) => e.payload && (e.payload as Record<string, unknown>).is_field_report
  ).length;
  const items: Array<{ key: InfoPanel; label: string; Icon: React.ElementType; badge?: number }> = [
    { key: "tasks",        label: "Tasks",               Icon: ClipboardCheck, badge: pendingTaskCount || undefined },
    { key: "grievance",    label: "Original Grievance",  Icon: BookOpen },
    { key: "field_reports",label: "Field Reports",       Icon: Flag,           badge: fieldReportCount || undefined },
    { key: "complainant",  label: "Complainant Info",    Icon: User },
    { key: "attachments",  label: "Attachments",         Icon: Paperclip },
  ];

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30" />
      <div
        className="relative bg-white rounded-t-2xl shadow-2xl pb-safe-bottom"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Drag handle */}
        <div className="pt-3 pb-1 flex justify-center">
          <div className="w-10 h-1 bg-gray-300 rounded-full" />
        </div>
        <div className="py-2">
          {items.map(({ key, label, Icon, badge }) => (
            <button
              key={key}
              onClick={() => { onSelect(key); onClose(); }}
              className="w-full flex items-center gap-4 px-6 py-4 active:bg-gray-50 text-left"
            >
              <Icon size={22} strokeWidth={1.8} className="text-gray-500 shrink-0" />
              <span className="flex-1 text-base text-gray-800">{label}</span>
              {badge !== undefined && (
                <span className="bg-blue-100 text-blue-700 text-xs font-bold px-2 py-0.5 rounded-full">
                  {badge}
                </span>
              )}
            </button>
          ))}
        </div>
        <div className="border-t border-gray-100 px-6 py-4">
          <button onClick={onClose} className="w-full text-sm font-medium text-gray-500 text-center">
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Tasks sheet ───────────────────────────────────────────────────────────────

function TasksSheet({
  ticket,
  tasks,
  currentUserId,
  onClose,
  onComplete,
  onAssignNew,
}: {
  ticket: TicketDetail;
  tasks: TicketTask[];
  currentUserId: string;
  onClose: () => void;
  onComplete: (task: TicketTask) => void;
  onAssignNew: () => void;
}) {
  const pending   = tasks.filter((t) => t.status === "PENDING");
  const completed = tasks.filter((t) => t.status === "DONE");

  function TaskRow({ task }: { task: TicketTask }) {
    const isDone = task.status === "DONE";
    const isMine = task.assigned_to_user_id === currentUserId;
    return (
      <div className={`px-5 py-4 border-b border-gray-50 ${isDone ? "opacity-50" : ""}`}>
        <div className="flex items-start gap-3">
          <button
            type="button"
            disabled={isDone || !isMine}
            onClick={() => !isDone && isMine && onComplete(task)}
            className={`mt-0.5 w-5 h-5 rounded-full border-2 flex-shrink-0 flex items-center justify-center transition ${
              isDone
                ? "bg-green-500 border-green-500"
                : isMine
                ? "border-blue-400 active:bg-blue-50"
                : "border-gray-300"
            }`}
          >
            {isDone && <CheckCircle2 size={12} strokeWidth={3} className="text-white" />}
          </button>
          <div className="flex-1 min-w-0">
            <div className={`text-sm ${isDone ? "line-through text-gray-400" : "text-gray-800"}`}>
              {task.description ?? task.task_type}
            </div>
            <div className="text-xs text-gray-400 mt-0.5">
              → {task.assigned_to_user_id}
              {task.due_date && ` · due ${new Date(task.due_date).toLocaleDateString()}`}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <BottomSheet title="Tasks" onClose={onClose} badge={pending.length}>
      {tasks.length === 0 ? (
        <div className="flex flex-col items-center py-12 gap-2 text-gray-400">
          <ClipboardList size={32} strokeWidth={1.5} />
          <span className="text-sm">No tasks yet</span>
        </div>
      ) : (
        <div className="py-2">
          {pending.length > 0 && (
            <>
              <div className="px-5 pt-2 pb-1 text-[11px] font-semibold text-gray-400 uppercase tracking-wide">
                Pending ({pending.length})
              </div>
              {pending.map((t) => <TaskRow key={t.task_id} task={t} />)}
            </>
          )}
          {completed.length > 0 && (
            <>
              <div className="px-5 pt-3 pb-1 text-[11px] font-semibold text-gray-400 uppercase tracking-wide">
                Completed ({completed.length})
              </div>
              {completed.map((t) => <TaskRow key={t.task_id} task={t} />)}
            </>
          )}
        </div>
      )}
      <div className="px-5 py-4 border-t border-gray-100">
        <button
          onClick={() => { onClose(); onAssignNew(); }}
          className="w-full flex items-center justify-center gap-2 py-3 border-2 border-dashed border-gray-200 rounded-xl text-sm text-gray-500 active:bg-gray-50"
        >
          <ClipboardList size={16} strokeWidth={2} />
          Assign a new task
        </button>
      </div>
    </BottomSheet>
  );
}

// ── Field reports sheet ───────────────────────────────────────────────────────

function FieldReportsSheet({
  ticket,
  onClose,
}: {
  ticket: TicketDetail;
  onClose: () => void;
}) {
  const reports = (ticket.events ?? []).filter(
    (e) => e.payload && (e.payload as Record<string, unknown>).is_field_report
  );

  return (
    <BottomSheet title="Field Reports" onClose={onClose} badge={reports.length}>
      {reports.length === 0 ? (
        <div className="flex flex-col items-center py-12 gap-2 text-gray-400">
          <Flag size={32} strokeWidth={1.5} />
          <p className="text-sm">No field reports yet.</p>
          <p className="text-xs text-center px-8">
            Assign a field report with <code className="bg-gray-100 px-1 rounded">#report @officer</code> or{" "}
            <code className="bg-gray-100 px-1 rounded">#inspect @me</code> in the compose bar.
          </p>
        </div>
      ) : (
        <div className="py-3 space-y-3 px-4">
          {reports.map((e) => (
            <div key={e.event_id} className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
              <div className="flex items-center gap-1.5 mb-1.5">
                <Flag size={12} strokeWidth={2} className="text-amber-600" />
                <span className="text-[11px] font-semibold text-amber-700 uppercase tracking-wide">
                  Field Report
                </span>
                <span className="text-[10px] text-amber-500 ml-auto">
                  {new Date(e.created_at).toLocaleDateString()}
                </span>
              </div>
              <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">{e.note}</p>
              <div className="text-[10px] text-gray-400 mt-1.5">By {e.created_by_user_id ?? "officer"}</div>
            </div>
          ))}
        </div>
      )}
    </BottomSheet>
  );
}

// ── Grievance sheet ───────────────────────────────────────────────────────────

function GrievanceSheet({ ticket, onClose }: { ticket: TicketDetail; onClose: () => void }) {
  function Row({ label, value }: { label: string; value?: string | null }) {
    if (!value) return null;
    return (
      <div className="px-5 py-3.5 border-b border-gray-50">
        <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide mb-0.5">{label}</div>
        <div className="text-sm text-gray-800 leading-snug">{value}</div>
      </div>
    );
  }
  return (
    <BottomSheet title="Original Grievance" onClose={onClose}>
      <div className="py-2">
        {ticket.grievance_summary && (
          <div className="px-5 py-3.5 border-b border-gray-50">
            <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide mb-1">Summary</div>
            <p className="text-sm text-gray-800 leading-relaxed">{ticket.grievance_summary}</p>
          </div>
        )}
        <Row label="Categories"  value={ticket.grievance_categories} />
        <Row label="Priority"    value={ticket.priority} />
        <Row label="Submitted"   value={ticket.created_at ? new Date(ticket.created_at).toLocaleString() : null} />
        {ticket.ai_summary_en ? (
          <div className="px-5 py-3.5 border-b border-gray-50">
            <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide mb-1">
              AI Findings
              {ticket.ai_summary_updated_at && (
                <span className="text-[10px] text-gray-300 ml-1 normal-case font-normal">
                  · {new Date(ticket.ai_summary_updated_at).toLocaleDateString()}
                </span>
              )}
            </div>
            <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">{ticket.ai_summary_en}</p>
          </div>
        ) : (
          <div className="px-5 py-4 text-xs text-gray-400 italic">AI case findings not yet generated.</div>
        )}
      </div>
    </BottomSheet>
  );
}

// ── Complainant sheet ─────────────────────────────────────────────────────────

function ComplainantSheet({
  ticket,
  onClose,
  onRevealOriginal,
  onComplainantUpdated,
}: {
  ticket: TicketDetail;
  onClose: () => void;
  onRevealOriginal?: () => void;
  onComplainantUpdated?: () => void;
}) {
  const [pii, setPii] = useState<GrievancePii | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function loadPii() {
    setLoading(true);
    setError(null);
    getGrievancePii(ticket.ticket_id)
      .then(setPii)
      .catch(() => setError("Could not load complainant details"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadPii();
  }, [ticket.ticket_id]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <BottomSheet title="Complainant Info" onClose={onClose}>
      <div className="py-2">
        {loading ? (
          <div className="px-5 py-8 text-center text-xs text-gray-400 animate-pulse">Loading…</div>
        ) : error ? (
          <div className="px-5 py-6 text-center text-xs text-gray-500">
            <p>{error}</p>
            <button type="button" onClick={loadPii} className="mt-2 text-blue-600 underline">
              Retry
            </button>
          </div>
        ) : (
          <ComplainantEditForm
            ticket={ticket}
            pii={pii}
            variant="mobile"
            onSaved={() => {
              loadPii();
              onComplainantUpdated?.();
            }}
            onCancel={onClose}
            onRevealOriginal={onRevealOriginal}
          />
        )}
      </div>
    </BottomSheet>
  );
}

// ── Attachments sheet ─────────────────────────────────────────────────────────

function AttachmentsSheet({
  ticket,
  onClose,
  onUploaded,
  onUploadError,
}: {
  ticket: TicketDetail;
  onClose: () => void;
  onUploaded?: () => void;
  onUploadError?: (notice: ActionNoticeState) => void;
}) {
  const [chatbotFiles, setChatbotFiles] = useState<TicketFile[]>([]);
  const [officerFiles, setOfficerFiles] = useState<OfficerAttachment[]>([]);
  const [loading, setLoading]           = useState(true);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    Promise.all([
      listTicketFiles(ticket.ticket_id).catch(() => [] as TicketFile[]),
      listOfficerAttachments(ticket.ticket_id).catch(() => [] as OfficerAttachment[]),
    ]).then(([cf, of]) => { setChatbotFiles(cf); setOfficerFiles(of); })
      .finally(() => setLoading(false));
  }, [ticket.ticket_id]);

  const total = chatbotFiles.length + officerFiles.length;

  return (
    <BottomSheet title="Attachments" onClose={onClose} badge={total || undefined}>
      {loading ? (
        <div className="flex justify-center py-10 text-xs text-gray-400 animate-pulse">Loading…</div>
      ) : (
        <div className="py-2 px-4">
          {total === 0 && (
            <div className="flex flex-col items-center py-12 gap-2 text-gray-400">
              <Paperclip size={32} strokeWidth={1.5} />
              <span className="text-sm">No attachments yet</span>
            </div>
          )}
          <AttachmentListSection
            complainantFiles={chatbotFiles}
            officerFiles={officerFiles}
            getComplainantUrl={getFileDownloadUrl}
            getOfficerUrl={getOfficerAttachmentUrl}
            compact
          />
          <div className="py-4">
            <input ref={fileInputRef} type="file" className="hidden"
              accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,audio/*,.m4a,.mp3,.wav,.webm"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (!file) return;
                setUploading(true);
                try {
                  await uploadOfficerAttachment(ticket.ticket_id, file, "");
                  const [cf, of] = await Promise.all([
                    listTicketFiles(ticket.ticket_id).catch(() => [] as TicketFile[]),
                    listOfficerAttachments(ticket.ticket_id).catch(() => [] as OfficerAttachment[]),
                  ]);
                  setChatbotFiles(cf);
                  setOfficerFiles(of);
                  onUploaded?.();
                } catch (err) {
                  console.error("Upload failed", err);
                  onUploadError?.(formatUserFacingError(err, "upload"));
                } finally {
                  setUploading(false);
                }
              }} />
            <button type="button" disabled={uploading} onClick={() => fileInputRef.current?.click()}
              className="w-full flex items-center justify-center gap-2 py-3 border-2 border-dashed border-gray-200 rounded-xl text-sm text-gray-400 active:bg-gray-50 disabled:opacity-50">
              <Paperclip size={16} strokeWidth={2} />{uploading ? "Uploading…" : "Upload a file"}
            </button>
          </div>
        </div>
      )}
    </BottomSheet>
  );
}

// ── More actions sheet (Escalate / Close — reached via "More ▾" CTA) ─────────

function MoreActionsSheet({
  ticket,
  onEscalate,
  onAssignTask,
  onReassign,
  canAssign,
  canReassign,
  onClose,
}: {
  ticket: TicketDetail;
  onEscalate: () => void;
  onAssignTask: () => void;
  onReassign: () => void;
  canAssign: boolean;
  canReassign: boolean;
  onClose: () => void;
}) {
  const canEscalate = !["RESOLVED", "CLOSED"].includes(ticket.status_code);
  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30" />
      <div className="relative bg-white rounded-t-2xl shadow-2xl pb-safe-bottom" onClick={(e) => e.stopPropagation()}>
        <div className="pt-3 pb-1 flex justify-center">
          <div className="w-10 h-1 bg-gray-300 rounded-full" />
        </div>
        <div className="py-2">
          {canEscalate && (
            <button onClick={() => { onEscalate(); onClose(); }}
              className="w-full flex items-center gap-4 px-6 py-4 active:bg-gray-50 text-left">
              <ArrowUpCircle size={22} strokeWidth={1.8} className="text-amber-500 shrink-0" />
              <span className="text-base text-gray-800">Escalate to next level</span>
            </button>
          )}
          {canReassign && (
            <button onClick={() => { onReassign(); onClose(); }}
              className="w-full flex items-center gap-4 px-6 py-4 active:bg-gray-50 text-left">
              <ClipboardList size={22} strokeWidth={1.8} className="text-violet-500 shrink-0" />
              <span className="text-base text-gray-800">Ask for reassignment</span>
            </button>
          )}
          {canAssign && (
            <button onClick={() => { onAssignTask(); onClose(); }}
              className="w-full flex items-center gap-4 px-6 py-4 active:bg-gray-50 text-left">
              <User size={22} strokeWidth={1.8} className="text-blue-500 shrink-0" />
              <span className="text-base text-gray-800">Assign ticket to officer</span>
            </button>
          )}
          {canAssign && (
            <button onClick={() => { onAssignTask(); onClose(); }}
              className="w-full flex items-center gap-4 px-6 py-4 active:bg-gray-50 text-left">
              <ClipboardList size={22} strokeWidth={1.8} className="text-blue-500 shrink-0" />
              <span className="text-base text-gray-800">Assign a task</span>
            </button>
          )}
        </div>
        <div className="border-t border-gray-100 px-6 py-4">
          <button onClick={onClose} className="w-full text-sm font-medium text-gray-500 text-center">Cancel</button>
        </div>
      </div>
    </div>
  );
}

// ── Primary CTA bar ───────────────────────────────────────────────────────────

function PrimaryCtaBar({
  ticket,
  onAction,
  onMore,
  onOpenResolve,
}: {
  ticket: TicketDetail;
  onAction: (type: string) => void;
  onMore: () => void;
  onOpenResolve: () => void;
}) {
  const { status_code } = ticket;

  if (status_code === "RESOLVED" || status_code === "CLOSED") {
    return (
      <div className="px-4 py-2 text-center text-sm text-gray-400 py-2">
        {status_code === "RESOLVED"
          ? <><CheckCircle2 size={15} strokeWidth={2} className="inline mr-1 text-green-500" />Case resolved</>
          : <><Lock size={15} strokeWidth={2} className="inline mr-1 text-gray-400" />Case closed</>}
      </div>
    );
  }

  if (status_code === "OPEN") {
    return null;
  }

  return (
    <div className="flex gap-2 px-4 py-2">
      <button onClick={onOpenResolve}
        className="flex-1 bg-green-600 active:bg-green-700 text-white font-semibold py-3 rounded-xl text-sm">
        <Flag size={15} strokeWidth={2} className="inline mr-1.5" />Resolve
      </button>
      <button onClick={onMore}
        className="flex-1 bg-gray-100 active:bg-gray-200 text-gray-800 font-semibold py-3 rounded-xl text-sm inline-flex items-center justify-center gap-1">
        <ArrowUpCircle size={15} strokeWidth={2} />More ▾
      </button>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function MobileThreadPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: ticketId } = use(params);
  const router           = useRouter();
  const searchParams     = useSearchParams();
  const { user, roleKeys, isAdmin } = useAuth();
  const currentUserId    = canonicalUserId(user);
  const fieldVisitSubmitLock = useRef(false);

  const [ticket, setTicket]               = useState<TicketDetail | null>(null);
  const [sla, setSla]                     = useState<SlaStatus | null>(null);
  const [tasks, setTasks]                 = useState<TicketTask[]>([]);
  const [loading, setLoading]             = useState(true);
  const [activeFilter, setActiveFilter]   = useState<FilterChip>("all");
  const [noteText, setNoteText]           = useState("");
  const [submitting, setSubmitting]       = useState(false);
  const [fieldReportOpen, setFieldReportOpen] = useState(false);
  const [fieldReportLinkedTask, setFieldReportLinkedTask] = useState<TicketTask | null>(null);
  const [fieldReportSubmitting, setFieldReportSubmitting] = useState(false);
  const [attachUploading, setAttachUploading] = useState(false);
  const [escalationOpen, setEscalationOpen] = useState(false);
  const [callReportOpen, setCallReportOpen] = useState(false);
  const [reassignOpen, setReassignOpen] = useState(false);
  const [complainantFiles, setComplainantFiles] = useState<TicketFile[]>([]);
  const [officerFiles, setOfficerFiles] = useState<OfficerAttachment[]>([]);
  const [rosterIds, setRosterIds] = useState<string[]>([]);
  const [actionNotice, setActionNotice] = useState<ActionNoticeState | null>(null);
  const [revealModalOpen, setRevealModalOpen] = useState(false);
  const [revealSession, setRevealSession] = useState<RevealSession | null>(null);

  // Sheet visibility
  const [showInfoMenu, setShowInfoMenu]   = useState(false);
  const [infoPanel, setInfoPanel]         = useState<InfoPanel | null>(null);
  const [showMore, setShowMore]           = useState(false);
  const [showAssignTask, setShowAssignTask] = useState(false);
  const [resolutionOpen, setResolutionOpen] = useState(false);

  const threadEndRef = useRef<HTMLDivElement>(null);

  // ── Data loading ──────────────────────────────────────────────────────────

  const loadTicket = useCallback(async () => {
    try {
      const [t, s, tk] = await Promise.all([
        getTicket(ticketId),
        getSla(ticketId).catch(() => null),
        listTicketTasks(ticketId).catch(() => [] as TicketTask[]),
      ]);
      setTicket(t);
      setSla(s);
      setTasks(tk);
    } catch (e) {
      console.error("Failed to load ticket", e);
    } finally {
      setLoading(false);
    }
  }, [ticketId]);

  useEffect(() => { loadTicket(); }, [loadTicket]);
  useEffect(() => {
    if (!ticketId) return;
    Promise.all([
      listTicketFiles(ticketId).catch(() => [] as TicketFile[]),
      listOfficerAttachments(ticketId).catch(() => [] as OfficerAttachment[]),
    ]).then(([cf, of]) => { setComplainantFiles(cf); setOfficerFiles(of); });
    listOfficerRoster().then((r) => setRosterIds(r.map((o) => o.user_id))).catch(() => {});
  }, [ticketId, ticket?.updated_at]);
  useEffect(() => { markSeen(ticketId).catch(() => {}); }, [ticketId]);
  useEffect(() => {
    const openId = searchParams.get("openFieldVisit");
    if (!openId || tasks.length === 0) return;
    const pending = tasks.find((t) => t.task_id === openId && t.status === "PENDING");
    if (pending) {
      setFieldReportLinkedTask(pending);
      setFieldReportOpen(true);
    }
  }, [searchParams, tasks]);
  useEffect(() => {
    if (ticket && !loading) threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [ticket, loading]);

  // ── Derived state ─────────────────────────────────────────────────────────

  const viewerIds = useMemo(
    () => new Set((ticket?.viewers ?? []).map((v) => v.user_id)),
    [ticket],
  );
  const viewerTiers = useMemo(() => {
    const m = new Map<string, "informed" | "observer">();
    (ticket?.viewers ?? []).forEach((v) => m.set(v.user_id, v.tier as "informed" | "observer"));
    return m;
  }, [ticket]);

  const filteredEvents = useMemo(() => {
    if (!ticket) return [];
    switch (activeFilter) {
      case "all":        return ticket.events;
      case "mine":       return ticket.events.filter((e) => e.created_by_user_id === currentUserId);
      case "owner":      return ticket.events.filter((e) => e.created_by_user_id === ticket.assigned_to_user_id);
      case "supervisor": return ticket.events.filter((e) => e.actor_role && AUTHORITY_ROLES.has(e.actor_role) && e.created_by_user_id !== ticket.assigned_to_user_id);
      case "observers":  return ticket.events.filter((e) => e.created_by_user_id && viewerIds.has(e.created_by_user_id));
      case "tasks":      return ticket.events.filter((e) => isThreadTaskEvent(e.event_type));
      case "complainant":return ticket.events.filter((e) => COMPLAINANT_EVENT_TYPES.has(e.event_type));
      default:           return ticket.events;
    }
  }, [ticket, activeFilter, currentUserId, viewerIds]);

  const pendingTaskCount = useMemo(() => tasks.filter((t) => t.status === "PENDING").length, [tasks]);
  const myPendingTasks   = useMemo(
    () => tasks.filter((t) => t.status === "PENDING" && assigneeIsCurrentUser(t.assigned_to_user_id, user)),
    [tasks, user],
  );
  const canManageViewers = useMemo(() => !!ticket && ticket.assigned_to_user_id === currentUserId, [ticket, currentUserId]);
  const isAssignedActor = useMemo(
    () =>
      !!ticket &&
      (!ticket.assigned_to_user_id ||
        assigneeIsCurrentUser(ticket.assigned_to_user_id, user)),
    [ticket, user],
  );
  const userCanAssign = useMemo(
    () => !!ticket && canAssignTicket(roleKeys, ticket, isAdmin),
    [ticket, roleKeys, isAdmin],
  );
  const userCanReassign = useMemo(
    () => !!ticket && canRequestReassignment(roleKeys, ticket, currentUserId, isAdmin),
    [ticket, roleKeys, currentUserId, isAdmin],
  );
  const hasImages = useMemo(
    () => hasImageAttachment(complainantFiles, officerFiles),
    [complainantFiles, officerFiles],
  );

  const refreshFiles = useCallback(async () => {
    const [cf, of] = await Promise.all([
      listTicketFiles(ticketId).catch(() => [] as TicketFile[]),
      listOfficerAttachments(ticketId).catch(() => [] as OfficerAttachment[]),
    ]);
    setComplainantFiles(cf);
    setOfficerFiles(of);
  }, [ticketId]);

  const ensureAcknowledged = useCallback(async () => {
    await ensureTicketAcknowledged(ticket, isAssignedActor, ticketId, loadTicket);
  }, [ticket, isAssignedActor, ticketId, loadTicket]);
  const mentionParticipants = useMemo(() => {
    if (!ticket) return [];
    const ids = new Set<string>();
    if (ticket.assigned_to_user_id) ids.add(ticket.assigned_to_user_id);
    (ticket.viewers ?? []).forEach((v) => ids.add(v.user_id));
    ids.delete(currentUserId);
    const list = Array.from(ids).map((id) => ({ user_id: id, label: `@${id}` }));
    list.unshift({ user_id: "all", label: "@all" });
    return list;
  }, [ticket, currentUserId]);

  // ── Actions ───────────────────────────────────────────────────────────────

  const handleAction = useCallback(async (actionType: string) => {
    if (!ticket) return;
    setSubmitting(true);
    try {
      await performAction(ticketId, { action_type: actionType });
      await loadTicket();
      await refreshFiles();
    } catch (e) {
      console.error("Action failed", e);
      setActionNotice(formatUserFacingError(e));
    } finally {
      setSubmitting(false);
    }
  }, [ticket, ticketId, loadTicket, refreshFiles]);

  const openEscalationFlow = useCallback(() => {
    if (!hasImages) {
      setActionNotice({ message: MSG_IMAGE_BEFORE_ESCALATE, kind: "validation" });
      return;
    }
    setEscalationOpen(true);
  }, [hasImages]);

  const openResolveFlow = useCallback(() => {
    if (!hasImages) {
      setActionNotice({ message: MSG_IMAGE_BEFORE_RESOLVE, kind: "validation" });
      return;
    }
    setResolutionOpen(true);
  }, [hasImages]);

  const submitEscalation = useCallback(async (data: {
    escalationDate: string;
    personsInvolved: string[];
    notes: string;
  }) => {
    setSubmitting(true);
    try {
      await ensureAcknowledged();
      await performAction(ticketId, {
        action_type: "ESCALATE",
        escalation_date: data.escalationDate,
        persons_involved: data.personsInvolved,
        escalation_notes: data.notes,
      });
      setEscalationOpen(false);
      await loadTicket();
    } catch (e) {
      setActionNotice(formatUserFacingError(e));
      throw e;
    } finally {
      setSubmitting(false);
    }
  }, [ticketId, loadTicket, ensureAcknowledged]);

  const submitReassignment = useCallback(async (reasonCode: ReassignmentReasonCode, notes: string) => {
    setSubmitting(true);
    try {
      await performAction(ticketId, {
        action_type: "REASSIGNMENT_REQUESTED",
        reassignment_reason_code: reasonCode,
        reassignment_notes: notes,
      });
      setReassignOpen(false);
      await loadTicket();
    } catch (e) {
      setActionNotice(formatUserFacingError(e));
      throw e;
    } finally {
      setSubmitting(false);
    }
  }, [ticketId, loadTicket]);

  const submitCallReport = useCallback(async (data: CallReportFormData) => {
    setSubmitting(true);
    try {
      await ensureAcknowledged();
      await performAction(ticketId, {
        action_type: "NOTE",
        note: formatCallReportNote(data),
        is_call_report: true,
      });
      setCallReportOpen(false);
      await loadTicket();
    } catch (e) {
      setActionNotice(formatUserFacingError(e));
      throw e;
    } finally {
      setSubmitting(false);
    }
  }, [ticketId, loadTicket, ensureAcknowledged]);

  const submitResolve = useCallback(async (category: ResolutionCategoryCode, note: string) => {
    if (!ticket) return;
    setSubmitting(true);
    try {
      await ensureAcknowledged();
      await performAction(ticketId, {
        action_type: "RESOLVE",
        resolution_category: category,
        note,
      });
      setResolutionOpen(false);
      await loadTicket();
    } catch (e) {
      console.error("Resolve failed", e);
      setActionNotice(formatUserFacingError(e));
    } finally {
      setSubmitting(false);
    }
  }, [ticket, ticketId, loadTicket, ensureAcknowledged]);

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

  const handleHashCommand = useCallback(async (cmd: HashCommand) => {
    if (cmd.kind === "call_report") { setCallReportOpen(true); return; }
    if (cmd.kind === "action" && cmd.action === "ESCALATE") { openEscalationFlow(); return; }
    if (cmd.kind === "action" && cmd.action) { await handleAction(cmd.action); return; }
    if (cmd.kind === "assign" && !userCanAssign) {
      setActionNotice({ message: MSG_SUPERVISOR_ONLY_ASSIGN, kind: "validation" });
    }
  }, [handleAction, openEscalationFlow, userCanAssign]);

  const handleNoteOrReport = useCallback(async () => {
    if (!noteText.trim() || submitting) return;
    setSubmitting(true);
    const text = noteText.trim();
    setNoteText("");
    try {
      const assignMatch = text.match(/^#assign\s+@([A-Za-z0-9][A-Za-z0-9._@-]*)/);
      const reportAssignMatch = text.match(/^#report\s+@([A-Za-z0-9][A-Za-z0-9._@-]*)/);
      const inspectAssignee = parseInspectAssignCommand(text);
      if (inspectAssignee !== undefined) {
        const assignee = inspectAssignee ?? currentUserId;
        await createTask(ticketId, {
          task_type: "SITE_VISIT",
          assigned_to_user_id: assignee,
        });
      } else if (reportAssignMatch) {
        if (!userCanAssign) {
          setActionNotice({ message: MSG_SUPERVISOR_ONLY_FIELD_REPORT, kind: "validation" });
          setNoteText(text);
          return;
        }
        await createTask(ticketId, {
          task_type: "SYSTEM_NOTE",
          assigned_to_user_id: reportAssignMatch[1],
        });
      } else if (assignMatch) {
        if (!userCanAssign) {
          setActionNotice({ message: MSG_SUPERVISOR_ONLY_ASSIGN, kind: "validation" });
          setNoteText(text);
          return;
        }
        await patchTicket(ticketId, { assign_to_user_id: assignMatch[1] });
      } else {
        await ensureAcknowledged();
        await performAction(ticketId, { action_type: "NOTE", note: text });
      }
      await loadTicket();
      threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
    } catch (e) {
      console.error("Submit failed", e);
      setNoteText(text);
      setActionNotice(formatUserFacingError(e));
    } finally {
      setSubmitting(false);
    }
  }, [noteText, submitting, ticketId, loadTicket, ensureAcknowledged, currentUserId, userCanAssign]);

  const handleCompleteTask = useCallback(async (task: TicketTask) => {
    if (!ticket) return;
    if (isSiteVisitTask(task.task_type) && task.status === "PENDING") {
      openFieldReport(task);
      return;
    }
    try {
      await completeTask(ticketId, task.task_id);
      await loadTicket();
    } catch (e) {
      console.error("Complete task failed", e);
      setActionNotice(formatUserFacingError(e, "task"));
    }
  }, [ticket, ticketId, loadTicket, openFieldReport]);

  const submitFieldReportForm = useCallback(async (data: FieldVisitFormData) => {
    if (fieldVisitSubmitLock.current) return;
    fieldVisitSubmitLock.current = true;
    setFieldReportSubmitting(true);
    try {
      await submitStructuredFieldReport({
        ticketId,
        data,
        linkedTask: fieldReportLinkedTask,
        ensureAcknowledged,
      });
      closeFieldReport();
      await loadTicket();
      threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
    } catch (e) {
      console.error("Field report failed", e);
      setActionNotice(formatUserFacingError(e, "field_report"));
      throw e;
    } finally {
      fieldVisitSubmitLock.current = false;
      setFieldReportSubmitting(false);
    }
  }, [ticketId, fieldReportLinkedTask, loadTicket, ensureAcknowledged, closeFieldReport]);

  const handleAttachFile = useCallback(async (file: File) => {
    setAttachUploading(true);
    try {
      await uploadOfficerAttachment(ticketId, file, "");
      await refreshFiles();
      await loadTicket();
    } catch (e) {
      console.error("Attach failed", e);
      setActionNotice(formatUserFacingError(e, "upload"));
    } finally {
      setAttachUploading(false);
    }
  }, [ticketId, loadTicket, refreshFiles]);

  // ── Render ────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-sm text-gray-400 animate-pulse">Loading…</div>
      </div>
    );
  }

  if (!ticket) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <AlertTriangle size={32} strokeWidth={1.5} className="text-amber-400" />
        <div className="text-sm text-gray-500">Ticket not found</div>
        <button onClick={() => router.back()} className="text-blue-600 text-sm">← Go back</button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-dvh bg-white">

      {/* ── Sticky header ─────────────────────────────────────────────────── */}
      <div className="flex-shrink-0 bg-white border-b border-gray-200 pt-safe-top">

        {/* Row 1: back · title · SEAH badge · ⋮ */}
        <div className="flex items-center gap-2 px-2 py-2.5">
          <button onClick={() => router.back()} className="p-2 text-gray-500 active:bg-gray-100 rounded-lg">
            <ChevronLeft size={22} strokeWidth={2} />
          </button>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-gray-900 truncate">{ticket.grievance_id}</span>
              {ticket.is_seah && (
                <span className="inline-flex items-center gap-0.5 text-[10px] font-bold text-red-600 bg-red-50 px-1.5 py-0.5 rounded shrink-0">
                  <Lock size={9} strokeWidth={2.5} />SEAH
                </span>
              )}
            </div>
            <div className="text-xs text-gray-400 truncate leading-tight">
              {ticket.grievance_summary ?? "No summary"}
            </div>
          </div>
          {/* ⋮ opens the info menu */}
          <button
            onClick={() => setShowInfoMenu(true)}
            className="p-2 text-gray-500 active:bg-gray-100 rounded-lg"
            aria-label="Case info"
          >
            <MoreVertical size={20} strokeWidth={2} />
          </button>
        </div>

        {/* Row 2: SLA + status */}
        <SlaSubHeader ticket={ticket} sla={sla} />

        {/* Row 3: workflow mini-stepper */}
        {ticket.current_step && (
          <WorkflowMiniStepper
            steps={[ticket.current_step]}
            currentStepKey={ticket.current_step.step_key}
          />
        )}

        {/* Row 4: pending tasks banner */}
        {myPendingTasks.length > 0 && (
          <button
            onClick={() => setInfoPanel("tasks")}
            className="w-full bg-amber-50 border-b border-amber-200 px-4 py-1.5 text-xs text-amber-700 font-medium text-left active:bg-amber-100"
          >
            <ClipboardList size={12} strokeWidth={2} className="inline mr-1" />
            {myPendingTasks.length} task{myPendingTasks.length > 1 ? "s" : ""} assigned to you — tap to view
          </button>
        )}

        {/* Row 5: filter chips */}
        <FilterChips
          events={ticket.events}
          currentUserId={currentUserId}
          assignedToUserId={ticket.assigned_to_user_id ?? null}
          viewerIds={viewerIds}
          active={activeFilter}
          pendingTaskCount={pendingTaskCount}
          onChange={setActiveFilter}
        />

        {/* Row 6: viewers bar */}
        <ViewersBar
          viewers={ticket.viewers ?? []}
          canManage={canManageViewers}
          ticketId={ticketId}
          onChanged={loadTicket}
        />
      </div>

      <ActionNotice
        notice={actionNotice}
        onDismiss={() => setActionNotice(null)}
        className="mx-3 mt-2 flex-shrink-0"
      />

      {/* ── Thread — full width ────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto py-2">
        {ticket.status_code === "OPEN" && (
          <GrievanceThreadCard
            ticket={ticket}
            acknowledging={submitting}
            onAcknowledge={() => handleAction("ACKNOWLEDGE")}
            onClassificationUpdated={loadTicket}
          />
        )}
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
                    ticketId={ticketId}
                    onComplete={handleCompleteTask}
                  />
                );
              return (
                <NoteBubble
                  key={event.event_id}
                  event={event}
                  isMine={isMine}
                  assignedToUserId={ticket.assigned_to_user_id}
                  viewerIds={viewerIds}
                  viewerTiers={viewerTiers}
                />
              );
            })
        )}
        <div ref={threadEndRef} />
      </div>

      {/* ── Fixed bottom bar ──────────────────────────────────────────────── */}
      <div className={`flex-shrink-0 bg-white border-t pb-safe-bottom ${fieldReportOpen ? "border-amber-200" : "border-gray-200"}`}>
        <PrimaryCtaBar
          ticket={ticket}
          onAction={handleAction}
          onMore={() => setShowMore(true)}
          onOpenResolve={openResolveFlow}
        />
        <FieldReportComposeCard
          open={fieldReportOpen}
          defaultLocation={ticket.grievance_location}
          completeVisit={!!fieldReportLinkedTask}
          submitting={fieldReportSubmitting}
          onClose={closeFieldReport}
          onSubmit={submitFieldReportForm}
        />
        <EscalationFormCard
          open={escalationOpen}
          currentUserId={currentUserId}
          rosterIds={rosterIds}
          submitting={submitting}
          onClose={() => setEscalationOpen(false)}
          onSubmit={submitEscalation}
        />
        <CallReportComposeCard
          open={callReportOpen}
          submitting={submitting}
          onClose={() => setCallReportOpen(false)}
          onSubmit={submitCallReport}
        />
        <ReassignmentRequestCard
          open={reassignOpen}
          ticket={ticket}
          submitting={submitting}
          onClose={() => setReassignOpen(false)}
          onSubmit={submitReassignment}
        />
        <ComposeBar
          value={noteText}
          onChange={setNoteText}
          onSubmit={handleNoteOrReport}
          onFileSelected={handleAttachFile}
          attachUploading={attachUploading}
          onHashCommand={handleHashCommand}
          fieldReportOpen={fieldReportOpen}
          canAssign={userCanAssign}
          disabled={submitting || fieldReportSubmitting}
          participants={mentionParticipants}
        />
      </div>

      {/* ── Sheets ────────────────────────────────────────────────────────── */}

      {/* ⋮ info menu */}
      {showInfoMenu && (
        <InfoMenuSheet
          ticket={ticket}
          tasks={tasks}
          onSelect={(panel) => setInfoPanel(panel)}
          onClose={() => setShowInfoMenu(false)}
        />
      )}

      {/* Info panel bottom sheets */}
      {infoPanel === "tasks" && (
        <TasksSheet
          ticket={ticket}
          tasks={tasks}
          currentUserId={currentUserId}
          onClose={() => setInfoPanel(null)}
          onComplete={handleCompleteTask}
          onAssignNew={() => { setInfoPanel(null); setShowAssignTask(true); }}
        />
      )}
      {infoPanel === "grievance" && (
        <GrievanceSheet ticket={ticket} onClose={() => setInfoPanel(null)} />
      )}
      {infoPanel === "field_reports" && (
        <FieldReportsSheet ticket={ticket} onClose={() => setInfoPanel(null)} />
      )}
      {infoPanel === "complainant" && (
        <ComplainantSheet
          ticket={ticket}
          onClose={() => setInfoPanel(null)}
          onComplainantUpdated={loadTicket}
          onRevealOriginal={
            ticket.is_seah ? () => { setInfoPanel(null); setRevealModalOpen(true); } : undefined
          }
        />
      )}
      {infoPanel === "attachments" && (
        <AttachmentsSheet
          ticket={ticket}
          onClose={() => setInfoPanel(null)}
          onUploaded={loadTicket}
          onUploadError={(notice) => {
            setInfoPanel(null);
            setActionNotice(notice);
          }}
        />
      )}

      {/* More actions (Escalate / Close) */}
      {showMore && (
        <MoreActionsSheet
          ticket={ticket}
          onEscalate={openEscalationFlow}
          onAssignTask={() => setShowAssignTask(true)}
          onReassign={() => setReassignOpen(true)}
          canAssign={userCanAssign}
          canReassign={userCanReassign}
          onClose={() => setShowMore(false)}
        />
      )}

      {/* Assign task sheet */}
      {showAssignTask && (
        <AssignTaskSheet
          ticketId={ticketId}
          variant="sheet"
          onClose={() => setShowAssignTask(false)}
          onAssigned={async () => { setShowAssignTask(false); await loadTicket(); }}
        />
      )}

      <ResolutionSheet
        open={resolutionOpen}
        onClose={() => setResolutionOpen(false)}
        onSubmit={submitResolve}
        submitting={submitting}
      />

      {ticket && revealModalOpen && (
        <RevealModal
          ticketId={ticket.ticket_id}
          isSeah={ticket.is_seah}
          onClose={() => setRevealModalOpen(false)}
          onGranted={(session) => {
            setRevealModalOpen(false);
            setRevealSession(session);
          }}
        />
      )}
      {ticket && revealSession && (
        <RevealOverlay
          session={revealSession}
          ticketId={ticket.ticket_id}
          onClose={() => setRevealSession(null)}
        />
      )}

    </div>
  );
}
