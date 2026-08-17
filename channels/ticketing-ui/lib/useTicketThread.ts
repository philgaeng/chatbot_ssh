// SPDX-License-Identifier: Apache-2.0

/**
 * H2-06 — `useTicketThread`: the shared orchestration layer behind the desktop
 * (`app/tickets/[id]`) and mobile (`app/m/tickets/[id]`) ticket-thread screens.
 *
 * Before this hook the two pages each carried ~350 lines of *identical* page
 * orchestration (data load/reload, chip filtering, viewers/tiers, mention
 * participants, the acknowledge-ensure gate, and every mutation handler) — already
 * drifting (see the two `// H2-06 deviation:` notes below). Leaf components in
 * `components/thread/*` were already shared; only this orchestration layer was
 * duplicated. This hook owns it; the pages keep layout/JSX + page-specific UI state
 * (desktop panels vs mobile bottom-sheets).
 *
 * Auth is passed IN (not read via `useAuth`) so this module stays free of the
 * `AuthProvider`/`next/navigation` import graph and its pure helpers
 * ({@link filterThreadEvents}) remain unit-testable in a plain node env.
 */
"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from "react";
import {
  getTicket, getSla, performAction, markSeen, listTicketTasks, completeTask, createTask,
  patchTicket, listTicketFiles, listOfficerAttachments, uploadOfficerAttachment, listOfficerRoster,
  type TicketDetail, type TicketEvent, type SlaStatus, type TicketTask,
  type TicketFile, type OfficerAttachment,
} from "@/lib/api";
import {
  canonicalUserId, assigneeIsCurrentUser, type TokenPayload,
} from "@/lib/auth/token-storage";
import { ensureTicketAcknowledged } from "@/lib/ticket-ack";
import {
  formatCallReportNote, isSiteVisitTask,
  type CallReportFormData, type FieldVisitFormData,
} from "@/lib/field-visit";
import { submitStructuredFieldReport } from "@/lib/submit-field-report";
import {
  canAssignTicket, canSupervisorAssign, getReassignMode, type ReassignMode,
} from "@/lib/officer-permissions";
import { hasImageAttachment } from "@/lib/attachments";
import {
  formatUserFacingError,
  MSG_IMAGE_BEFORE_ESCALATE, MSG_IMAGE_BEFORE_RESOLVE, MSG_SUPERVISOR_ONLY_ASSIGN,
  type ActionNoticeState,
} from "@/lib/user-messages";
import {
  AUTHORITY_ROLES, SYSTEM_EVENT_TYPES, COMPLAINANT_EVENT_TYPES, isThreadTaskEvent,
  type HashCommand,
} from "@/lib/mobile-constants";
import { parseThreadCommand } from "@/lib/threadCommands";
import type { ResolutionCategoryCode } from "@/lib/resolution";
import type { FilterChip } from "@/components/thread/FilterChips";
import type { MentionParticipant } from "@/components/thread/ComposeBar";
import type { ReassignmentReasonCode } from "@/components/thread/ReassignmentRequestCard";

// ── Pure chip-filter predicate ────────────────────────────────────────────────
// Extracted verbatim from the two pages' `filteredEvents` switches. Kept as a
// standalone pure function so it is unit-testable in a node env (no React) and so
// both the hook's `useMemo` and the parity test call the exact same code.
//
// H2-06 deviation (drift #1): the mobile page's switch was MISSING the `"system"`
// case — a chip the desktop had — so tapping "System" on mobile silently fell
// through `default` and showed *all* events. Resolved to the desktop behavior: the
// `"system"` case is included here, so mobile now filters to system events too
// (the ticket flagged this exact silent divergence).

/** Context a chip filter needs beyond the event list itself. */
export interface ThreadFilterContext {
  currentUserId: string;
  assignedToUserId: string | null;
  viewerIds: Set<string>;
}

export function filterThreadEvents(
  events: TicketEvent[],
  activeFilter: FilterChip,
  ctx: ThreadFilterContext,
): TicketEvent[] {
  switch (activeFilter) {
    case "all":         return events;
    case "mine":        return events.filter((e) => e.created_by_user_id === ctx.currentUserId);
    case "owner":       return events.filter((e) => e.created_by_user_id === ctx.assignedToUserId);
    case "supervisor":  return events.filter((e) => e.actor_role && AUTHORITY_ROLES.has(e.actor_role) && e.created_by_user_id !== ctx.assignedToUserId);
    case "observers":   return events.filter((e) => e.created_by_user_id && ctx.viewerIds.has(e.created_by_user_id));
    case "tasks":       return events.filter((e) => isThreadTaskEvent(e.event_type));
    case "complainant": return events.filter((e) => COMPLAINANT_EVENT_TYPES.has(e.event_type));
    case "system":      return events.filter((e) => SYSTEM_EVENT_TYPES.has(e.event_type));
    default:            return events;
  }
}

