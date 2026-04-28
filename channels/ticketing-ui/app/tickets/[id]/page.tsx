"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getTicket, getSla, performAction, markSeen, replyToComplainant, getGrievancePii,
  listTicketFiles, getFileDownloadUrl, listOfficers, patchTicket,
  listOfficerAttachments, getOfficerAttachmentUrl, uploadOfficerAttachment,
  getTeammates, generateFindings, listTicketTasks, completeTask,
  type TicketDetail, type SlaStatus, type GrievancePii, type TicketFile,
  type OfficerBrief, type OfficerAttachment, type RevealSession, type TicketTask, type TicketEvent,
} from "@/lib/api";
import { useAuth } from "@/app/providers/AuthProvider";
import { RevealModal, RevealOverlay } from "@/components/ui/VaultReveal";
import { StatusBadge, PriorityBadge, SeahBadge } from "@/components/ui/Badge";

import { NoteBubble }                        from "@/components/thread/NoteBubble";
import { SystemPill }                         from "@/components/thread/SystemPill";
import { TaskCard, AssignTaskSheet }          from "@/components/thread/TaskCard";
import { FilterChips, type FilterChip }       from "@/components/thread/FilterChips";
import { ViewersBar }                         from "@/components/thread/ViewersBar";
import { ComposeBar }                         from "@/components/thread/ComposeBar";
import { SlaSubHeader }                       from "@/components/thread/SlaSubHeader";
import {
  SYSTEM_EVENT_TYPES, TASK_EVENT_TYPES, NOTIFICATION_ONLY_EVENT_TYPES,
} from "@/lib/mobile-constants";

// ── Workflow mini-stepper (desktop variant — horizontal, wider nodes) ──────────

const STEP_LABELS: Record<string, string> = {
  LEVEL_1_SITE:            "L1 Site",
  LEVEL_2_PIU:             "L2 PIU",
  LEVEL_3_GRC:             "L3 GRC",
  LEVEL_4_LEGAL:           "L4 Legal",
  SEAH_LEVEL_1_NATIONAL:   "L1 National",
  SEAH_LEVEL_2_HQ:         "L2 HQ",
};

