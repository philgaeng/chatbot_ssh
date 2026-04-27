"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getTicket, getSla, markSeen, performAction, replyToComplainant, getGrievancePii,
  listTicketFiles, getFileDownloadUrl, listOfficers, patchTicket,
  listOfficerAttachments, getOfficerAttachmentUrl, uploadOfficerAttachment,
  getTeammates, generateFindings, revealOriginal,
  type TicketDetail, type SlaStatus, type GrievancePii, type TicketFile,
  type OfficerBrief, type OfficerAttachment, type RevealSession,
} from "@/lib/api";
import { useAuth } from "@/app/providers/AuthProvider";
import { RevealModal, RevealOverlay } from "@/components/ui/VaultReveal";
import { StatusBadge, PriorityBadge, SeahBadge } from "@/components/ui/Badge";
import { SlaCountdown } from "@/components/ui/SlaCountdown";

// ── Workflow level stepper ────────────────────────────────────────────────────

const STEP_LABELS: Record<string, string> = {
  LEVEL_1_SITE:        "L1 Site",
  LEVEL_2_PIU:         "L2 PIU",
  LEVEL_3_GRC:         "L3 GRC",
  LEVEL_4_LEGAL:       "L4 Legal",
  SEAH_LEVEL_1_NATIONAL: "L1 National",
  SEAH_LEVEL_2_HQ:       "L2 HQ",
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
        const done = i < currentIdx;
        const active = i === currentIdx;
        return (
          <div key={s} className="flex items-center gap-1 flex-1">
            <div className={`flex-1 h-1 rounded ${done ? "bg-blue-500" : active ? "bg-blue-300" : "bg-gray-200"}`} />
            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
              done ? "bg-blue-500 text-white" : active ? "bg-blue-600 text-white ring-2 ring-blue-300" : "bg-gray-200 text-gray-500"
            }`}>
              {i + 1}
            </div>
            {i === steps.length - 1 && <div className="flex-1 h-1 rounded bg-gray-200" />}
          </div>
        );
      })}
    </div>
  );
}

// ── Event timeline ────────────────────────────────────────────────────────────

const EVENT_ICON: Record<string, string> = {
  CREATED: "🎫", ACKNOWLEDGED: "✅", ESCALATED: "🔺", RESOLVED: "🏁",
  CLOSED: "🔒", NOTE_ADDED: "📝", REPLY_SENT: "💬", ASSIGNED: "👤",
  GRC_CONVENED: "🏛️", GRC_DECIDED: "⚖️", GRC_HEARING_NOTIFICATION: "🔔",
  COMPLAINANT_NOTIFIED: "📱", SLA_BREACH_FINAL_STEP: "⚠️",
};

function EventTimeline({
  events,
  showTranslations,
  onTogglePanel,
  panelOpen,
}: {
  events: TicketDetail["events"];
  /** True for English-first users — show inline translation chips */
  showTranslations: boolean;
  onTogglePanel: () => void;
  panelOpen: boolean;
}) {
  return (
    <div className="space-y-3">
      {[...events].reverse().map((e) => {
        const translationEn = (e.payload as Record<string, unknown> | null)?.translation_en as string | undefined;
        return (
          <div key={e.event_id} className="flex gap-3">
            <div className="shrink-0 w-7 h-7 rounded-full bg-gray-100 flex items-center justify-center text-sm">
              {EVENT_ICON[e.event_type] ?? "•"}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-baseline gap-2 flex-wrap">
                <span className="text-sm font-medium text-gray-700">
                  {e.event_type.replace(/_/g, " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase())}
                </span>
                {e.new_status_code && (
                  <span className="text-xs text-gray-400">→ {e.new_status_code}</span>
                )}
                <span className="text-xs text-gray-400 ml-auto">
                  {new Date(e.created_at).toLocaleString()}
                </span>
              </div>
              {e.note && (
                <div className={`mt-1 text-sm text-gray-600 ${e.event_type === "NOTE_ADDED" ? "italic" : ""}`}>
                  {e.event_type === "NOTE_ADDED" && (
                    <span className="text-xs text-gray-400 mr-1">🔒 Internal:</span>
                  )}
                  {e.note}
                </div>
              )}
              {/* Inline translation chip — only shown for English-first users (showTranslations=true) */}
              {showTranslations && e.event_type === "NOTE_ADDED" && translationEn && translationEn !== e.note && (
                <div className="mt-1.5 bg-blue-50 border border-blue-100 rounded px-2 py-1.5">
                  <span className="text-xs text-blue-500 font-medium mr-1.5">🌐 Translated</span>
                  <span className="text-sm text-blue-800 italic">{translationEn}</span>
                </div>
              )}
              {e.created_by_user_id && (
                <div className="text-xs text-gray-400 mt-0.5">by {e.created_by_user_id}</div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Translation review panel (collapsible right column) ───────────────────────
// Inspired by Arc sidebar / Cursor Explorer panel — toggled by a button in the
// timeline card header, persisted via localStorage. Shows original + translation
// side-by-side for bilingual officers to verify AI accuracy.

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
    <div
      className="w-80 shrink-0 flex flex-col border-l border-gray-200 bg-gray-50 overflow-y-auto"
      style={{ minHeight: 0 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-white sticky top-0 z-10">
        <span className="text-sm font-semibold text-blue-700">🌐 Translation Review</span>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 text-lg leading-none"
          title="Close panel (T)"
        >
          ×
        </button>
      </div>

      {/* Notes */}
      <div className="flex-1 p-3 space-y-4">
        {notes.length === 0 ? (
          <p className="text-xs text-gray-400 italic p-2">No notes in this case yet.</p>
        ) : (
          notes.map((e) => {
            const payload = e.payload as Record<string, unknown> | null;
            const translationEn = payload?.translation_en as string | undefined;
            const isSameAsOriginal = translationEn === e.note;
            const isPending = !translationEn;

            return (
              <div key={e.event_id} className="space-y-1.5">
                {/* Meta */}
                <div className="text-xs text-gray-400">
                  {new Date(e.created_at).toLocaleDateString()} · {e.created_by_user_id ?? "—"}
                </div>

                {/* Original */}
                <div className="rounded border border-gray-200 bg-white p-2">
                  <div className="text-xs font-medium text-gray-400 mb-1">Original</div>
                  <div className="text-sm text-gray-700 italic">{e.note}</div>
                </div>

                {/* Translation */}
                <div className={`rounded border p-2 ${isPending ? "border-amber-200 bg-amber-50" : isSameAsOriginal ? "border-gray-200 bg-white" : "border-blue-100 bg-blue-50"}`}>
                  <div className="text-xs font-medium text-gray-400 mb-1">English</div>
                  {isPending ? (
                    <div className="text-xs text-amber-600">⟳ Translation pending</div>
                  ) : isSameAsOriginal ? (
                    <div className="text-xs text-gray-500">= Same (already English)</div>
                  ) : (
                    <div className="text-sm text-blue-800">{translationEn}</div>
                  )}
                </div>

                {/* Status chip */}
                {!isPending && !isSameAsOriginal && (
                  <div className="text-xs text-blue-500">✓ Translated by AI</div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Footer note */}
      <div className="px-3 py-2 border-t border-gray-100 text-xs text-gray-400">
        Translations are AI-generated. Bilingual officers may verify accuracy above.
      </div>
    </div>
  );
}

// ── File attachments panel ───────────────────────────────────────────────────

function FilesPanel({
  ticketId,
  onBeforeDownload,
  isAssigned,
  onUpload,
}: {
  ticketId: string;
  onBeforeDownload: () => Promise<void>;
  isAssigned: boolean;
  onUpload: () => void; // refresh parent timeline after upload
}) {
  // Complainant files (read-only, from public.file_attachments)
  const [complainantFiles, setComplainantFiles] = useState<TicketFile[]>([]);
  // Officer-uploaded files (from ticketing.ticket_files)
  const [officerFiles, setOfficerFiles] = useState<OfficerAttachment[]>([]);
  const [loading, setLoading] = useState(true);

  // Upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [caption, setCaption] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

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

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  const fileIcon = (type: string | null) =>
    type === "image" ? "🖼️" : type === "pdf" ? "📄" : "📎";

  async function handleComplainantDownload(fileId: string) {
    await onBeforeDownload();
    window.open(getFileDownloadUrl(fileId), "_blank", "noopener,noreferrer");
  }

  async function handleUpload() {
    if (!selectedFile) return;
    setUploading(true);
    setUploadError(null);
    try {
      await onBeforeDownload(); // auto-acknowledge if OPEN/ESCALATED
      await uploadOfficerAttachment(ticketId, selectedFile, caption);
      setSelectedFile(null);
      setCaption("");
      await loadFiles();
      onUpload(); // refresh timeline in parent
    } catch (e) {
      setUploadError(String(e));
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
      <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide">
        Attachments
      </h2>

      {/* Complainant files */}
      <div>
        <div className="text-xs font-medium text-gray-400 mb-1.5">From complainant</div>
        {loading ? (
          <div className="text-xs text-gray-400">Loading…</div>
        ) : complainantFiles.length === 0 ? (
          <div className="text-xs text-gray-400 italic">No files uploaded by complainant.</div>
        ) : (
          <div className="space-y-1.5">
            {complainantFiles.map((f) => (
              <button
                key={f.file_id}
                onClick={() => handleComplainantDownload(f.file_id)}
                className="flex items-center gap-2 text-xs text-blue-600 hover:text-blue-800 group w-full text-left"
              >
                <span>{fileIcon(f.file_type)}</span>
                <span className="flex-1 truncate group-hover:underline">{f.file_name}</span>
                <span className="text-gray-400 shrink-0">{formatSize(f.file_size)}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Officer-uploaded files */}
      <div>
        <div className="text-xs font-medium text-gray-400 mb-1.5">Officer attachments</div>
        {officerFiles.length === 0 ? (
          <div className="text-xs text-gray-400 italic">No officer files attached yet.</div>
        ) : (
          <div className="space-y-2">
            {officerFiles.map((f) => (
              <div key={f.file_id} className="flex items-start gap-2">
                <button
                  onClick={() => window.open(getOfficerAttachmentUrl(f.file_id), "_blank", "noopener,noreferrer")}
                  className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-800 group shrink-0"
                >
                  <span>{fileIcon(f.file_type)}</span>
                  <span className="group-hover:underline max-w-[120px] truncate">{f.file_name}</span>
                  <span className="text-gray-400">{formatSize(f.file_size)}</span>
                </button>
                {f.caption && (
                  <span className="text-xs text-gray-500 italic flex-1 min-w-0 truncate">{f.caption}</span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Upload form — assigned officer only */}
      {isAssigned && (
        <div className="border-t border-gray-100 pt-3 space-y-2">
          <div className="text-xs font-medium text-gray-500">Attach a document</div>
          <input
            type="file"
            onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
            className="text-xs text-gray-600 w-full"
          />
          <input
            type="text"
            value={caption}
            onChange={(e) => setCaption(e.target.value)}
            placeholder="Caption (optional)…"
            className="w-full text-xs border border-gray-200 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
          {uploadError && (
            <div className="text-xs text-red-500">{uploadError}</div>
          )}
          <button
            onClick={handleUpload}
            disabled={!selectedFile || uploading}
            className="w-full text-xs bg-gray-100 text-gray-700 hover:bg-gray-200 rounded px-2 py-1.5 disabled:opacity-50 transition font-medium"
          >
            {uploading ? "Uploading…" : "📎 Upload"}
          </button>
        </div>
      )}
    </div>
  );
}

// ── Assign to officer panel ───────────────────────────────────────────────────

function AssignPanel({ ticket, onRefresh }: { ticket: TicketDetail; onRefresh: () => void }) {
  const [officers, setOfficers] = useState<OfficerBrief[]>([]);
  const [selected, setSelected] = useState(ticket.assigned_to_user_id ?? "");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    listOfficers().then(setOfficers).catch(() => {});
  }, []);

  async function handleAssign() {
    if (!selected || selected === ticket.assigned_to_user_id) return;
    setSaving(true);
    try {
      await patchTicket(ticket.ticket_id, { assign_to_user_id: selected });
      onRefresh();
    } catch (e) {
      alert(String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
        Assignment
      </h2>
      <div className="space-y-2">
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
        >
          <option value="">— Unassigned —</option>
          {officers.map((o) => (
            <option key={o.user_id} value={o.user_id}>
              {o.user_id}{o.role_keys.length > 0 ? ` (${o.role_keys[0].replace(/_/g, " ")})` : ""}
            </option>
          ))}
        </select>
        {selected !== (ticket.assigned_to_user_id ?? "") && (
          <button
            onClick={handleAssign}
            disabled={saving}
            className="w-full text-xs bg-blue-600 text-white rounded px-2 py-1.5 hover:bg-blue-700 disabled:opacity-50 transition"
          >
            {saving ? "Saving…" : "Save assignment"}
          </button>
        )}
      </div>
    </div>
  );
}

// ── Reassign to teammate panel ─────────────────────────────────────────────────

function ReassignPanel({ ticket, onRefresh }: { ticket: TicketDetail; onRefresh: () => void }) {
  const [teammates, setTeammates] = useState<string[]>([]);
  const [selected, setSelected] = useState("");
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    getTeammates(ticket.ticket_id)
      .then((r) => setTeammates(r.teammates))
      .catch(() => setTeammates([]));
  }, [ticket.ticket_id]);

  if (teammates.length === 0) return null;

  async function handleReassign() {
    if (!selected) return;
    setSaving(true);
    try {
      await patchTicket(ticket.ticket_id, { assign_to_user_id: selected });
      setDone(true);
      setSelected("");
      onRefresh();
      setTimeout(() => setDone(false), 2000);
    } catch (e) {
      alert(String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
        Reassign to Teammate
      </h2>
      <div className="space-y-2">
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="w-full text-sm border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400"
        >
          <option value="">— Select colleague —</option>
          {teammates.map((uid) => (
            <option key={uid} value={uid}>{uid}</option>
          ))}
        </select>
        {selected && (
          <button
            onClick={handleReassign}
            disabled={saving}
            className="w-full text-xs bg-slate-600 text-white rounded px-2 py-1.5 hover:bg-slate-700 disabled:opacity-50 transition"
          >
            {saving ? "Reassigning…" : done ? "✓ Reassigned" : "Reassign ticket"}
          </button>
        )}
      </div>
      <p className="text-xs text-gray-400 mt-2">
        Only officers with the same role in this jurisdiction are shown.
      </p>
    </div>
  );
}


// ── Findings card (AI case summary — supervisor/GRC roles only) ──────────────

const FINDINGS_ROLES = new Set([
  "grc_chair", "adb_hq_safeguards", "adb_hq_project",
  "adb_hq_exec", "adb_national_project_director",
  "super_admin", "local_admin",
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
  if (!canView) return null;

  const [regenerating, setRegenerating] = useState(false);
  const [queuedMsg, setQueuedMsg] = useState<string | null>(null);

  async function handleRegenerate() {
    setRegenerating(true);
    setQueuedMsg(null);
    try {
      await generateFindings(ticket.ticket_id);
      setQueuedMsg(
        "Generation queued — this may take up to 30 s. Refresh the page to see the updated summary."
      );
    } catch (e) {
      setQueuedMsg(`Error: ${String(e)}`);
    } finally {
      setRegenerating(false);
    }
  }

  return (
    <div className="bg-white rounded-lg border border-blue-200 p-4">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-semibold text-blue-700 uppercase tracking-wide">
          🧠 Findings
        </h2>
        <button
          onClick={handleRegenerate}
          disabled={regenerating}
          title="Regenerate AI summary"
          className="text-xs text-blue-500 hover:text-blue-700 disabled:opacity-50 underline"
        >
          {regenerating ? "Queuing…" : "↻ Regenerate"}
        </button>
      </div>

      {queuedMsg && (
        <div className="text-xs text-blue-600 bg-blue-50 rounded px-2 py-1.5 mb-2">
          {queuedMsg}
        </div>
      )}

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
          No summary yet. Click ↻ Regenerate to generate one, or resolve the ticket to trigger
          automatic generation.
        </p>
      )}
    </div>
  );
}

// ── Action panel ──────────────────────────────────────────────────────────────

function ActionPanel({ ticket, roleKeys, onRefresh, ensureAcknowledged, isAssigned }: {
  ticket: TicketDetail;
  roleKeys: string[];
  onRefresh: () => void;
  ensureAcknowledged: () => Promise<void>;
  isAssigned: boolean;
}) {
  const [note, setNote] = useState("");
  const [replyText, setReplyText] = useState("");
  const [loading, setLoading] = useState(false);
  const [grcHearingDate, setGrcHearingDate] = useState("");
  const [grcDecision, setGrcDecision] = useState<"RESOLVED" | "ESCALATE_TO_LEGAL">("RESOLVED");

  const status = ticket.status_code;
  const stepKey = ticket.current_step?.step_key ?? "";
  const isGrcChair = roleKeys.includes("grc_chair") || roleKeys.includes("super_admin");

  async function act(action_type: string, extra?: Record<string, string>) {
    setLoading(true);
    try {
      // Auto-acknowledge before any action when ticket is still OPEN
      if (action_type !== "ACKNOWLEDGE") await ensureAcknowledged();
      await performAction(ticket.ticket_id, { action_type, note: note || undefined, ...extra });
      setNote("");
      onRefresh();
    } catch (e) {
      alert(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function sendReply() {
    if (!replyText.trim()) return;
    setLoading(true);
    try {
      await ensureAcknowledged();
      await replyToComplainant(ticket.ticket_id, replyText);
      setReplyText("");
      onRefresh();
    } catch (e) {
      alert(String(e));
    } finally {
      setLoading(false);
    }
  }

  const btnBase = "px-3 py-1.5 rounded text-sm font-medium transition disabled:opacity-50";

  // Statuses where no further status-changes make sense
  const isClosed = ["RESOLVED", "CLOSED"].includes(status);
  // Escalated = awaiting the next-level officer's acknowledgement
  const isEscalated = status === "ESCALATED";

  return (
    <div className="space-y-4">

      {/* Non-assigned officer banner */}
      {!isAssigned && (
        <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
          This ticket is assigned to another officer. You can add notes but cannot change its status.
        </div>
      )}

      {/* Primary actions — only for the assigned officer */}
      {isAssigned && (
        <div className="flex flex-wrap gap-2">
          {/* Acknowledge — shown for OPEN or ESCALATED (L2 pickup) */}
          {(status === "OPEN" || isEscalated) && (
            <button onClick={() => act("ACKNOWLEDGE")} disabled={loading}
              className={`${btnBase} bg-blue-600 text-white hover:bg-blue-700`}>
              ✅ Acknowledge
            </button>
          )}
          {/* Escalate / Resolve / Close — not available while ESCALATED (must acknowledge first) */}
          {!isClosed && !isEscalated && (
            <button onClick={() => act("ESCALATE")} disabled={loading}
              className={`${btnBase} bg-orange-500 text-white hover:bg-orange-600`}>
              🔺 Escalate
            </button>
          )}
          {!isClosed && !isEscalated && (
            <button onClick={() => act("RESOLVE")} disabled={loading}
              className={`${btnBase} bg-green-600 text-white hover:bg-green-700`}>
              🏁 Resolve
            </button>
          )}
          {!isClosed && !isEscalated && (
            <button onClick={() => act("CLOSE")} disabled={loading}
              className={`${btnBase} bg-gray-400 text-white hover:bg-gray-500`}>
              Close
            </button>
          )}

          {/* GRC Convene — only once acknowledged (not while ESCALATED) */}
          {isGrcChair && stepKey === "LEVEL_3_GRC" && !isEscalated && status !== "GRC_HEARING_SCHEDULED" && (
            <div className="flex gap-2 items-center w-full mt-1">
              <input type="date" value={grcHearingDate} onChange={(e) => setGrcHearingDate(e.target.value)}
                className="text-sm border border-gray-300 rounded px-2 py-1.5" />
              <button
                onClick={() => act("GRC_CONVENE", { grc_hearing_date: grcHearingDate })}
                disabled={loading}
                className={`${btnBase} bg-purple-600 text-white hover:bg-purple-700`}
              >
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
              <button
                onClick={() => act("GRC_DECIDE", { grc_decision: grcDecision })}
                disabled={loading}
                className={`${btnBase} bg-purple-700 text-white hover:bg-purple-800`}
              >
                ⚖️ Record Decision
              </button>
            </div>
          )}
        </div>
      )}

      {/* Internal note — available to all officers */}
      <div>
        <label className="text-xs font-medium text-gray-500 block mb-1">Internal Note 🔒</label>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={2}
          placeholder="Add an internal officer note (not visible to complainant)…"
          className="w-full text-sm border border-gray-200 rounded px-3 py-2 resize-none focus:outline-none focus:ring-1 focus:ring-blue-400"
        />
        <button
          onClick={() => act("NOTE")}
          disabled={!note.trim() || loading}
          className={`mt-1 ${btnBase} bg-gray-100 text-gray-700 hover:bg-gray-200`}
        >
          Save Note
        </button>
      </div>

      {/* Reply to complainant — only for the assigned officer */}
      {isAssigned && (
        <div>
          <label className="text-xs font-medium text-gray-500 block mb-1">Reply to Complainant 💬</label>
          <textarea
            value={replyText}
            onChange={(e) => setReplyText(e.target.value)}
            rows={3}
            placeholder="Message sent via chatbot (SMS fallback if session expired)…"
            className="w-full text-sm border border-gray-200 rounded px-3 py-2 resize-none focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
          <button
            onClick={sendReply}
            disabled={!replyText.trim() || loading}
            className={`mt-1 ${btnBase} bg-blue-50 text-blue-700 hover:bg-blue-100`}
          >
            Send Reply
          </button>
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

// ── Complainant PII card ──────────────────────────────────────────────────────
// Per PRIVACY.md: name shown by default; phone hidden behind audited "Reveal" (proto: no OTP).
// "Reveal original statement" opens the full vault reveal flow (RevealModal → RevealOverlay).

function ComplainantCard({
  ticket,
  onRevealOriginal,
}: {
  ticket: TicketDetail;
  /** Called when officer clicks "Reveal original statement" — opens RevealModal in parent */
  onRevealOriginal: () => void;
}) {
  const [pii, setPii] = useState<GrievancePii | null>(null);
  const [piiLoading, setPiiLoading] = useState(false);
  const [piiError, setPiiError] = useState<string | null>(null);
  // Phone reveal: simple reveal + REVEAL_CONTACT audit event (proto per PRIVACY.md)
  const [phoneRevealed, setPhoneRevealed] = useState(false);
  const [phoneRevealing, setPhoneRevealing] = useState(false);

  // Fetch name automatically (non-sensitive)
  useEffect(() => {
    if (!ticket.grievance_id) return;
    setPiiLoading(true);
    getGrievancePii(ticket.grievance_id)
      .then(setPii)
      .catch(() => setPiiError("Could not load complainant details"))
      .finally(() => setPiiLoading(false));
  }, [ticket.grievance_id]);

  async function handlePhoneReveal() {
    setPhoneRevealing(true);
    // Log reveal via REVEAL_CONTACT action — audited, no OTP for proto
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
          <div><span className="text-gray-400">Session:</span> {ticket.session_id ? "✅ Active" : "❌ Expired"}</div>
        </div>
      ) : (
        <div className="text-xs space-y-1.5 text-gray-700">
          {pii?.complainant_name && (
            <div><span className="text-gray-400">Name:</span> {pii.complainant_name}</div>
          )}
          <div><span className="text-gray-400">Ref:</span> {ticket.complainant_id ?? "—"}</div>

          {/* Phone — hidden, audited reveal (proto: no OTP) */}
          <div className="flex items-center gap-1.5">
            <span className="text-gray-400">Phone:</span>
            {phoneRevealed && pii?.phone_number ? (
              <span className="font-mono">{pii.phone_number}</span>
            ) : (
              <>
                <span className="text-gray-300 font-mono">••••••••</span>
                <button
                  onClick={handlePhoneReveal}
                  disabled={phoneRevealing}
                  className="text-blue-500 hover:text-blue-700 underline text-xs ml-0.5 disabled:opacity-50"
                >
                  {phoneRevealing ? "…" : "Reveal"}
                </button>
              </>
            )}
          </div>

          {pii?.email && (
            <div><span className="text-gray-400">Email:</span> {pii.email}</div>
          )}
          <div>
            <span className="text-gray-400">Session:</span>{" "}
            {ticket.session_id ? (
              <span className="text-green-600">✅ Active</span>
            ) : (
              <span className="text-red-500">❌ Expired — SMS fallback</span>
            )}
          </div>

          {/* Vault reveal — original statement (full reveal flow per PRIVACY.md) */}
          {ticket.grievance_id && (
            <div className="border-t border-gray-100 pt-2 mt-1">
              <button
                onClick={onRevealOriginal}
                className="text-xs text-red-700 hover:text-red-900 underline flex items-center gap-1"
                title="View original grievance statement — access is audited and time-limited"
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

// ── Page ──────────────────────────────────────────────────────────────────────

export default function TicketDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user, roleKeys, canSeeSeah, isAdmin, effectiveLang } = useAuth();
  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [sla, setSla] = useState<SlaStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ── Vault reveal state ──────────────────────────────────────────────────────
  // revealModalOpen → RevealModal (reason form) → on grant → revealSession → RevealOverlay
  const [revealModalOpen, setRevealModalOpen] = useState(false);
  const [revealSession, setRevealSession] = useState<RevealSession | null>(null);

  function openRevealModal() { setRevealModalOpen(true); }
  function closeRevealModal() { setRevealModalOpen(false); }
  function onRevealGranted(session: RevealSession) {
    setRevealModalOpen(false);
    setRevealSession(session);
  }
  function onRevealOverlayClosed() { setRevealSession(null); }

  // ── Translation panel state — persisted to localStorage ──────────────────
  const PANEL_KEY = "grm_translation_panel_open";
  const [panelOpen, setPanelOpen] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(PANEL_KEY) === "true";
  });
  function togglePanel() {
    setPanelOpen((prev) => {
      const next = !prev;
      localStorage.setItem(PANEL_KEY, String(next));
      return next;
    });
  }

  // Keyboard shortcut: T toggles translation panel (when not typing in an input)
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

  // Inline translation chips shown to English-first users; hidden for Nepali-first
  // (null = still loading, default to showing to avoid flicker for English users)
  const showTranslations = effectiveLang !== "ne";

  async function load() {
    try {
      const [t, s] = await Promise.all([getTicket(id), getSla(id)]);
      setTicket(t);
      setSla(s);
      // Mark events as seen
      markSeen(id).catch(() => {});
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  // True when the current user is the assigned officer (or an admin).
  // Non-assigned officers can view and add notes but cannot change ticket status.
  const isAssigned =
    isAdmin ||
    !ticket?.assigned_to_user_id ||
    ticket?.assigned_to_user_id === user?.sub;

  // Silently acknowledge before any officer action.
  // Fires for both OPEN (L1) and ESCALATED (L2 picking up the ticket).
  // Escalation resets step_started_at to null — the SLA clock restarts on acknowledge.
  // Only fires for the assigned officer — non-assigned officers cannot acknowledge.
  async function ensureAcknowledged() {
    if (!ticket || !["OPEN", "ESCALATED"].includes(ticket.status_code)) return;
    if (!isAssigned) return;
    await performAction(id, { action_type: "ACKNOWLEDGE" });
    await load();
  }

  useEffect(() => { load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <div className="p-8 text-gray-400 text-sm">Loading…</div>;
  if (error)   return <div className="p-8 text-red-500 text-sm">{error}</div>;
  if (!ticket) return null;

  // SEAH access guard (belt-and-suspenders — server already blocks)
  if (ticket.is_seah && !canSeeSeah) {
    return <div className="p-8 text-red-500 text-sm">Access denied.</div>;
  }

  return (
    <div className="p-6">
      {/* Back */}
      <button onClick={() => router.back()} className="text-sm text-gray-500 hover:text-gray-700 mb-4 flex items-center gap-1">
        ← Back to queue
      </button>

      {/* Title row */}
      <div className="flex items-start justify-between mb-5 flex-wrap gap-2">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-xl font-semibold text-gray-800">{ticket.grievance_id}</h1>
            {ticket.is_seah && <SeahBadge />}
            <StatusBadge code={ticket.status_code} />
            <PriorityBadge priority={ticket.priority} />
          </div>
          <p className="text-sm text-gray-500 mt-1">
            {ticket.organization_id} · {ticket.location_code} · {ticket.project_code}
          </p>
        </div>
        <div className="text-sm text-gray-400">
          Created {new Date(ticket.created_at).toLocaleDateString()}
        </div>
      </div>

      {/* Outer wrapper: main grid + translation panel side by side */}
      <div className="flex gap-0 items-start">

      {/* ── Main grid (shrinks when panel is open) ── */}
      <div className={`flex-1 min-w-0 grid grid-cols-1 lg:grid-cols-3 gap-5 transition-all duration-200`}>

        {/* ── Left: case info ── */}
        <div className="lg:col-span-2 space-y-4">

          {/* Grievance info card */}
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">Grievance Summary</h2>
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

          {/* Workflow progress */}
          {ticket.current_step && (
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-2">Workflow</h2>
              <div className="text-sm font-medium text-gray-700">{ticket.current_step.display_name}</div>
              <div className="text-xs text-gray-400 mt-0.5">
                Assigned role: {ticket.current_step.assigned_role_key.replace(/_/g, " ")}
              </div>
              <WorkflowStepper currentStepKey={ticket.current_step.step_key} />

              {/* SLA detail */}
              {sla && sla.urgency !== "none" && (
                <div className={`mt-3 text-xs p-2 rounded ${
                  sla.breached ? "bg-red-50 text-red-700" :
                  sla.urgency === "warning" ? "bg-yellow-50 text-yellow-700" :
                  "bg-green-50 text-green-700"
                }`}>
                  ⏱ SLA: {sla.resolution_time_days}d resolution target ·{" "}
                  {sla.deadline && `Deadline ${new Date(sla.deadline).toLocaleDateString()} · `}
                  <SlaCountdown ticketId={ticket.ticket_id} initial={sla} />
                </div>
              )}
            </div>
          )}

          {/* Event timeline */}
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide">Case Timeline</h2>
              <button
                onClick={togglePanel}
                title={panelOpen ? "Close translation panel (T)" : "Open translation review panel (T)"}
                className={`text-xs px-2 py-1 rounded border transition ${
                  panelOpen
                    ? "bg-blue-100 border-blue-300 text-blue-700"
                    : "bg-gray-50 border-gray-200 text-gray-500 hover:border-blue-300 hover:text-blue-600"
                }`}
              >
                🌐 {panelOpen ? "Hide translations" : "Review translations"}
              </button>
            </div>
            <EventTimeline
              events={ticket.events}
              showTranslations={showTranslations}
              onTogglePanel={togglePanel}
              panelOpen={panelOpen}
            />
          </div>
        </div>

        {/* ── Right: actions ── */}
        <div className="space-y-4">

          {/* Complainant info card */}
          <ComplainantCard ticket={ticket} onRevealOriginal={openRevealModal} />

          {/* AI Findings — visible to GRC/supervisor roles only (7b) */}
          <FindingsCard ticket={ticket} roleKeys={roleKeys} onRefresh={load} />

          {/* File attachments */}
          <FilesPanel
            ticketId={ticket.ticket_id}
            onBeforeDownload={ensureAcknowledged}
            isAssigned={isAssigned}
            onUpload={load}
          />

          {/* Assignment */}
          <AssignPanel ticket={ticket} onRefresh={load} />

          {/* Reassign to teammate (shown when there are colleagues in same scope) */}
          <ReassignPanel ticket={ticket} onRefresh={load} />

          {/* Action panel */}
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">Actions</h2>
            <ActionPanel ticket={ticket} roleKeys={roleKeys} onRefresh={load} ensureAcknowledged={ensureAcknowledged} isAssigned={isAssigned} />
          </div>
        </div>
      </div>{/* end main grid */}

      {/* ── Translation panel (rightmost collapsible column) ── */}
      {panelOpen && ticket && (
        <div className="sticky top-6 self-start ml-4 hidden lg:block">
          <TranslationPanel events={ticket.events} onClose={() => { setPanelOpen(false); localStorage.setItem(PANEL_KEY, "false"); }} />
        </div>
      )}
      {/* Mobile / smaller screens: translation panel as a fixed right drawer */}
      {panelOpen && ticket && (
        <div className="lg:hidden fixed inset-y-0 right-0 z-40 w-80 shadow-2xl flex flex-col">
          <TranslationPanel events={ticket.events} onClose={() => { setPanelOpen(false); localStorage.setItem(PANEL_KEY, "false"); }} />
        </div>
      )}

      </div>{/* end outer flex */}

      {/* ── Vault reveal — reason modal ── */}
      {revealModalOpen && ticket && (
        <RevealModal
          ticketId={ticket.ticket_id}
          isSeah={ticket.is_seah}
          onClose={closeRevealModal}
          onGranted={onRevealGranted}
        />
      )}

      {/* ── Vault reveal — content overlay ── */}
      {revealSession && ticket && (
        <RevealOverlay
          session={revealSession}
          ticketId={ticket.ticket_id}
          onClose={onRevealOverlayClosed}
        />
      )}

    </div>
  );
}
