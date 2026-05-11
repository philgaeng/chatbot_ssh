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
import { useRouter } from "next/navigation";
import {
  getTicket, getSla, performAction, markSeen, listTicketTasks, completeTask, createTask, patchTicket,
  listTicketFiles, listOfficerAttachments, getFileDownloadUrl, getOfficerAttachmentUrl,
  type TicketDetail, type TicketEvent, type SlaStatus, type TicketTask,
  type TicketFile, type OfficerAttachment,
} from "@/lib/api";
import { useAuth } from "@/app/providers/AuthProvider";
import {
  SYSTEM_EVENT_TYPES, TASK_EVENT_TYPES, NOTIFICATION_ONLY_EVENT_TYPES,
  COMPLAINANT_EVENT_TYPES, AUTHORITY_ROLES, type HashCommand,
} from "@/lib/mobile-constants";
import {
  AlertTriangle, ArrowUpCircle, Flag, Lock, ClipboardList, CheckCircle2,
  MoreVertical, User, FileText, Paperclip, ChevronLeft, Download, FileIcon, X,
  ClipboardCheck, BookOpen,
} from "lucide-react";

import { NoteBubble }                        from "@/components/thread/NoteBubble";
import { SystemPill }                         from "@/components/thread/SystemPill";
import { TaskCard, AssignTaskSheet }          from "@/components/thread/TaskCard";
import { FilterChips, type FilterChip }       from "@/components/thread/FilterChips";
import { ViewersBar }                         from "@/components/thread/ViewersBar";
import { ComposeBar }                         from "@/components/thread/ComposeBar";
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
  onComplete: (taskId: string) => void;
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
            disabled={isDone || !isMine}
            onClick={() => !isDone && isMine && onComplete(task.task_id)}
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
            Type <code className="bg-gray-100 px-1 rounded">#report</code> in the compose bar to add one.
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
        <Row label="Location"    value={ticket.grievance_location} />
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

function ComplainantSheet({ ticket, onClose }: { ticket: TicketDetail; onClose: () => void }) {
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
    <BottomSheet title="Complainant Info" onClose={onClose}>
      <div className="py-2">
        <div className="mx-5 mt-3 mb-4 bg-amber-50 border border-amber-100 rounded-xl px-4 py-2.5 text-xs text-amber-700">
          PII is masked per data policy. Full identity retrieved on-demand from the grievance system.
        </div>
        <Row label="Complainant ID"      value={ticket.complainant_id} />
        <Row label="Grievance reference" value={ticket.grievance_id} />
        <Row label="Location"            value={ticket.grievance_location} />
        <Row label="Categories"          value={ticket.grievance_categories} />
        <Row label="Submitted"           value={ticket.created_at ? new Date(ticket.created_at).toLocaleString() : null} />
        <Row label="Case status"         value={ticket.status_code} />
      </div>
    </BottomSheet>
  );
}

// ── Attachments sheet ─────────────────────────────────────────────────────────

