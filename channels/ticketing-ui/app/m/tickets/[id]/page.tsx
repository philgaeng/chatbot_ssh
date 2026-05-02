"use client";

/**
 * /m/tickets/[id] — Mobile thread screen.
 * Layout: sticky header → filter chips → scrollable thread → fixed bottom bar.
 * Shared sub-components live in components/thread/ and are reused by the desktop.
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
import { SYSTEM_EVENT_TYPES, TASK_EVENT_TYPES, NOTIFICATION_ONLY_EVENT_TYPES, AUTHORITY_ROLES, type HashCommand } from "@/lib/mobile-constants";
import { AlertTriangle, ArrowUpCircle, Flag, Lock, ClipboardList, CheckCircle2, MoreVertical, User, FileText, Paperclip, Users, ChevronLeft, Download, FileIcon } from "lucide-react";

import { NoteBubble }                        from "@/components/thread/NoteBubble";
import { SystemPill }                         from "@/components/thread/SystemPill";
import { TaskCard, AssignTaskSheet }          from "@/components/thread/TaskCard";
import { FilterChips, type FilterChip }       from "@/components/thread/FilterChips";
import { ViewersBar }                         from "@/components/thread/ViewersBar";
import { ComposeBar }                         from "@/components/thread/ComposeBar";
import { SlaSubHeader, WorkflowMiniStepper }  from "@/components/thread/SlaSubHeader";

// ── More actions bottom sheet ─────────────────────────────────────────────────

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
      <div className="bg-white rounded-t-2xl shadow-xl p-5" onClick={(e) => e.stopPropagation()}>
        <div className="w-12 h-1 bg-gray-300 rounded-full mx-auto mb-4" />
        <div className="space-y-1">
          {canEscalate && (
            <button
              onClick={() => { onAction("ESCALATE"); onClose(); }}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-xl active:bg-gray-50 text-left"
            >
              <ArrowUpCircle size={20} strokeWidth={2} className="text-amber-500 shrink-0" />
              <span className="text-sm font-medium text-gray-800">Escalate to next level</span>
            </button>
          )}
          <button
            onClick={() => { onAssignTask(); onClose(); }}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl active:bg-gray-50 text-left"
          >
            <ClipboardList size={20} strokeWidth={2} className="text-blue-500 shrink-0" />
            <span className="text-sm font-medium text-gray-800">Assign a task</span>
          </button>
          {canEscalate && (
            <button
              onClick={() => { onAction("CLOSE"); onClose(); }}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-xl active:bg-gray-50 text-left"
            >
              <Lock size={20} strokeWidth={2} className="text-red-400 shrink-0" />
              <span className="text-sm font-medium text-red-600">Close without resolve</span>
            </button>
          )}
        </div>
        <div className="mt-3 pt-3 border-t border-gray-100">
          <button onClick={onClose} className="w-full py-3 text-sm font-medium text-gray-500">
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Case info menu (⋮ dropdown) ───────────────────────────────────────────────

type InfoPanel = "complainant" | "grievance" | "attachments" | "members";

type InfoIcon = React.ComponentType<{ size?: number; strokeWidth?: number; className?: string }>;

function CaseInfoMenu({
  onSelect,
  onClose,
}: {
  onSelect: (panel: InfoPanel) => void;
  onClose: () => void;
}) {
  const items: Array<{ key: InfoPanel; label: string; Icon: InfoIcon }> = [
    { key: "complainant",  label: "Complainant info",       Icon: User },
    { key: "grievance",    label: "Grievance & findings",   Icon: FileText },
    { key: "attachments",  label: "Attachments",            Icon: Paperclip },
    { key: "members",      label: "Members",                Icon: Users },
  ];
  return (
    <>
      {/* Tap-away backdrop */}
      <div className="fixed inset-0 z-40" onClick={onClose} />
      {/* Dropdown — fixed top-right, below the header */}
      <div className="fixed top-14 right-2 z-50 bg-white rounded-2xl shadow-2xl border border-gray-100 min-w-[220px] overflow-hidden">
        {items.map(({ key, label, Icon }, idx) => (
          <button
            key={key}
            onClick={() => { onSelect(key); onClose(); }}
            className={`w-full flex items-center gap-3 px-4 py-3.5 text-sm text-gray-700 active:bg-gray-50 ${idx < items.length - 1 ? "border-b border-gray-50" : ""}`}
          >
            <Icon size={18} strokeWidth={1.8} className="text-gray-400 shrink-0" />
            <span>{label}</span>
          </button>
        ))}
      </div>
    </>
  );
}