// ── Hook ───────────────────────────────────────────────────────────────────────

export interface UseTicketThreadOptions {
  ticketId: string;
  /** From `useAuth()` — passed in to keep this module out of the AuthProvider graph. */
  user: TokenPayload | null;
  roleKeys: string[];
  isAdmin: boolean;
}

export interface UseTicketThreadResult {
  // ── Core data ──────────────────────────────────────────────────────────────
  ticket: TicketDetail | null;
  sla: SlaStatus | null;
  tasks: TicketTask[];
  loading: boolean;
  /** Friendly load-error message (null when none). Desktop renders this directly. */
  error: string | null;
  /** True when the load failed with an HTTP 404 — lets mobile show "not found". */
  errorIsNotFound: boolean;
  rosterIds: string[];

  // ── Thread / compose state ───────────────────────────────────────────────────
  activeFilter: FilterChip;
  setActiveFilter: (f: FilterChip) => void;
  noteText: string;
  setNoteText: (v: string) => void;
  submitting: boolean;
  actionNotice: ActionNoticeState | null;
  setActionNotice: (n: ActionNoticeState | null) => void;
  threadEndRef: RefObject<HTMLDivElement | null>;

  // ── Flow-open state (compose cards / sheets owned by the hook) ───────────────
  escalationOpen: boolean;
  setEscalationOpen: (v: boolean) => void;
  resolutionOpen: boolean;
  setResolutionOpen: (v: boolean) => void;
  reassignOpen: boolean;
  setReassignOpen: (v: boolean) => void;
  callReportOpen: boolean;
  setCallReportOpen: (v: boolean) => void;
  fieldReportOpen: boolean;
  fieldReportLinkedTask: TicketTask | null;
  fieldReportSubmitting: boolean;
  attachUploading: boolean;

  // ── Derived ──────────────────────────────────────────────────────────────────
  currentUserId: string;
  /** Admin, unassigned, or the assignee — the "may act as actor" flag (ack-ensure). */
  isAssigned: boolean;
  viewerIds: Set<string>;
  viewerTiers: Map<string, "informed" | "observer">;
  filteredEvents: TicketEvent[];
  mentionParticipants: MentionParticipant[];
  pendingTaskCount: number;
  hasResolutionRecord: boolean;
  canManageViewers: boolean;
  userCanAssign: boolean;
  userCanSupervisorAssign: boolean;
  reassignMode: ReassignMode | null;

  // ── Actions ──────────────────────────────────────────────────────────────────
  reload: () => Promise<void>;
  ensureAcknowledged: () => Promise<void>;
  /** ACKNOWLEDGE / GRC_CONVENE / other one-shot ticket actions (optional extra payload). */
  performSimpleAction: (actionType: string, extra?: Record<string, string>) => Promise<void>;
  openEscalationFlow: () => void;
  submitEscalation: (data: { escalationDate: string; personsInvolved: string[]; notes: string }) => Promise<void>;
  openResolveFlow: () => void;
  submitResolve: (category: ResolutionCategoryCode, note: string) => Promise<void>;
  submitReassignment: (reasonCode: ReassignmentReasonCode, notes: string) => Promise<void>;
  submitCallReport: (data: CallReportFormData) => Promise<void>;
  /** Compose-bar submit — routes `#assign` / `#inspect` / plain note (see threadCommands). */
  submitNote: () => Promise<void>;
  handleHashCommand: (cmd: HashCommand) => Promise<void>;
  handleCompleteTask: (task: TicketTask) => Promise<void>;
  openFieldReport: (linkedTask?: TicketTask | null) => void;
  closeFieldReport: () => void;
  submitFieldReportForm: (data: FieldVisitFormData) => Promise<void>;
  handleAttachFile: (file: File) => Promise<void>;
}