function AttachmentsSheet({ ticket, onClose }: { ticket: TicketDetail; onClose: () => void }) {
  const [chatbotFiles, setChatbotFiles] = useState<TicketFile[]>([]);
  const [officerFiles, setOfficerFiles] = useState<OfficerAttachment[]>([]);
  const [loading, setLoading]           = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    Promise.all([
      listTicketFiles(ticket.ticket_id).catch(() => [] as TicketFile[]),
      listOfficerAttachments(ticket.ticket_id).catch(() => [] as OfficerAttachment[]),
    ]).then(([cf, of]) => { setChatbotFiles(cf); setOfficerFiles(of); })
      .finally(() => setLoading(false));
  }, [ticket.ticket_id]);

  const fmt = (b: number) =>
    b < 1024 ? `${b} B` : b < 1048576 ? `${(b / 1024).toFixed(1)} KB` : `${(b / 1048576).toFixed(1)} MB`;

  const total = chatbotFiles.length + officerFiles.length;

  return (
    <BottomSheet title="Attachments" onClose={onClose} badge={total || undefined}>
      {loading ? (
        <div className="flex justify-center py-10 text-xs text-gray-400 animate-pulse">Loading…</div>
      ) : (
        <div className="py-2">
          {total === 0 && (
            <div className="flex flex-col items-center py-12 gap-2 text-gray-400">
              <Paperclip size={32} strokeWidth={1.5} />
              <span className="text-sm">No attachments yet</span>
            </div>
          )}
          {chatbotFiles.length > 0 && (
            <>
              <div className="px-5 pt-2 pb-1 text-[11px] font-semibold text-gray-400 uppercase tracking-wide">
                From complainant
              </div>
              {chatbotFiles.map((f) => (
                <a key={f.file_id} href={getFileDownloadUrl(f.file_id)} target="_blank" rel="noopener noreferrer"
                  className="flex items-center gap-3 px-5 py-3 border-b border-gray-50 active:bg-gray-50">
                  <FileIcon size={20} strokeWidth={1.5} className="text-blue-400 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-gray-800 truncate">{f.file_name}</div>
                    <div className="text-xs text-gray-400">{fmt(f.file_size)}</div>
                  </div>
                  <Download size={16} strokeWidth={1.8} className="text-gray-300 shrink-0" />
                </a>
              ))}
            </>
          )}
          {officerFiles.length > 0 && (
            <>
              <div className="px-5 pt-3 pb-1 text-[11px] font-semibold text-gray-400 uppercase tracking-wide">
                Officer uploads
              </div>
              {officerFiles.map((f) => (
                <a key={f.file_id} href={getOfficerAttachmentUrl(f.file_id)} target="_blank" rel="noopener noreferrer"
                  className="flex items-center gap-3 px-5 py-3 border-b border-gray-50 active:bg-gray-50">
                  <FileIcon size={20} strokeWidth={1.5} className="text-green-400 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-gray-800 truncate">{f.file_name}</div>
                    <div className="text-xs text-gray-400">
                      {fmt(f.file_size)}{f.caption ? ` · ${f.caption}` : ""}
                    </div>
                  </div>
                  <Download size={16} strokeWidth={1.8} className="text-gray-300 shrink-0" />
                </a>
              ))}
            </>
          )}
          <div className="px-5 py-4">
            <input ref={fileInputRef} type="file" className="hidden"
              onChange={() => { /* wire uploadOfficerAttachment in follow-up */ }} />
            <button onClick={() => fileInputRef.current?.click()}
              className="w-full flex items-center justify-center gap-2 py-3 border-2 border-dashed border-gray-200 rounded-xl text-sm text-gray-400 active:bg-gray-50">
              <Paperclip size={16} strokeWidth={2} />Upload a file
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
  onAction,
  onAssignTask,
  onClose,
}: {
  ticket: TicketDetail;
  onAction: (type: string) => void;
  onAssignTask: () => void;
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
            <button onClick={() => { onAction("ESCALATE"); onClose(); }}
              className="w-full flex items-center gap-4 px-6 py-4 active:bg-gray-50 text-left">
              <ArrowUpCircle size={22} strokeWidth={1.8} className="text-amber-500 shrink-0" />
              <span className="text-base text-gray-800">Escalate to next level</span>
            </button>
          )}
          <button onClick={() => { onAssignTask(); onClose(); }}
            className="w-full flex items-center gap-4 px-6 py-4 active:bg-gray-50 text-left">
            <ClipboardList size={22} strokeWidth={1.8} className="text-blue-500 shrink-0" />
            <span className="text-base text-gray-800">Assign a task</span>
          </button>
          {canEscalate && (
            <button onClick={() => { onAction("CLOSE"); onClose(); }}
              className="w-full flex items-center gap-4 px-6 py-4 active:bg-gray-50 text-left">
              <Lock size={22} strokeWidth={1.8} className="text-red-400 shrink-0" />
              <span className="text-base text-red-600">Close without resolve</span>
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
}: {
  ticket: TicketDetail;
  onAction: (type: string) => void;
  onMore: () => void;
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
    return (
      <div className="px-4 py-2">
        <button onClick={() => onAction("ACKNOWLEDGE")}
          className="w-full bg-blue-600 active:bg-blue-700 text-white font-semibold py-3 rounded-xl text-sm">
          <CheckCircle2 size={16} strokeWidth={2} className="inline mr-1.5" />
          Acknowledge — tap to start
        </button>
      </div>
    );
  }

  return (
    <div className="flex gap-2 px-4 py-2">
      <button onClick={() => onAction("RESOLVE")}
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
  const { user }         = useAuth();
  const currentUserId    = user?.sub ?? "mock-super-admin";

  const [ticket, setTicket]               = useState<TicketDetail | null>(null);
  const [sla, setSla]                     = useState<SlaStatus | null>(null);
  const [tasks, setTasks]                 = useState<TicketTask[]>([]);
  const [loading, setLoading]             = useState(true);
  const [activeFilter, setActiveFilter]   = useState<FilterChip>("all");
  const [noteText, setNoteText]           = useState("");
  const [submitting, setSubmitting]       = useState(false);
  const [reportMode, setReportMode]       = useState(false);

  // Sheet visibility
  const [showInfoMenu, setShowInfoMenu]   = useState(false);
  const [infoPanel, setInfoPanel]         = useState<InfoPanel | null>(null);
  const [showMore, setShowMore]           = useState(false);
  const [showAssignTask, setShowAssignTask] = useState(false);

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
  useEffect(() => { markSeen(ticketId).catch(() => {}); }, [ticketId]);
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
      case "tasks":      return ticket.events.filter((e) => TASK_EVENT_TYPES.has(e.event_type));
      case "complainant":return ticket.events.filter((e) => COMPLAINANT_EVENT_TYPES.has(e.event_type));
      default:           return ticket.events;
    }
  }, [ticket, activeFilter, currentUserId, viewerIds]);

  const pendingTaskCount = useMemo(() => tasks.filter((t) => t.status === "PENDING").length, [tasks]);
  const myPendingTasks   = useMemo(
    () => tasks.filter((t) => t.status === "PENDING" &&
      (t.assigned_to_user_id === currentUserId || t.assigned_to_user_id === "mock-super-admin")),
    [tasks, currentUserId],
  );
  const canManageViewers = useMemo(() => !!ticket && ticket.assigned_to_user_id === currentUserId, [ticket, currentUserId]);
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
    } catch (e) {
      console.error("Action failed", e);
    } finally {
      setSubmitting(false);
    }
  }, [ticket, ticketId, loadTicket]);

  const handleHashCommand = useCallback(async (cmd: HashCommand) => {
    if (cmd.kind === "report")                          { setReportMode(true); return; }
    if (cmd.kind === "action" && cmd.action)            { await handleAction(cmd.action); return; }
    if (cmd.kind === "task" && cmd.taskKey) {
      try {
        await createTask(ticketId, { task_type: cmd.taskKey, assigned_to_user_id: currentUserId });
        await loadTicket();
      } catch (e) { console.error("Create task failed", e); }
    }
  }, [ticketId, currentUserId, loadTicket, handleAction]);

  const handleNoteOrReport = useCallback(async () => {
    if (!noteText.trim() || submitting) return;
    setSubmitting(true);
    const text = noteText.trim();
    setNoteText("");
    setReportMode(false);
    try {
      const assignMatch = text.match(/^#assign\s+@([\w.-]+)/);
      if (assignMatch) {
        await patchTicket(ticketId, { assign_to_user_id: assignMatch[1] });
      } else if (reportMode) {
        await performAction(ticketId, { action_type: "FIELD_REPORT", note: text });
      } else {
        await performAction(ticketId, { action_type: "NOTE", note: text });
      }
      await loadTicket();
      threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
    } catch (e) {
      console.error("Submit failed", e);
      setNoteText(text);
    } finally {
      setSubmitting(false);
    }
  }, [noteText, submitting, reportMode, ticketId, loadTicket]);

  const handleCompleteTask = useCallback(async (taskId: string) => {
    if (!ticket) return;
    try {
      await completeTask(ticketId, taskId);
      await loadTicket();
    } catch (e) { console.error("Complete task failed", e); }
  }, [ticket, ticketId, loadTicket]);

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

      {/* ── Thread — full width ────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto py-2">
        {filteredEvents.length === 0 ? (
          <div className="flex justify-center py-8 text-xs text-gray-400">No messages in this view</div>
        ) : (
          filteredEvents
            .filter((e: TicketEvent) => !NOTIFICATION_ONLY_EVENT_TYPES.has(e.event_type))
            .map((event: TicketEvent) => {
              const isMine = event.created_by_user_id === currentUserId;
              if (SYSTEM_EVENT_TYPES.has(event.event_type))
                return <SystemPill key={event.event_id} event={event} />;
              if (TASK_EVENT_TYPES.has(event.event_type))
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
      <div className="flex-shrink-0 bg-white border-t border-gray-200 pb-safe-bottom">
        <PrimaryCtaBar ticket={ticket} onAction={handleAction} onMore={() => setShowMore(true)} />
        <ComposeBar
          value={noteText}
          onChange={setNoteText}
          onSubmit={handleNoteOrReport}
          onAttach={() => setInfoPanel("attachments")}
          onHashCommand={handleHashCommand}
          reportMode={reportMode}
          onExitReportMode={() => setReportMode(false)}
          disabled={submitting}
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
        <ComplainantSheet ticket={ticket} onClose={() => setInfoPanel(null)} />
      )}
      {infoPanel === "attachments" && (
        <AttachmentsSheet ticket={ticket} onClose={() => setInfoPanel(null)} />
      )}

      {/* More actions (Escalate / Close) */}
      {showMore && (
        <MoreActionsSheet
          ticket={ticket}
          onAction={handleAction}
          onAssignTask={() => setShowAssignTask(true)}
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
    </div>
  );
}
