"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getTicket, getSla, performAction, markSeen, replyToComplainant, getGrievancePii,
  listTicketFiles, getFileDownloadUrl, listOfficers, patchTicket,
  listOfficerAttachments, getOfficerAttachmentUrl, uploadOfficerAttachment,
  generateFindings, listTicketTasks, completeTask, patchComplainant,
  type TicketDetail, type SlaStatus, type GrievancePii, type TicketFile,
  type OfficerBrief, type OfficerAttachment, type RevealSession, type TicketTask, type TicketEvent,
  type ComplainantPatchPayload,
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
import {
  SYSTEM_EVENT_TYPES, TASK_EVENT_TYPES, NOTIFICATION_ONLY_EVENT_TYPES, TASK_TYPES,
} from "@/lib/mobile-constants";
import {
  IconAcknowledge, IconEscalateAction, IconResolve, IconGrcConvene, IconGrcDecide,
  IconReply, IconTask, IconAssign, IconTranslations,
  IconEdit, IconActiveSession, IconExpiredSession, IconRevealStatement,
  IconFileImage, IconFilePdf, IconFileOther, IconUpload,
  IconFindings, IconRegenerate, IconWarning, IconClose,
  TaskTypeIcon,
} from "@/lib/icons";
import { Check, RefreshCw } from "lucide-react";

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

// ── File attachments panel ────────────────────────────────────────────────────