// ── Shared panel shell (full-screen slide-up overlay) ─────────────────────────

function PanelShell({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 bg-white flex flex-col">
      <div className="flex-shrink-0 flex items-center gap-2 px-2 py-3 border-b border-gray-200 bg-white pt-safe-top">
        <button onClick={onClose} className="p-2 text-gray-500 active:bg-gray-100 rounded-lg">
          <ChevronLeft size={22} strokeWidth={2} />
        </button>
        <h2 className="text-base font-semibold text-gray-900">{title}</h2>
      </div>
      <div className="flex-1 overflow-y-auto">
        {children}
      </div>
    </div>
  );
}

// helper: label + value row
function InfoRow({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null;
  return (
    <div className="px-5 py-3.5 border-b border-gray-50">
      <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide mb-0.5">{label}</div>
      <div className="text-sm text-gray-800 leading-snug">{value}</div>
    </div>
  );
}

// ── Complainant Panel ─────────────────────────────────────────────────────────

function ComplainantPanel({ ticket, onClose }: { ticket: TicketDetail; onClose: () => void }) {
  return (
    <PanelShell title="Complainant info" onClose={onClose}>
      <div className="py-2">
        <div className="mx-5 mt-3 mb-4 bg-amber-50 border border-amber-100 rounded-xl px-4 py-2.5 text-xs text-amber-700">
          PII is masked per data policy. Full identity is retrieved on-demand from the grievance system.
        </div>
        <InfoRow label="Complainant ID" value={ticket.complainant_id} />
        <InfoRow label="Grievance reference" value={ticket.grievance_id} />
        <InfoRow label="Location" value={ticket.grievance_location} />
        <InfoRow label="Categories" value={ticket.grievance_categories} />
        <InfoRow label="Submitted" value={ticket.created_at ? new Date(ticket.created_at).toLocaleString() : null} />
        <InfoRow label="Case status" value={ticket.status_code} />
      </div>
    </PanelShell>
  );
}

// ── Grievance & Findings Panel ────────────────────────────────────────────────

function GrievancePanel({ ticket, onClose }: { ticket: TicketDetail; onClose: () => void }) {
  return (
    <PanelShell title="Grievance & findings" onClose={onClose}>
      <div className="py-2">
        {ticket.grievance_summary && (
          <div className="px-5 py-3.5 border-b border-gray-50">
            <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide mb-1">Summary</div>
            <p className="text-sm text-gray-800 leading-relaxed">{ticket.grievance_summary}</p>
          </div>
        )}
        <InfoRow label="Categories" value={ticket.grievance_categories} />
        <InfoRow label="Location" value={ticket.grievance_location} />
        <InfoRow label="Priority" value={ticket.priority} />

        {ticket.ai_summary_en ? (
          <div className="px-5 py-3.5 border-b border-gray-50">
            <div className="flex items-center gap-1.5 mb-1">
              <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide">AI Findings</div>
              {ticket.ai_summary_updated_at && (
                <span className="text-[10px] text-gray-300">
                  · {new Date(ticket.ai_summary_updated_at).toLocaleDateString()}
                </span>
              )}
            </div>
            <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">{ticket.ai_summary_en}</p>
          </div>
        ) : (
          <div className="px-5 py-5 text-xs text-gray-400 italic">
            AI case findings not yet generated.
          </div>
        )}
      </div>
    </PanelShell>
  );
}

// ── Attachments Panel ─────────────────────────────────────────────────────────

function AttachmentsPanel({
  ticket,
  onClose,
}: {
  ticket: TicketDetail;
  onClose: () => void;
}) {
  const [chatbotFiles, setChatbotFiles] = useState<TicketFile[]>([]);
  const [officerFiles, setOfficerFiles] = useState<OfficerAttachment[]>([]);
  const [loading, setLoading] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    Promise.all([
      listTicketFiles(ticket.ticket_id).catch(() => [] as TicketFile[]),
      listOfficerAttachments(ticket.ticket_id).catch(() => [] as OfficerAttachment[]),
    ]).then(([cf, of]) => {
      setChatbotFiles(cf);
      setOfficerFiles(of);
    }).finally(() => setLoading(false));
  }, [ticket.ticket_id]);

  const formatBytes = (b: number) => b < 1024 ? `${b} B` : b < 1024 * 1024 ? `${(b / 1024).toFixed(1)} KB` : `${(b / (1024 * 1024)).toFixed(1)} MB`;

  return (
    <PanelShell title="Attachments" onClose={onClose}>
      {loading ? (
        <div className="flex justify-center py-10 text-xs text-gray-400 animate-pulse">Loading…</div>
      ) : (
        <div className="py-2">
          {chatbotFiles.length === 0 && officerFiles.length === 0 && (
            <div className="flex flex-col items-center py-12 gap-2 text-gray-400">
              <Paperclip size={32} strokeWidth={1.5} />
              <span className="text-sm">No attachments yet</span>
            </div>
          )}

          {chatbotFiles.length > 0 && (
            <div>
              <div className="px-5 pt-3 pb-1 text-[11px] font-semibold text-gray-400 uppercase tracking-wide">
                From complainant
              </div>
              {chatbotFiles.map((f) => (
                <a
                  key={f.file_id}
                  href={getFileDownloadUrl(f.file_id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3 px-5 py-3 border-b border-gray-50 active:bg-gray-50"
                >
                  <FileIcon size={20} strokeWidth={1.5} className="text-blue-400 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-gray-800 truncate">{f.file_name}</div>
                    <div className="text-xs text-gray-400">{formatBytes(f.file_size)}</div>
                  </div>
                  <Download size={16} strokeWidth={1.8} className="text-gray-300 shrink-0" />
                </a>
              ))}
            </div>
          )}

          {officerFiles.length > 0 && (
            <div>
              <div className="px-5 pt-3 pb-1 text-[11px] font-semibold text-gray-400 uppercase tracking-wide">
                Officer uploads
              </div>
              {officerFiles.map((f) => (
                <a
                  key={f.file_id}
                  href={getOfficerAttachmentUrl(f.file_id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3 px-5 py-3 border-b border-gray-50 active:bg-gray-50"
                >
                  <FileIcon size={20} strokeWidth={1.5} className="text-green-400 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-gray-800 truncate">{f.file_name}</div>
                    <div className="text-xs text-gray-400">
                      {formatBytes(f.file_size)}
                      {f.caption ? ` · ${f.caption}` : ""}
                    </div>
                  </div>
                  <Download size={16} strokeWidth={1.8} className="text-gray-300 shrink-0" />
                </a>
              ))}
            </div>
          )}

          {/* Upload button */}
          <div className="px-5 pt-4 pb-6">
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              onChange={() => { /* wire to uploadOfficerAttachment in follow-up */ }}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="w-full flex items-center justify-center gap-2 py-3 border-2 border-dashed border-gray-200 rounded-xl text-sm text-gray-400 active:bg-gray-50"
            >
              <Paperclip size={16} strokeWidth={2} />
              Upload a file
            </button>
          </div>
        </div>
      )}
    </PanelShell>
  );
}

// ── Members Panel ─────────────────────────────────────────────────────────────

function MembersPanel({ ticket, onClose }: { ticket: TicketDetail; onClose: () => void }) {
  const viewers = ticket.viewers ?? [];
  return (
    <PanelShell title="Members" onClose={onClose}>
      <div className="py-2">
        {/* Case owner */}
        <div className="px-5 pt-3 pb-1 text-[11px] font-semibold text-gray-400 uppercase tracking-wide">
          Case owner
        </div>
        {ticket.assigned_to_user_id ? (
          <div className="flex items-center gap-3 px-5 py-3 border-b border-gray-50">
            <div className="w-9 h-9 rounded-full bg-blue-100 flex items-center justify-center shrink-0">
              <User size={18} strokeWidth={1.8} className="text-blue-500" />
            </div>
            <div>
              <div className="text-sm font-medium text-gray-800">{ticket.assigned_to_user_id}</div>
              <div className="text-xs text-gray-400">Assigned officer</div>
            </div>
          </div>
        ) : (
          <div className="px-5 py-3 text-sm text-gray-400 italic border-b border-gray-50">Unassigned</div>
        )}

        {/* Watchers */}
        <div className="px-5 pt-3 pb-1 text-[11px] font-semibold text-gray-400 uppercase tracking-wide">
          Watchers ({viewers.length})
        </div>
        {viewers.length === 0 ? (
          <div className="px-5 py-3 text-sm text-gray-400 italic">No watchers</div>
        ) : (
          viewers.map((v) => (
            <div key={v.viewer_id} className="flex items-center gap-3 px-5 py-3 border-b border-gray-50">
              <div className="w-9 h-9 rounded-full bg-gray-100 flex items-center justify-center shrink-0">
                <User size={17} strokeWidth={1.8} className="text-gray-400" />
              </div>
              <div>
                <div className="text-sm text-gray-800">{v.user_id}</div>
                <div className="text-xs text-gray-400">Added {new Date(v.added_at).toLocaleDateString()}</div>
              </div>
            </div>
          ))
        )}
      </div>
    </PanelShell>
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
      <div className="px-4 py-2">
        <div className="text-center text-sm text-gray-400 py-2">
          {status_code === "RESOLVED"
            ? <><CheckCircle2 size={15} strokeWidth={2} className="inline mr-1 text-green-500" />Case resolved</>
            : <><Lock size={15} strokeWidth={2} className="inline mr-1 text-gray-400" />Case closed</>}
        </div>
      </div>
    );
  }

  if (status_code === "OPEN") {
    return (
      <div className="px-4 py-2">
        <button
          onClick={() => onAction("ACKNOWLEDGE")}
          className="w-full bg-blue-600 active:bg-blue-700 text-white font-semibold py-3 rounded-xl text-sm transition-colors"
        >
          <CheckCircle2 size={16} strokeWidth={2} className="inline mr-1.5" />
          Acknowledge — tap to start
        </button>
      </div>
    );
  }

  return (
    <div className="flex gap-2 px-4 py-2">
      <button
        onClick={() => onAction("RESOLVE")}
        className="flex-1 bg-green-600 active:bg-green-700 text-white font-semibold py-3 rounded-xl text-sm transition-colors"
      >
        <Flag size={15} strokeWidth={2} className="inline mr-1.5" />Resolve
      </button>
      <button
        onClick={onMore}
        className="flex-1 bg-gray-100 active:bg-gray-200 text-gray-800 font-semibold py-3 rounded-xl text-sm transition-colors inline-flex items-center justify-center gap-1"
      >
        <ArrowUpCircle size={15} strokeWidth={2} />More ▾
      </button>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function MobileThreadPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: ticketId } = use(params);
  const router = useRouter();
  const { user } = useAuth();
  const currentUserId = user?.sub ?? "mock-super-admin";

  const [ticket, setTicket]       = useState<TicketDetail | null>(null);
  const [sla, setSla]             = useState<SlaStatus | null>(null);
  const [tasks, setTasks]         = useState<TicketTask[]>([]);
  const [loading, setLoading]     = useState(true);
  const [activeFilter, setActiveFilter] = useState<FilterChip>("all");
  const [noteText, setNoteText]   = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showMore, setShowMore]   = useState(false);
  const [showAssignTask, setShowAssignTask] = useState(false);
  const [showInfoMenu, setShowInfoMenu] = useState(false);
  const [infoPanel, setInfoPanel] = useState<InfoPanel | null>(null);
  const [reportMode, setReportMode] = useState(false);

  const threadEndRef = useRef<HTMLDivElement>(null);

  // ── Data loading ────────────────────────────────────────────────────────

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

  // ── Derived state ───────────────────────────────────────────────────────

  const viewerIds = useMemo(
    () => new Set((ticket?.viewers ?? []).map((v) => v.user_id)),
    [ticket],
  );

  const filteredEvents = useMemo(() => {
    if (!ticket) return [];
    switch (activeFilter) {
      case "all":        return ticket.events;
      case "mine":       return ticket.events.filter((e) => e.created_by_user_id === currentUserId);
      case "owner":      return ticket.events.filter((e) => e.created_by_user_id === ticket.assigned_to_user_id);
      case "supervisor": return ticket.events.filter((e) => e.actor_role && AUTHORITY_ROLES.has(e.actor_role) && e.created_by_user_id !== ticket.assigned_to_user_id);
      case "observers":  return ticket.events.filter((e) => e.created_by_user_id && viewerIds.has(e.created_by_user_id));
      case "tasks":      return ticket.events.filter((e) => TASK_EVENT_TYPES.has(e.event_type));
      default:           return ticket.events;
    }
  }, [ticket, activeFilter, currentUserId, viewerIds]);

  const pendingTaskCount = useMemo(
    () => tasks.filter((t) => t.status === "PENDING").length,
    [tasks],
  );

  const myPendingTasks = useMemo(
    () => tasks.filter((t) => t.status === "PENDING" &&
      (t.assigned_to_user_id === currentUserId || t.assigned_to_user_id === "mock-super-admin")),
    [tasks, currentUserId],
  );

  const canManageViewers = useMemo(
    () => !!ticket && ticket.assigned_to_user_id === currentUserId,
    [ticket, currentUserId],
  );

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

  // ── Actions ─────────────────────────────────────────────────────────────

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
    if (cmd.kind === "report") { setReportMode(true); return; }
    if (cmd.kind === "action" && cmd.action) { await handleAction(cmd.action); return; }
    if (cmd.kind === "task" && cmd.taskKey) {
      try {
        await createTask(ticketId, { task_type: cmd.taskKey, assigned_to_user_id: currentUserId });
        await loadTicket();
      } catch (e) {
        console.error("Create task failed", e);
      }
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
    } catch (e) {
      console.error("Complete task failed", e);
    }
  }, [ticket, ticketId, loadTicket]);

  // ── Render ──────────────────────────────────────────────────────────────

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

      {/* ── Sticky header ───────────────────────────────────────── */}
      <div className="flex-shrink-0 bg-white border-b border-gray-200 pt-safe-top">
        <div className="flex items-center gap-2 px-2 py-3">
          <button onClick={() => router.back()} className="p-2 text-gray-500 active:bg-gray-100 rounded-lg">
            ←
          </button>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-gray-900 truncate">{ticket.grievance_id}</span>
              {ticket.is_seah && (
                <span className="inline-flex items-center gap-0.5 text-[10px] font-bold text-red-600 bg-red-50 px-1.5 py-0.5 rounded shrink-0">
                  <Lock size={9} strokeWidth={2.5} />SEAH
                </span>
              )}
            </div>
            <div className="text-xs text-gray-400 truncate">
              {ticket.grievance_summary ?? "No summary"}
            </div>
          </div>
          <button
            onClick={() => setShowInfoMenu(true)}
            className="p-2 text-gray-400 active:bg-gray-100 rounded-lg"
            aria-label="Case info"
          >
            <MoreVertical size={20} strokeWidth={2} />
          </button>
        </div>

        <SlaSubHeader ticket={ticket} sla={sla} />

        {/* Mini stepper — needs full step list; current_step only carries one step,
            so stepper will show just that step until we wire a full step list API. */}
        {ticket.current_step && (
          <WorkflowMiniStepper
            steps={[ticket.current_step]}
            currentStepKey={ticket.current_step.step_key}
          />
        )}

        {myPendingTasks.length > 0 && (
          <div className="bg-amber-50 border-b border-amber-200 px-4 py-1.5 text-xs text-amber-700 font-medium">
            <ClipboardList size={12} strokeWidth={2} className="inline mr-1" />
            {myPendingTasks.length} task{myPendingTasks.length > 1 ? "s" : ""} assigned to you
          </div>
        )}

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
          ticketId={ticketId}
          onChanged={loadTicket}
        />
      </div>

      {/* ── Thread ──────────────────────────────────────────────── */}
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
              return <NoteBubble key={event.event_id} event={event} isMine={isMine} assignedToUserId={ticket.assigned_to_user_id} viewerIds={viewerIds} />;
            })
        )}
        <div ref={threadEndRef} />
      </div>

      {/* ── Fixed bottom bar ────────────────────────────────────── */}
      <div className="flex-shrink-0 bg-white border-t border-gray-200 pb-safe-bottom">
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
        <PrimaryCtaBar ticket={ticket} onAction={handleAction} onMore={() => setShowMore(true)} />
      </div>

      {/* ── Sheets ──────────────────────────────────────────────── */}
      {showMore && (
        <MoreActionsSheet
          ticket={ticket}
          onAction={handleAction}
          onAssignTask={() => setShowAssignTask(true)}
          onClose={() => setShowMore(false)}
        />
      )}
      {showAssignTask && (
        <AssignTaskSheet
          ticketId={ticketId}
          variant="sheet"
          onClose={() => setShowAssignTask(false)}
          onAssigned={async () => { setShowAssignTask(false); await loadTicket(); }}
        />
      )}

      {/* ── Case info dropdown menu ──────────────────────────────── */}
      {showInfoMenu && (
        <CaseInfoMenu
          onSelect={(panel) => setInfoPanel(panel)}
          onClose={() => setShowInfoMenu(false)}
        />
      )}

      {/* ── Info panels (full-screen overlays) ──────────────────── */}
      {infoPanel === "complainant" && (
        <ComplainantPanel ticket={ticket} onClose={() => setInfoPanel(null)} />
      )}
      {infoPanel === "grievance" && (
        <GrievancePanel ticket={ticket} onClose={() => setInfoPanel(null)} />
      )}
      {infoPanel === "attachments" && (
        <AttachmentsPanel ticket={ticket} onClose={() => setInfoPanel(null)} />
      )}
      {infoPanel === "members" && (
        <MembersPanel ticket={ticket} onClose={() => setInfoPanel(null)} />
      )}
    </div>
  );
}