export function useTicketThread({
  ticketId,
  user,
  roleKeys,
  isAdmin,
}: UseTicketThreadOptions): UseTicketThreadResult {
  // ── Core data ──────────────────────────────────────────────────────────────
  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [sla, setSla]       = useState<SlaStatus | null>(null);
  const [tasks, setTasks]   = useState<TicketTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState<string | null>(null);
  const [errorIsNotFound, setErrorIsNotFound] = useState(false);
  const [complainantFiles, setComplainantFiles] = useState<TicketFile[]>([]);
  const [officerFiles, setOfficerFiles]         = useState<OfficerAttachment[]>([]);
  const [rosterIds, setRosterIds]               = useState<string[]>([]);
  const loadSeqRef = useRef(0);

  // ── Thread / compose state ───────────────────────────────────────────────────
  const [activeFilter, setActiveFilter] = useState<FilterChip>("all");
  const [noteText, setNoteText]         = useState("");
  const [submitting, setSubmitting]     = useState(false);
  const [actionNotice, setActionNotice] = useState<ActionNoticeState | null>(null);
  const threadEndRef = useRef<HTMLDivElement>(null);

  // ── Flow-open state ──────────────────────────────────────────────────────────
  const [escalationOpen, setEscalationOpen] = useState(false);
  const [resolutionOpen, setResolutionOpen] = useState(false);
  const [reassignOpen, setReassignOpen]     = useState(false);
  const [callReportOpen, setCallReportOpen] = useState(false);
  const [fieldReportOpen, setFieldReportOpen] = useState(false);
  const [fieldReportLinkedTask, setFieldReportLinkedTask] = useState<TicketTask | null>(null);
  const [fieldReportSubmitting, setFieldReportSubmitting] = useState(false);
  const [attachUploading, setAttachUploading] = useState(false);
  const fieldVisitSubmitLock = useRef(false);

  // ── Data loading ─────────────────────────────────────────────────────────────
  const refreshFiles = useCallback(async () => {
    const [cf, of] = await Promise.all([
      listTicketFiles(ticketId).catch(() => [] as TicketFile[]),
      listOfficerAttachments(ticketId).catch(() => [] as OfficerAttachment[]),
    ]);
    setComplainantFiles(cf);
    setOfficerFiles(of);
  }, [ticketId]);

  // Single reload path for both pages. Guarded by a sequence ref (mobile's
  // stale-response guard, adopted for both) so a slow first load can't clobber a
  // newer one. Does NOT flip `loading` back to true on reload — so a post-mutation
  // refresh never blanks the screen with the full-page loader (desktop behavior;
  // mobile used to flash "Loading…" on every action — that flicker is now gone).
  const reload = useCallback(async () => {
    const seq = ++loadSeqRef.current;
    setError(null);
    setErrorIsNotFound(false);
    try {
      const [t, s, tk] = await Promise.all([
        getTicket(ticketId),
        getSla(ticketId).catch(() => null),
        listTicketTasks(ticketId).catch(() => [] as TicketTask[]),
      ]);
      if (seq !== loadSeqRef.current) return; // a newer load has started
      setTicket(t);
      setSla(s);
      setTasks(tk);
      await refreshFiles();
      markSeen(ticketId).catch(() => {});
    } catch (e) {
      if (seq !== loadSeqRef.current) return;
      console.error("Failed to load ticket", e);
      setTicket(null);
      setError(formatUserFacingError(e).message);
      const raw = e instanceof Error ? e.message : String(e);
      setErrorIsNotFound(/^API 404\b/.test(raw));
    } finally {
      if (seq === loadSeqRef.current) setLoading(false);
    }
  }, [ticketId, refreshFiles]);

  useEffect(() => { void reload(); }, [reload]);

  useEffect(() => {
    listOfficerRoster().then((r) => setRosterIds(r.map((o) => o.user_id))).catch(() => {});
  }, []);

  // ── Derived ──────────────────────────────────────────────────────────────────
  const currentUserId = canonicalUserId(user);
  const isAssigned = isAdmin
    || !ticket?.assigned_to_user_id
    || assigneeIsCurrentUser(ticket.assigned_to_user_id, user);

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
    return filterThreadEvents(ticket.events, activeFilter, {
      currentUserId,
      assignedToUserId: ticket.assigned_to_user_id ?? null,
      viewerIds,
    });
  }, [ticket, activeFilter, currentUserId, viewerIds]);

  const pendingTaskCount = useMemo(() => tasks.filter((t) => t.status === "PENDING").length, [tasks]);

  const hasImages = useMemo(
    () => hasImageAttachment(complainantFiles, officerFiles),
    [complainantFiles, officerFiles],
  );

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

  const canManageViewers = useMemo(
    () => !!ticket && ticket.assigned_to_user_id === currentUserId,
    [ticket, currentUserId],
  );

  const mentionParticipants = useMemo<MentionParticipant[]>(() => {
    if (!ticket) return [];
    const ids = new Set<string>();
    if (ticket.assigned_to_user_id) ids.add(ticket.assigned_to_user_id);
    (ticket.viewers ?? []).forEach((v) => ids.add(v.user_id));
    ids.delete(currentUserId);
    const list = Array.from(ids).map((uid) => ({ user_id: uid, label: `@${uid}` }));
    list.unshift({ user_id: "all", label: "@all" });
    return list;
  }, [ticket, currentUserId]);

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

  // ── Acknowledge-ensure gate ──────────────────────────────────────────────────
  // H2-06 deviation: the mobile page computed its actor flag without the admin
  // bypass the desktop had (`isAdmin || …`). Unified to the desktop `isAssigned`
  // (admin-inclusive) so an admin acting on mobile auto-acknowledges the same way
  // they already did on desktop. Only reachable difference is admins-on-mobile.
  const ensureAcknowledged = useCallback(async () => {
    await ensureTicketAcknowledged(ticket, isAssigned, ticketId, reload);
  }, [ticket, isAssigned, ticketId, reload]);

  // ── Mutations ────────────────────────────────────────────────────────────────
  const performSimpleAction = useCallback(async (
    actionType: string,
    extra?: Record<string, string>,
  ) => {
    setActionNotice(null);
    setSubmitting(true);
    try {
      if (actionType !== "ACKNOWLEDGE") await ensureAcknowledged();
      await performAction(ticketId, { action_type: actionType, ...(extra ?? {}) });
      await reload();
    } catch (e) {
      console.error("Action failed", e);
      setActionNotice(formatUserFacingError(e));
    } finally {
      setSubmitting(false);
    }
  }, [ticketId, reload, ensureAcknowledged]);

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
    setActionNotice(null);
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
      await reload();
    } catch (e) {
      console.error("Escalation failed", e);
      setActionNotice(formatUserFacingError(e));
      throw e;
    } finally {
      setSubmitting(false);
    }
  }, [ticketId, reload, ensureAcknowledged]);

  const openResolveFlow = useCallback(() => {
    if (!hasImages) {
      setActionNotice({ message: MSG_IMAGE_BEFORE_RESOLVE, kind: "validation" });
      return;
    }
    setResolutionOpen(true);
  }, [hasImages]);

  const submitResolve = useCallback(async (category: ResolutionCategoryCode, note: string) => {
    setActionNotice(null);
    setSubmitting(true);
    try {
      await ensureAcknowledged();
      await performAction(ticketId, {
        action_type: "RESOLVE",
        resolution_category: category,
        note,
      });
      setResolutionOpen(false);
      await reload();
    } catch (e) {
      console.error("Resolve failed", e);
      setActionNotice(formatUserFacingError(e));
    } finally {
      setSubmitting(false);
    }
  }, [ticketId, reload, ensureAcknowledged]);

  const submitReassignment = useCallback(async (reasonCode: ReassignmentReasonCode, notes: string) => {
    setActionNotice(null);
    setSubmitting(true);
    try {
      await performAction(ticketId, {
        action_type: "REASSIGNMENT_REQUESTED",
        reassignment_reason_code: reasonCode,
        reassignment_notes: notes,
      });
      setReassignOpen(false);
      await reload();
    } catch (e) {
      setActionNotice(formatUserFacingError(e));
      throw e;
    } finally {
      setSubmitting(false);
    }
  }, [ticketId, reload]);

  const submitCallReport = useCallback(async (data: CallReportFormData) => {
    setActionNotice(null);
    setSubmitting(true);
    try {
      await ensureAcknowledged();
      await performAction(ticketId, {
        action_type: "NOTE",
        note: formatCallReportNote(data),
        is_call_report: true,
      });
      setCallReportOpen(false);
      await reload();
    } catch (e) {
      setActionNotice(formatUserFacingError(e));
      throw e;
    } finally {
      setSubmitting(false);
    }
  }, [ticketId, reload, ensureAcknowledged]);

  // Compose-bar submit: routes `#inspect` / `#assign` / plain note.
  // H2-06 deviation (drift #2): parse the command from the captured text BEFORE
  // clearing the input (desktop order). The mobile copy cleared `noteText` first and
  // matched inside the try — functionally equivalent (both captured `text` first)
  // but the ticket calls out the desktop order as canonical, so the parse now runs
  // via `parseThreadCommand` before `setNoteText("")` for both pages.
  const submitNote = useCallback(async () => {
    const text = noteText.trim();
    if (!text || submitting) return;
    setSubmitting(true);

    const cmd = parseThreadCommand(text);
    setNoteText("");
    try {
      if (cmd.kind === "inspect") {
        const assignee = cmd.args.assignee ?? currentUserId;
        await createTask(ticketId, { task_type: "SITE_VISIT", assigned_to_user_id: assignee });
      } else if (cmd.kind === "assign") {
        if (!userCanAssign) {
          setActionNotice({ message: MSG_SUPERVISOR_ONLY_ASSIGN, kind: "validation" });
          setNoteText(text);
          return;
        }
        await patchTicket(ticketId, { assign_to_user_id: cmd.args.assignee });
      } else {
        await ensureAcknowledged();
        await performAction(ticketId, { action_type: "NOTE", note: text });
      }
      await reload();
      threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
    } catch (e) {
      console.error("Submit failed", e);
      setNoteText(text);
      setActionNotice(formatUserFacingError(e));
    } finally {
      setSubmitting(false);
    }
  }, [noteText, submitting, ticketId, reload, ensureAcknowledged, currentUserId, userCanAssign]);

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
      await performSimpleAction(cmd.action);
      return;
    }
    if (cmd.kind === "task" && cmd.taskKey) {
      // instant self-assign task
      try {
        await createTask(ticketId, { task_type: cmd.taskKey, assigned_to_user_id: currentUserId });
        await reload();
      } catch (e) { console.error("Create task failed", e); }
      return;
    }
    if (cmd.kind === "assign" && !userCanAssign) {
      setActionNotice({ message: MSG_SUPERVISOR_ONLY_ASSIGN, kind: "validation" });
    }
    // #assign / peer #reassign handled inline in ComposeBar (text becomes "#assign @…")
  }, [reassignMode, openEscalationFlow, performSimpleAction, ticketId, currentUserId, reload, userCanAssign]);

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
      await completeTask(ticketId, task.task_id);
      await reload();
    } catch (e) {
      console.error("Complete task failed", e);
      setActionNotice(formatUserFacingError(e, "task"));
    }
  }, [ticketId, reload, openFieldReport]);

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
      await reload();
      threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
    } catch (e) {
      console.error("Field report failed", e);
      setActionNotice(formatUserFacingError(e, "field_report"));
      throw e;
    } finally {
      fieldVisitSubmitLock.current = false;
      setFieldReportSubmitting(false);
    }
  }, [ticketId, fieldReportLinkedTask, reload, ensureAcknowledged, closeFieldReport]);

  const handleAttachFile = useCallback(async (file: File) => {
    setAttachUploading(true);
    setActionNotice(null);
    try {
      await ensureAcknowledged();
      await uploadOfficerAttachment(ticketId, file, "");
      await refreshFiles();
      await reload();
    } catch (e) {
      console.error("Upload failed", e);
      setActionNotice(formatUserFacingError(e, "upload"));
    } finally {
      setAttachUploading(false);
    }
  }, [ensureAcknowledged, ticketId, reload, refreshFiles]);

  return {
    ticket, sla, tasks, loading, error, errorIsNotFound, rosterIds,
    activeFilter, setActiveFilter, noteText, setNoteText, submitting,
    actionNotice, setActionNotice, threadEndRef,
    escalationOpen, setEscalationOpen, resolutionOpen, setResolutionOpen,
    reassignOpen, setReassignOpen, callReportOpen, setCallReportOpen,
    fieldReportOpen, fieldReportLinkedTask, fieldReportSubmitting, attachUploading,
    currentUserId, isAssigned, viewerIds, viewerTiers, filteredEvents,
    mentionParticipants, pendingTaskCount, hasResolutionRecord,
    canManageViewers, userCanAssign, userCanSupervisorAssign, reassignMode,
    reload, ensureAcknowledged, performSimpleAction,
    openEscalationFlow, submitEscalation, openResolveFlow, submitResolve,
    submitReassignment, submitCallReport, submitNote, handleHashCommand,
    handleCompleteTask, openFieldReport, closeFieldReport, submitFieldReportForm,
    handleAttachFile,
  };
}