function WorkflowStepper({ currentStepKey }: { currentStepKey: string }) {
  const isSeah = currentStepKey.startsWith("SEAH");
  const steps = isSeah
    ? ["SEAH_LEVEL_1_NATIONAL", "SEAH_LEVEL_2_HQ"]
    : ["LEVEL_1_SITE", "LEVEL_2_PIU", "LEVEL_3_GRC", "LEVEL_4_LEGAL"];
  const currentIdx = steps.indexOf(currentStepKey);

  return (
    <div className="flex items-center gap-1 mt-2">
      {steps.map((s, i) => {
        const done   = i < currentIdx;
        const active = i === currentIdx;
        return (
          <div key={s} className="flex items-center gap-1 flex-1">
            <div className={`flex-1 h-1 rounded ${done ? "bg-blue-500" : active ? "bg-blue-300" : "bg-gray-200"}`} />
            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
              done   ? "bg-blue-500 text-white" :
              active ? "bg-blue-600 text-white ring-2 ring-blue-300" :
                       "bg-gray-200 text-gray-500"
            }`}>
              {i + 1}
            </div>
            {i === steps.length - 1 && <div className="flex-1 h-1 rounded bg-gray-200" />}
          </div>
        );
      })}
      <div className="flex justify-between w-full mt-1 absolute" style={{ display: "none" }} />
    </div>
  );
}

// ── Translation review panel ───────────────────────────────────────────────────

function TranslationPanel({ events, onClose }: { events: TicketDetail["events"]; onClose: () => void }) {
  const notes = [...events]
    .filter((e) => e.event_type === "NOTE_ADDED" && e.note)
    .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());

  return (
    <div className="w-80 shrink-0 flex flex-col border-l border-gray-200 bg-gray-50 overflow-y-auto" style={{ minHeight: 0 }}>
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-white sticky top-0 z-10">
        <span className="text-sm font-semibold text-blue-700">🌐 Translation Review</span>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">×</button>
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
                  ? <div className="text-xs text-amber-600">⟳ Translation pending</div>
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

// ── File attachments panel ────────────────────────────────────────────────────

function FilesPanel({ ticketId, onBeforeDownload, isAssigned, onUpload }: {
  ticketId: string;
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
  useEffect(() => { loadFiles(); }, [ticketId]); // eslint-disable-line react-hooks/exhaustive-deps

  const fmt = (bytes: number) =>
    bytes < 1024 ? `${bytes} B` : bytes < 1024 ** 2 ? `${(bytes / 1024).toFixed(0)} KB` : `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  const icon = (type: string | null) => type === "image" ? "🖼️" : type === "pdf" ? "📄" : "📎";

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
      setUploadError(String(e));
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
      <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide">Attachments</h2>

      <div>
        <div className="text-xs font-medium text-gray-400 mb-1.5">From complainant</div>
        {loading ? <div className="text-xs text-gray-400">Loading…</div>
          : complainantFiles.length === 0
            ? <div className="text-xs text-gray-400 italic">No files uploaded by complainant.</div>
            : complainantFiles.map((f) => (
              <button key={f.file_id}
                onClick={async () => { await onBeforeDownload(); window.open(getFileDownloadUrl(f.file_id), "_blank", "noopener,noreferrer"); }}
                className="flex items-center gap-2 text-xs text-blue-600 hover:text-blue-800 group w-full text-left mb-1"
              >
                <span>{icon(f.file_type)}</span>
                <span className="flex-1 truncate group-hover:underline">{f.file_name}</span>
                <span className="text-gray-400 shrink-0">{fmt(f.file_size)}</span>
              </button>
            ))
        }
      </div>

      <div>
        <div className="text-xs font-medium text-gray-400 mb-1.5">Officer attachments</div>
        {officerFiles.length === 0
          ? <div className="text-xs text-gray-400 italic">No officer files attached yet.</div>
          : officerFiles.map((f) => (
            <div key={f.file_id} className="flex items-start gap-2 mb-1">
              <button
                onClick={() => window.open(getOfficerAttachmentUrl(f.file_id), "_blank", "noopener,noreferrer")}
                className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-800 group shrink-0"
              >
                <span>{icon(f.file_type)}</span>
                <span className="group-hover:underline max-w-[120px] truncate">{f.file_name}</span>
                <span className="text-gray-400">{fmt(f.file_size)}</span>
              </button>
              {f.caption && <span className="text-xs text-gray-500 italic flex-1 min-w-0 truncate">{f.caption}</span>}
            </div>
          ))
        }
      </div>

      {isAssigned && (
        <div className="border-t border-gray-100 pt-3 space-y-2">
          <div className="text-xs font-medium text-gray-500">Attach a document</div>
          <input type="file" onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)} className="text-xs text-gray-600 w-full" />
          <input type="text" value={caption} onChange={(e) => setCaption(e.target.value)}
            placeholder="Caption (optional)…"
            className="w-full text-xs border border-gray-200 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
          {uploadError && <div className="text-xs text-red-500">{uploadError}</div>}
          <button onClick={handleUpload} disabled={!selectedFile || uploading}
            className="w-full text-xs bg-gray-100 text-gray-700 hover:bg-gray-200 rounded px-2 py-1.5 disabled:opacity-50 transition font-medium"
          >
            {uploading ? "Uploading…" : "📎 Upload"}
          </button>
        </div>
      )}
    </div>
  );
}

// ── Complainant card ───────────────────────────────────────────────────────────

function ComplainantCard({ ticket, onRevealOriginal }: {
  ticket: TicketDetail;
  onRevealOriginal: () => void;
}) {
  const [pii, setPii]               = useState<GrievancePii | null>(null);
  const [piiLoading, setPiiLoading] = useState(false);
  const [piiError, setPiiError]     = useState<string | null>(null);
  const [phoneRevealed, setPhoneRevealed]   = useState(false);
  const [phoneRevealing, setPhoneRevealing] = useState(false);

  useEffect(() => {
    setPiiLoading(true);
    getGrievancePii(ticket.ticket_id)
      .then(setPii)
      .catch(() => setPiiError("Could not load complainant details"))
      .finally(() => setPiiLoading(false));
  }, [ticket.ticket_id]);

  async function handlePhoneReveal() {
    setPhoneRevealing(true);
    await performAction(ticket.ticket_id, { action_type: "REVEAL_CONTACT" }).catch(() => {});
    setPhoneRevealed(true);
    setPhoneRevealing(false);
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">Complainant</h2>
      {piiLoading ? (
        <div className="text-xs text-gray-400">Loading…</div>
      ) : piiError ? (
        <div className="text-xs space-y-1 text-gray-600">
          <div><span className="text-gray-400">Ref:</span> {ticket.complainant_id ?? "—"}</div>
          <div className="text-xs text-gray-400 italic">{piiError}</div>
        </div>
      ) : (
        <div className="text-xs space-y-1.5 text-gray-700">
          {pii?.complainant_name && <div><span className="text-gray-400">Name:</span> {pii.complainant_name}</div>}
          <div><span className="text-gray-400">Ref:</span> {ticket.complainant_id ?? "—"}</div>
          <div className="flex items-center gap-1.5">
            <span className="text-gray-400">Phone:</span>
            {phoneRevealed && pii?.phone_number ? (
              <span className="font-mono">{pii.phone_number}</span>
            ) : (
              <>
                <span className="text-gray-300 font-mono">••••••••</span>
                <button onClick={handlePhoneReveal} disabled={phoneRevealing}
                  className="text-blue-500 hover:text-blue-700 underline text-xs ml-0.5 disabled:opacity-50"
                >
                  {phoneRevealing ? "…" : "Reveal"}
                </button>
              </>
            )}
          </div>
          {pii?.email && <div><span className="text-gray-400">Email:</span> {pii.email}</div>}
          <div>
            <span className="text-gray-400">Session:</span>{" "}
            {ticket.session_id
              ? <span className="text-green-600">✅ Active</span>
              : <span className="text-red-500">❌ Expired — SMS fallback</span>}
          </div>
          {ticket.grievance_id && (
            <div className="border-t border-gray-100 pt-2 mt-1">
              <button onClick={onRevealOriginal}
                className="text-xs text-red-700 hover:text-red-900 underline flex items-center gap-1"
              >
                📄 Reveal original statement
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── AI findings card ──────────────────────────────────────────────────────────

const FINDINGS_ROLES = new Set([
  "grc_chair", "adb_hq_safeguards", "adb_hq_project", "adb_hq_exec",
  "adb_national_project_director", "super_admin", "local_admin",
]);

function FindingsCard({ ticket, roleKeys, onRefresh }: {
  ticket: TicketDetail;
  roleKeys: string[];
  onRefresh: () => void;
}) {
  const canView = roleKeys.some((r) => FINDINGS_ROLES.has(r));
  const [regenerating, setRegenerating] = useState(false);
  const [queuedMsg, setQueuedMsg]       = useState<string | null>(null);

  if (!canView) return null;

  async function handleRegenerate() {
    setRegenerating(true);
    setQueuedMsg(null);
    try {
      await generateFindings(ticket.ticket_id);
      setQueuedMsg("Generation queued — this may take up to 30 s. Refresh to see the updated summary.");
    } catch (e) {
      setQueuedMsg(`Error: ${String(e)}`);
    } finally {
      setRegenerating(false);
    }
  }

  return (
    <div className="bg-white rounded-lg border border-blue-200 p-4">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-semibold text-blue-700 uppercase tracking-wide">🧠 Findings</h2>
        <button onClick={handleRegenerate} disabled={regenerating}
          className="text-xs text-blue-500 hover:text-blue-700 disabled:opacity-50 underline"
        >
          {regenerating ? "Queuing…" : "↻ Regenerate"}
        </button>
      </div>
      {queuedMsg && <div className="text-xs text-blue-600 bg-blue-50 rounded px-2 py-1.5 mb-2">{queuedMsg}</div>}
      {ticket.ai_summary_en ? (
        <>
          <p className="text-sm text-gray-700 leading-relaxed">{ticket.ai_summary_en}</p>
          {ticket.ai_summary_updated_at && (
            <p className="text-xs text-gray-400 mt-2">
              Last generated {new Date(ticket.ai_summary_updated_at).toLocaleString()}
            </p>
          )}
        </>
      ) : (
        <p className="text-xs text-gray-400 italic">
          No summary yet. Click ↻ Regenerate to generate one.
        </p>
      )}
    </div>
  );
}

// ── Top-right actions card ────────────────────────────────────────────────────

function ActionsCard({ ticket, roleKeys, onRefresh, ensureAcknowledged, isAssigned }: {
  ticket: TicketDetail;
  roleKeys: string[];
  onRefresh: () => void;
  ensureAcknowledged: () => Promise<void>;
  isAssigned: boolean;
}) {
  const [replyText, setReplyText]   = useState("");
  const [loading, setLoading]       = useState(false);
  const [grcHearingDate, setGrcHearingDate] = useState("");
  const [grcDecision, setGrcDecision] = useState<"RESOLVED" | "ESCALATE_TO_LEGAL">("RESOLVED");
  const [showAssignTask, setShowAssignTask] = useState(false);

  // Officers for assign dropdown
  const [officers, setOfficers]     = useState<OfficerBrief[]>([]);
  const [teammates, setTeammates]   = useState<string[]>([]);
  const [assignSelected, setAssignSelected] = useState(ticket.assigned_to_user_id ?? "");
  const [reassignSelected, setReassignSelected] = useState("");
  const [savingAssign, setSavingAssign]     = useState(false);
  const [savingReassign, setSavingReassign] = useState(false);
  const [reassignDone, setReassignDone]     = useState(false);

  useEffect(() => { listOfficers().then(setOfficers).catch(() => {}); }, []);
  useEffect(() => {
    getTeammates(ticket.ticket_id).then((r) => setTeammates(r.teammates)).catch(() => {});
  }, [ticket.ticket_id]);

  const status    = ticket.status_code;
  const stepKey   = ticket.current_step?.step_key ?? "";
  const isGrcChair = roleKeys.includes("grc_chair") || roleKeys.includes("super_admin");
  const isClosed   = ["RESOLVED", "CLOSED"].includes(status);
  const isEscalated = status === "ESCALATED";

  async function act(action_type: string, extra?: Record<string, string>) {
    setLoading(true);
    try {
      if (action_type !== "ACKNOWLEDGE") await ensureAcknowledged();
      await performAction(ticket.ticket_id, { action_type, ...extra });
      onRefresh();
    } catch (e) { alert(String(e)); }
    finally { setLoading(false); }
  }

  async function sendReply() {
    if (!replyText.trim()) return;
    setLoading(true);
    try {
      await ensureAcknowledged();
      await replyToComplainant(ticket.ticket_id, replyText);
      setReplyText("");
      onRefresh();
    } catch (e) { alert(String(e)); }
    finally { setLoading(false); }
  }

  async function handleAssign() {
    if (!assignSelected || assignSelected === ticket.assigned_to_user_id) return;
    setSavingAssign(true);
    try { await patchTicket(ticket.ticket_id, { assign_to_user_id: assignSelected }); onRefresh(); }
    catch (e) { alert(String(e)); }
    finally { setSavingAssign(false); }
  }

  async function handleReassign() {
    if (!reassignSelected) return;
    setSavingReassign(true);
    try {
      await patchTicket(ticket.ticket_id, { assign_to_user_id: reassignSelected });
      setReassignDone(true);
      setReassignSelected("");
      onRefresh();
      setTimeout(() => setReassignDone(false), 2000);
    } catch (e) { alert(String(e)); }
    finally { setSavingReassign(false); }
  }

  const btn = "px-3 py-1.5 rounded text-sm font-medium transition disabled:opacity-50";

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
      <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide">Actions</h2>

      {!isAssigned && (
        <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
          This ticket is assigned to another officer. You can add notes but cannot change its status.
        </div>
      )}

      {/* Status-change actions — assigned officer only */}
      {isAssigned && (
        <div className="flex flex-wrap gap-2">
          {(status === "OPEN" || isEscalated) && (
            <button onClick={() => act("ACKNOWLEDGE")} disabled={loading}
              className={`${btn} bg-blue-600 text-white hover:bg-blue-700`}>
              ✅ Acknowledge
            </button>
          )}
          {!isClosed && !isEscalated && (
            <button onClick={() => act("ESCALATE")} disabled={loading}
              className={`${btn} bg-orange-500 text-white hover:bg-orange-600`}>
              🔺 Escalate
            </button>
          )}
          {!isClosed && !isEscalated && (
            <button onClick={() => act("RESOLVE")} disabled={loading}
              className={`${btn} bg-green-600 text-white hover:bg-green-700`}>
              🏁 Resolve
            </button>
          )}
          {!isClosed && !isEscalated && (
            <button onClick={() => act("CLOSE")} disabled={loading}
              className={`${btn} bg-gray-400 text-white hover:bg-gray-500`}>
              Close
            </button>
          )}
          <button onClick={() => setShowAssignTask(true)}
            className={`${btn} bg-amber-50 text-amber-700 border border-amber-300 hover:bg-amber-100`}>
            📋 Assign task
          </button>

          {/* GRC Convene */}
          {isGrcChair && stepKey === "LEVEL_3_GRC" && !isEscalated && status !== "GRC_HEARING_SCHEDULED" && (
            <div className="flex gap-2 items-center w-full mt-1">
              <input type="date" value={grcHearingDate} onChange={(e) => setGrcHearingDate(e.target.value)}
                className="text-sm border border-gray-300 rounded px-2 py-1.5" />
              <button onClick={() => act("GRC_CONVENE", { grc_hearing_date: grcHearingDate })} disabled={loading}
                className={`${btn} bg-purple-600 text-white hover:bg-purple-700`}>
                🏛️ Convene GRC
              </button>
            </div>
          )}

          {/* GRC Decide */}
          {isGrcChair && status === "GRC_HEARING_SCHEDULED" && (
            <div className="flex gap-2 items-center w-full mt-1">
              <select value={grcDecision} onChange={(e) => setGrcDecision(e.target.value as typeof grcDecision)}
                className="text-sm border border-gray-300 rounded px-2 py-1.5">
                <option value="RESOLVED">Decision: Resolved</option>
                <option value="ESCALATE_TO_LEGAL">Decision: Escalate to Legal</option>
              </select>
              <button onClick={() => act("GRC_DECIDE", { grc_decision: grcDecision })} disabled={loading}
                className={`${btn} bg-purple-700 text-white hover:bg-purple-800`}>
                ⚖️ Record Decision
              </button>
            </div>
          )}
        </div>
      )}

      {/* Reply to complainant */}
      {isAssigned && (
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Reply to Complainant 💬</label>
          <textarea value={replyText} onChange={(e) => setReplyText(e.target.value)} rows={2}
            placeholder="Message sent via chatbot (SMS fallback if session expired)…"
            className="w-full text-sm border border-gray-200 rounded px-3 py-2 resize-none focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
          <button onClick={sendReply} disabled={!replyText.trim() || loading}
            className={`mt-1 ${btn} bg-blue-50 text-blue-700 hover:bg-blue-100`}>
            Send Reply
          </button>
        </div>
      )}

      {/* Assign officer */}
      <div className="border-t border-gray-100 pt-3">
        <div className="text-xs font-medium text-gray-500 mb-2">Assign officer</div>
        <div className="flex gap-2">
          <select value={assignSelected} onChange={(e) => setAssignSelected(e.target.value)}
            className="flex-1 text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400">
            <option value="">— Unassigned —</option>
            {officers.map((o) => (
              <option key={o.user_id} value={o.user_id}>
                {o.user_id}{o.role_keys.length > 0 ? ` (${o.role_keys[0].replace(/_/g, " ")})` : ""}
              </option>
            ))}
          </select>
          {assignSelected !== (ticket.assigned_to_user_id ?? "") && (
            <button onClick={handleAssign} disabled={savingAssign}
              className="text-xs bg-blue-600 text-white rounded px-3 py-1.5 hover:bg-blue-700 disabled:opacity-50 transition">
              {savingAssign ? "Saving…" : "Save"}
            </button>
          )}
        </div>
      </div>

      {/* Reassign to teammate */}
      {teammates.length > 0 && (
        <div>
          <div className="text-xs font-medium text-gray-500 mb-2">Reassign to teammate</div>
          <div className="flex gap-2">
            <select value={reassignSelected} onChange={(e) => setReassignSelected(e.target.value)}
              className="flex-1 text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none">
              <option value="">— Select colleague —</option>
              {teammates.map((uid) => <option key={uid} value={uid}>{uid}</option>)}
            </select>
            {reassignSelected && (
              <button onClick={handleReassign} disabled={savingReassign}
                className="text-xs bg-slate-600 text-white rounded px-3 py-1.5 hover:bg-slate-700 disabled:opacity-50 transition">
                {savingReassign ? "…" : reassignDone ? "✓ Done" : "Reassign"}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Assign task modal */}
      {showAssignTask && (
        <AssignTaskSheet
          ticketId={ticket.ticket_id}
          variant="modal"
          onClose={() => setShowAssignTask(false)}
          onAssigned={() => { setShowAssignTask(false); onRefresh(); }}
        />
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function TicketDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user, roleKeys, canSeeSeah, isAdmin, effectiveLang } = useAuth();

  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [sla, setSla]       = useState<SlaStatus | null>(null);
  const [tasks, setTasks]   = useState<TicketTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState<string | null>(null);

  // Thread state
  const [activeFilter, setActiveFilter] = useState<FilterChip>("all");
  const [noteText, setNoteText]         = useState("");
  const [submitting, setSubmitting]     = useState(false);
  const threadEndRef = useRef<HTMLDivElement>(null);

  // Translation panel
  const PANEL_KEY = "grm_translation_panel_open";
  const [panelOpen, setPanelOpen] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(PANEL_KEY) === "true";
  });
  function togglePanel() {
    setPanelOpen((prev) => { const next = !prev; localStorage.setItem(PANEL_KEY, String(next)); return next; });
  }
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

  // Vault reveal
  const [revealModalOpen, setRevealModalOpen] = useState(false);
  const [revealSession, setRevealSession]     = useState<RevealSession | null>(null);

  const showTranslations = effectiveLang !== "ne";

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
      markSeen(id).catch(() => {});
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const isAssigned = isAdmin || !ticket?.assigned_to_user_id || ticket?.assigned_to_user_id === user?.sub;

  async function ensureAcknowledged() {
    if (!ticket || !["OPEN", "ESCALATED"].includes(ticket.status_code)) return;
    if (!isAssigned) return;
    await performAction(id, { action_type: "ACKNOWLEDGE" });
    await load();
  }

  // ── Thread derived state ─────────────────────────────────────────────────

  const filteredEvents = useMemo(() => {
    if (!ticket) return [];
    switch (activeFilter) {
      case "all":    return ticket.events;
      case "mine":   return ticket.events.filter((e) => e.created_by_user_id === (user?.sub ?? "mock-super-admin"));
      case "tasks":  return ticket.events.filter((e) => TASK_EVENT_TYPES.has(e.event_type));
      case "system": return ticket.events.filter((e) => SYSTEM_EVENT_TYPES.has(e.event_type));
      default:       return ticket.events.filter((e) => e.created_by_user_id === activeFilter);
    }
  }, [ticket, activeFilter, user]);

  const pendingTaskCount = useMemo(() => tasks.filter((t) => t.status === "PENDING").length, [tasks]);
  const currentUserId    = user?.sub ?? "mock-super-admin";

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
    const list = Array.from(ids).map((id_) => ({ user_id: id_, label: `@${id_}` }));
    list.unshift({ user_id: "all", label: "@all" });
    return list;
  }, [ticket, currentUserId]);

  const handleNote = useCallback(async () => {
    if (!noteText.trim() || submitting) return;
    setSubmitting(true);
    const text = noteText.trim();
    setNoteText("");
    try {
      await performAction(id, { action_type: "NOTE", note: text });
      await load();
      threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
    } catch (e) {
      console.error("Note failed", e);
      setNoteText(text);
    } finally {
      setSubmitting(false);
    }
  }, [noteText, submitting, id, load]);

  const handleCompleteTask = useCallback(async (taskId: string) => {
    try { await completeTask(id, taskId); await load(); }
    catch (e) { console.error("Complete task failed", e); }
  }, [id, load]);

  // ── Render ───────────────────────────────────────────────────────────────

  if (loading) return (
    <div className="flex items-center justify-center h-full min-h-[200px]">
      <div className="text-sm text-gray-400 animate-pulse">Loading…</div>
    </div>
  );
  if (error) return (
    <div className="flex flex-col items-center gap-3 py-16 text-sm text-gray-500">
      <span className="text-3xl">⚠️</span><span>{error}</span>
      <button onClick={load} className="text-blue-600">Retry</button>
    </div>
  );
  if (!ticket) return null;
  if (ticket.is_seah && !canSeeSeah) return <div className="p-8 text-red-500 text-sm">Access denied.</div>;

  return (
    <div className="p-6 space-y-5">
      {/* Back */}
      <button onClick={() => router.back()} className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1">
        ← Back to queue
      </button>

      {/* ── TOP ROW: ticket header + actions ────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Ticket header */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <h1 className="text-xl font-semibold text-gray-800">{ticket.grievance_id}</h1>
            {ticket.is_seah && <SeahBadge />}
            <StatusBadge code={ticket.status_code} />
            <PriorityBadge priority={ticket.priority} />
          </div>
          <p className="text-sm text-gray-500">
            {ticket.organization_id} · {ticket.location_code} · {ticket.project_code}
          </p>
          <p className="text-xs text-gray-400 mt-1">
            Created {new Date(ticket.created_at).toLocaleDateString()}
          </p>
          {/* SLA strip */}
          {sla && (
            <div className={`mt-3 text-xs px-3 py-2 rounded ${
              sla.breached ? "bg-red-50 text-red-700" :
              sla.urgency === "warning" ? "bg-yellow-50 text-yellow-700" :
              sla.urgency !== "none" ? "bg-green-50 text-green-700" : "bg-gray-50 text-gray-500"
            }`}>
              ⏱ {sla.resolution_time_days}d resolution target
              {sla.deadline ? ` · Deadline ${new Date(sla.deadline).toLocaleDateString()}` : ""}
              {sla.remaining_hours != null
                ? ` · ${sla.remaining_hours < 24 ? `${Math.round(sla.remaining_hours)}h left` : `${Math.round(sla.remaining_hours / 24)}d left`}`
                : ""}
            </div>
          )}
          {/* Workflow stepper */}
          {ticket.current_step && (
            <div className="mt-3">
              <div className="text-xs text-gray-500 mb-1">
                {ticket.current_step.display_name}
                <span className="text-gray-400"> · {ticket.current_step.assigned_role_key.replace(/_/g, " ")}</span>
              </div>
              <WorkflowStepper currentStepKey={ticket.current_step.step_key} />
            </div>
          )}
        </div>

        {/* Actions card */}
        <ActionsCard
          ticket={ticket}
          roleKeys={roleKeys}
          onRefresh={load}
          ensureAcknowledged={ensureAcknowledged}
          isAssigned={isAssigned}
        />
      </div>

      {/* ── MAIN AREA: thread (left) + info (right) ─────────────────── */}
      <div className="flex gap-0 items-start">

        {/* Left — thread */}
        <div className="flex-1 min-w-0 lg:mr-5">
          <div className="bg-white rounded-lg border border-gray-200 flex flex-col" style={{ height: "60vh" }}>
            {/* Thread header */}
            <div className="flex-shrink-0 border-b border-gray-200">
              <div className="flex items-center justify-between px-4 py-3">
                <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide">Case Thread</h2>
                <button
                  onClick={togglePanel}
                  className={`text-xs px-2 py-1 rounded border transition ${
                    panelOpen
                      ? "bg-blue-100 border-blue-300 text-blue-700"
                      : "bg-gray-50 border-gray-200 text-gray-500 hover:border-blue-300 hover:text-blue-600"
                  }`}
                >
                  🌐 {panelOpen ? "Hide translations" : "Translations"}
                </button>
              </div>
              <FilterChips
                events={ticket.events}
                currentUserId={currentUserId}
                active={activeFilter}
                pendingTaskCount={pendingTaskCount}
                onChange={setActiveFilter}
              />
              <ViewersBar
                viewers={ticket.viewers ?? []}
                canManage={canManageViewers}
                ticketId={ticket.ticket_id}
                onChanged={load}
              />
            </div>

            {/* Scrollable thread body */}
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
                          ticketId={ticket.ticket_id}
                          onComplete={handleCompleteTask}
                        />
                      );
                    return <NoteBubble key={event.event_id} event={event} isMine={isMine} />;
                  })
              )}
              <div ref={threadEndRef} />
            </div>

            {/* Compose bar */}
            <div className="flex-shrink-0 border-t border-gray-200">
              <ComposeBar
                value={noteText}
                onChange={setNoteText}
                onSubmit={handleNote}
                disabled={submitting}
                participants={mentionParticipants}
                placeholder="Add an internal note… (type @ to mention)"
              />
            </div>
          </div>
        </div>

        {/* Right — info column */}
        <div className="w-80 shrink-0 space-y-4">
          {/* Original Grievance */}
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">Original Grievance</h2>
            <p className="text-sm text-gray-700 leading-relaxed">
              {ticket.grievance_summary ?? <span className="text-gray-400">No summary</span>}
            </p>
            {ticket.grievance_categories && (
              <p className="text-xs text-gray-500 mt-2">
                <span className="font-medium">Categories:</span> {ticket.grievance_categories}
              </p>
            )}
            {ticket.grievance_location && (
              <p className="text-xs text-gray-500 mt-1">
                <span className="font-medium">Location:</span> {ticket.grievance_location}
              </p>
            )}
          </div>

          <FindingsCard ticket={ticket} roleKeys={roleKeys} onRefresh={load} />
          <ComplainantCard ticket={ticket} onRevealOriginal={() => setRevealModalOpen(true)} />
          <FilesPanel
            ticketId={ticket.ticket_id}
            onBeforeDownload={ensureAcknowledged}
            isAssigned={isAssigned}
            onUpload={load}
          />
        </div>

        {/* Translation panel (rightmost, collapsible) */}
        {panelOpen && (
          <div className="sticky top-6 self-start ml-4 hidden lg:block">
            <TranslationPanel
              events={ticket.events}
              onClose={() => { setPanelOpen(false); localStorage.setItem(PANEL_KEY, "false"); }}
            />
          </div>
        )}
      </div>

      {/* Vault reveal */}
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
    </div>
  );
}