function FilesPanel({
  ticketId,
  onBeforeDownload,
  isAssigned,
  onUpload,
}: {
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
      setUploadError(String(e));
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-4">
      <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide border-l-[3px] border-blue-500 pl-3">Attachments</h2>

      <div>
        <div className="text-xs font-medium text-gray-600 mb-1.5">From complainant</div>
        {loading ? <div className="text-xs text-gray-400">Loading…</div>
          : complainantFiles.length === 0
            ? <div className="text-xs text-gray-400 italic">No files uploaded by complainant.</div>
            : complainantFiles.map((f) => (
              <button key={f.file_id}
                onClick={async () => { await onBeforeDownload(); window.open(getFileDownloadUrl(f.file_id), "_blank", "noopener,noreferrer"); }}
                className="flex items-center gap-2 text-xs text-blue-600 hover:text-blue-800 group w-full text-left mb-1"
              >
                <FileIcon type={f.file_type} />
                <span className="flex-1 truncate group-hover:underline">{f.file_name}</span>
                <span className="text-gray-400 shrink-0">{fmt(f.file_size)}</span>
              </button>
            ))
        }
      </div>

      <div>
        <div className="text-xs font-medium text-gray-600 mb-1.5">Officer attachments</div>
        {officerFiles.length === 0
          ? <div className="text-xs text-gray-400 italic">No officer files attached yet.</div>
          : officerFiles.map((f) => (
            <div key={f.file_id} className="flex items-start gap-2 mb-1">
              <button
                onClick={() => window.open(getOfficerAttachmentUrl(f.file_id), "_blank", "noopener,noreferrer")}
                className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-800 group shrink-0"
              >
                <FileIcon type={f.file_type} />
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

// ── Complainant edit sheet ────────────────────────────────────────────────────

const EDIT_FIELDS: { key: keyof ComplainantPatchPayload; label: string }[] = [
  { key: "complainant_address",      label: "Address" },
  { key: "complainant_village",      label: "Village / Tole" },
  { key: "complainant_ward",         label: "Ward No." },
  { key: "complainant_municipality", label: "Municipality / VDC" },
  { key: "complainant_district",     label: "District" },
  { key: "complainant_province",     label: "Province" },
  { key: "complainant_email",        label: "Email" },
];

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
  const [form, setForm] = useState<ComplainantPatchPayload>({
    complainant_address:      (pii?.address      as string | undefined) ?? "",
    complainant_municipality: (pii?.municipality as string | undefined) ?? "",
    complainant_district:     (pii?.district     as string | undefined) ?? "",
    complainant_province:     (pii?.province     as string | undefined) ?? "",
    complainant_email:        pii?.email ?? "",
    complainant_village:      "",
    complainant_ward:         "",
  });
  const [saving, setSaving]   = useState(false);
  const [error,  setError]    = useState<string | null>(null);

  async function handleSave() {
    // Only send non-empty fields
    const payload: ComplainantPatchPayload = {};
    for (const { key } of EDIT_FIELDS) {
      const val = form[key];
      if (val && val.trim()) payload[key] = val.trim();
    }
    if (Object.keys(payload).length === 0) { onClose(); return; }

    setSaving(true);
    setError(null);
    try {
      await patchComplainant(ticket.ticket_id, payload);
      onSaved();
      onClose();
    } catch {
      setError("Save failed — please try again.");
    } finally {
      setSaving(false);
    }
  }

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

        <p className="text-xs text-gray-400 mb-4">
          Name and phone number cannot be changed here — contact the chatbot admin.
          All changes are logged in the case timeline.
        </p>

        <div className="space-y-3">
          {EDIT_FIELDS.map(({ key, label }) => (
            <div key={key}>
              <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
              <input
                type={key === "complainant_email" ? "email" : "text"}
                value={form[key] ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400"
                placeholder={`Enter ${label.toLowerCase()}`}
              />
            </div>
          ))}
        </div>

        {error && <p className="text-xs text-red-600 mt-3">{error}</p>}

        <div className="flex gap-2 mt-5">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium py-2.5 rounded-xl transition-colors"
          >
            {saving ? "Saving…" : "Save changes"}
          </button>
          <button
            onClick={onClose}
            className="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm font-medium py-2.5 rounded-xl transition-colors"
          >
            Cancel
          </button>
        </div>
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
  const [phoneRevealed, setPhoneRevealed]   = useState(false);
  const [phoneRevealing, setPhoneRevealing] = useState(false);
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

  async function handlePhoneReveal() {
    setPhoneRevealing(true);
    await performAction(ticket.ticket_id, { action_type: "REVEAL_CONTACT" }).catch(() => {});
    setPhoneRevealed(true);
    setPhoneRevealing(false);
  }

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
            {pii?.address && <div><span className="text-gray-400">Address:</span> {pii.address}</div>}
            {(pii as GrievancePii & { municipality?: string })?.municipality && (
              <div><span className="text-gray-400">Municipality:</span> {(pii as GrievancePii & { municipality?: string }).municipality}</div>
            )}
            {(pii as GrievancePii & { district?: string })?.district && (
              <div><span className="text-gray-400">District:</span> {(pii as GrievancePii & { district?: string }).district}</div>
            )}
            <div>
              <span className="text-gray-400">Session:</span>{" "}
              {ticket.session_id
                ? <span className="inline-flex items-center gap-1 text-green-600"><IconActiveSession size={12} strokeWidth={2} />Active</span>
                : <span className="inline-flex items-center gap-1 text-red-500"><IconExpiredSession size={12} strokeWidth={2} />Expired — SMS fallback</span>}
            </div>
            {ticket.grievance_id && (
              <div className="border-t border-gray-100 pt-2 mt-1">
                <button onClick={onRevealOriginal}
                  className="text-xs text-red-700 hover:text-red-900 underline flex items-center gap-1"
                >
                  <IconRevealStatement size={13} strokeWidth={2} />
                  Reveal original statement
                </button>
              </div>
            )}
          </div>
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
    <div className="bg-white rounded-xl border border-blue-100 p-4">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide border-l-[3px] border-indigo-400 pl-3 flex items-center gap-1.5">
          <IconFindings size={14} strokeWidth={2} className="text-indigo-500" />
          Findings
        </h2>
        <button onClick={handleRegenerate} disabled={regenerating}
          className="text-xs text-blue-500 hover:text-blue-700 disabled:opacity-50 inline-flex items-center gap-1"
        >
          <IconRegenerate size={11} strokeWidth={2} className={regenerating ? "animate-spin" : ""} />
          {regenerating ? "Queuing…" : "Regenerate"}
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
          No summary yet. Click Regenerate to generate one.
        </p>
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

function TasksCard({ tasks, currentUserId, onComplete }: {
  tasks: TicketTask[];
  currentUserId: string;
  onComplete: (taskId: string) => void;
}) {
  const pending   = tasks.filter((t) => t.status === "PENDING");
  const done      = tasks.filter((t) => t.status === "DONE");

  if (tasks.length === 0) return null;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <div className="flex items-center gap-2 mb-3">
        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide border-l-[3px] border-blue-500 pl-3">Tasks</h2>
        {pending.length > 0 && (
          <span className="bg-amber-100 text-amber-700 text-[10px] font-bold px-1.5 py-0.5 rounded-full">
            {pending.length} pending
          </span>
        )}
        {pending.length === 0 && (
          <span className="bg-green-100 text-green-700 text-[10px] font-bold px-1.5 py-0.5 rounded-full">
            All done
          </span>
        )}
      </div>

      <div className="space-y-2">
        {pending.map((task) => {
          const typeInfo = TASK_TYPES.find((t) => t.key === task.task_type);
          const isAssignedToMe = task.assigned_to_user_id === currentUserId || task.assigned_to_user_id === "mock-super-admin";
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
                  <span>→ {task.assigned_to_user_id === currentUserId ? "You" : task.assigned_to_user_id}</span>
                  {task.due_date && <><span>·</span><span>Due {new Date(task.due_date).toLocaleDateString()}</span></>}
                </div>
              </div>
              {isAssignedToMe && (
                <button
                  onClick={() => onComplete(task.task_id)}
                  className="shrink-0 text-[11px] text-green-700 bg-green-50 border border-green-200 rounded-lg px-2 py-1 hover:bg-green-100 transition font-medium"
                >
                  <Check size={11} strokeWidth={2.5} className="inline mr-0.5" />Done
                </button>
              )}
            </div>
          );
        })}

        {done.length > 0 && (
          <div className="pt-1 border-t border-gray-100 space-y-1.5">
            {done.map((task) => {
              const typeInfo = TASK_TYPES.find((t) => t.key === task.task_type);
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

  // ── Top bar actions ────────────────────────────────────────────────────
  const [actLoading, setActLoading]     = useState(false);
  const [showReply, setShowReply]       = useState(false);
  const [replyText, setReplyText]       = useState("");
  const [showAssign, setShowAssign]     = useState(false);
  const [officers, setOfficers]         = useState<OfficerBrief[]>([]);
  const [assignSelected, setAssignSelected] = useState("");
  const [savingAssign, setSavingAssign] = useState(false);
  const [showAssignTask, setShowAssignTask] = useState(false);
  const [grcHearingDate, setGrcHearingDate] = useState("");
  const [grcDecision, setGrcDecision]   = useState<"RESOLVED" | "ESCALATE_TO_LEGAL">("RESOLVED");

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
      markSeen(id).catch(() => {});
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (showAssign && officers.length === 0) {
      listOfficers().then(setOfficers).catch(() => {});
    }
  }, [showAssign]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Derived ────────────────────────────────────────────────────────────
  const currentUserId = user?.sub ?? "mock-super-admin";
  const isAssigned    = isAdmin || !ticket?.assigned_to_user_id || ticket?.assigned_to_user_id === user?.sub;

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

  const filteredEvents = useMemo(() => {
    if (!ticket) return [];
    switch (activeFilter) {
      case "all":    return ticket.events;
      case "mine":   return ticket.events.filter((e) => e.created_by_user_id === currentUserId);
      case "tasks":  return ticket.events.filter((e) => TASK_EVENT_TYPES.has(e.event_type));
      case "system": return ticket.events.filter((e) => SYSTEM_EVENT_TYPES.has(e.event_type));
      default:       return ticket.events.filter((e) => e.created_by_user_id === activeFilter);
    }
  }, [ticket, activeFilter, currentUserId]);

  const pendingTaskCount  = useMemo(() => tasks.filter((t) => t.status === "PENDING").length, [tasks]);
  const canManageViewers  = useMemo(() => !!ticket && ticket.assigned_to_user_id === currentUserId, [ticket, currentUserId]);
  const viewerIds         = useMemo(() => new Set((ticket?.viewers ?? []).map((v) => v.user_id)), [ticket]);

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

  // ── Actions ────────────────────────────────────────────────────────────
  const ensureAcknowledged = useCallback(async () => {
    if (!ticket || !["OPEN", "ESCALATED"].includes(ticket.status_code)) return;
    if (!isAssigned) return;
    await performAction(id, { action_type: "ACKNOWLEDGE" });
    await load();
  }, [ticket, isAssigned, id, load]);

  async function act(action_type: string, extra?: Record<string, string>) {
    setActLoading(true);
    try {
      if (action_type !== "ACKNOWLEDGE") await ensureAcknowledged();
      await performAction(id, { action_type, ...extra });
      await load();
    } catch (e) { alert(String(e)); }
    finally { setActLoading(false); }
  }

  async function sendReply() {
    if (!replyText.trim()) return;
    setActLoading(true);
    try {
      await ensureAcknowledged();
      await replyToComplainant(id, replyText);
      setReplyText("");
      setShowReply(false);
      await load();
    } catch (e) { alert(String(e)); }
    finally { setActLoading(false); }
  }

  async function handleAssign() {
    if (!assignSelected || assignSelected === ticket?.assigned_to_user_id) return;
    setSavingAssign(true);
    try {
      await patchTicket(id, { assign_to_user_id: assignSelected });
      setShowAssign(false);
      await load();
    } catch (e) { alert(String(e)); }
    finally { setSavingAssign(false); }
  }

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
                <button onClick={() => act("ACKNOWLEDGE")} disabled={actLoading}
                  className={`${btnBase} inline-flex items-center gap-1.5 bg-blue-600 text-white hover:bg-blue-700`}>
                  <IconAcknowledge size={15} strokeWidth={2} />
                  Acknowledge
                </button>
              )}
              {!isOpen && !isEscalated && !isGrcHearing && (
                <>
                  <button onClick={() => act("ESCALATE")} disabled={actLoading}
                    className={`${btnBase} inline-flex items-center gap-1.5 border border-amber-300 text-amber-700 bg-amber-50 hover:bg-amber-100`}>
                    <IconEscalateAction size={15} strokeWidth={2} />
                    Escalate
                  </button>
                  <button onClick={() => act("RESOLVE")} disabled={actLoading}
                    className={`${btnBase} inline-flex items-center gap-1.5 bg-blue-600 text-white hover:bg-blue-700`}>
                    <IconResolve size={15} strokeWidth={2} />
                    Resolve
                  </button>
                  <button onClick={() => act("CLOSE")} disabled={actLoading}
                    className={`${btnBase} border border-red-200 text-red-600 hover:bg-red-50`}>
                    Close
                  </button>
                </>
              )}
              {isGrcChair && isGrcHearing && (
                <>
                  <select value={grcDecision} onChange={(e) => setGrcDecision(e.target.value as typeof grcDecision)}
                    className="text-sm border border-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-purple-400">
                    <option value="RESOLVED">Decision: Resolved</option>
                    <option value="ESCALATE_TO_LEGAL">Decision: Escalate to Legal</option>
                  </select>
                  <button onClick={() => act("GRC_DECIDE", { grc_decision: grcDecision })} disabled={actLoading}
                    className={`${btnBase} inline-flex items-center gap-1.5 bg-purple-600 text-white hover:bg-purple-700`}>
                    <IconGrcDecide size={15} strokeWidth={2} />
                    GRC Decide
                  </button>
                </>
              )}
              {isGrcChair && stepKey === "LEVEL_3_GRC" && !isGrcHearing && (
                <>
                  <input type="date" value={grcHearingDate} onChange={(e) => setGrcHearingDate(e.target.value)}
                    className="text-sm border border-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-purple-400"
                    placeholder="Hearing date" />
                  <button onClick={() => act("GRC_CONVENE", { grc_hearing_date: grcHearingDate })} disabled={actLoading || !grcHearingDate}
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
                <button
                  onClick={() => { setShowAssign((v) => !v); setShowReply(false); }}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition inline-flex items-center gap-1 ${
                    showAssign
                      ? "bg-blue-100 border-blue-300 text-blue-700"
                      : "border-gray-200 text-gray-600 hover:border-gray-300 bg-white"
                  }`}
                >
                  <IconAssign size={12} strokeWidth={2} />
                  Assign
                </button>
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
                  return <NoteBubble key={event.event_id} event={event} isMine={isMine} assignedToUserId={ticket.assigned_to_user_id} viewerIds={viewerIds} />;
                })
            )}
            <div ref={threadEndRef} />
          </div>

          <div className="flex-shrink-0 border-t border-gray-100">
            <ComposeBar
              value={noteText}
              onChange={setNoteText}
              onSubmit={handleNote}
              disabled={submitting}
              participants={mentionParticipants}
              placeholder="Add an internal note… (@ to mention)"
            />
          </div>
        </div>

        {/* Info column — full-width top (text-rich), 2-col bottom (compact reference) */}
        <div className="col-span-3 overflow-y-auto space-y-3 pb-4">

          {/* Workflow progress — always visible at top */}
          {ticket.current_step && (
            <WorkflowCard
              currentStepKey={ticket.current_step.step_key}
              displayName={ticket.current_step.display_name}
            />
          )}

          {/* Open tasks — shown only when tasks exist */}
          <TasksCard
            tasks={tasks}
            currentUserId={currentUserId}
            onComplete={handleCompleteTask}
          />

          {/* Original Grievance — full width: primary reading content */}
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide border-l-[3px] border-blue-500 pl-3 mb-3">Original Grievance</h2>
            <p className="text-sm text-gray-700 leading-relaxed">
              {ticket.grievance_summary ?? <span className="text-gray-400 italic">No summary</span>}
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

          {/* Findings — full width: AI summary can be several sentences */}
          <FindingsCard ticket={ticket} roleKeys={roleKeys} onRefresh={load} />

          {/* Complainant + Attachments — side by side: compact reference cards */}
          <div className="grid grid-cols-2 gap-3">
            <ComplainantCard ticket={ticket} onRevealOriginal={() => setRevealModalOpen(true)} onComplainantUpdated={load} />
            <FilesPanel
              ticketId={ticket.ticket_id}
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
    </div>
  );
}
