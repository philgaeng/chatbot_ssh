"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getTicket, getSla, markSeen, performAction, replyToComplainant, getGrievancePii,
  type TicketDetail, type SlaStatus, type GrievancePii,
} from "@/lib/api";
import { useAuth } from "@/app/providers/AuthProvider";
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

function EventTimeline({ events }: { events: TicketDetail["events"] }) {
  return (
    <div className="space-y-3">
      {[...events].reverse().map((e) => (
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
            {e.created_by_user_id && (
              <div className="text-xs text-gray-400 mt-0.5">by {e.created_by_user_id}</div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Action panel ──────────────────────────────────────────────────────────────

function ActionPanel({ ticket, roleKeys, onRefresh }: {
  ticket: TicketDetail;
  roleKeys: string[];
  onRefresh: () => void;
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

  return (
    <div className="space-y-4">
      {/* Primary actions */}
      <div className="flex flex-wrap gap-2">
        {status === "OPEN" && (
          <button onClick={() => act("ACKNOWLEDGE")} disabled={loading}
            className={`${btnBase} bg-blue-600 text-white hover:bg-blue-700`}>
            ✅ Acknowledge
          </button>
        )}
        {!["RESOLVED", "CLOSED"].includes(status) && (
          <button onClick={() => act("ESCALATE")} disabled={loading}
            className={`${btnBase} bg-orange-500 text-white hover:bg-orange-600`}>
            🔺 Escalate
          </button>
        )}
        {!["RESOLVED", "CLOSED"].includes(status) && (
          <button onClick={() => act("RESOLVE")} disabled={loading}
            className={`${btnBase} bg-green-600 text-white hover:bg-green-700`}>
            🏁 Resolve
          </button>
        )}
        {!["RESOLVED", "CLOSED"].includes(status) && (
          <button onClick={() => act("CLOSE")} disabled={loading}
            className={`${btnBase} bg-gray-400 text-white hover:bg-gray-500`}>
            Close
          </button>
        )}

        {/* GRC Convene */}
        {isGrcChair && stepKey === "LEVEL_3_GRC" && status !== "GRC_HEARING_SCHEDULED" && (
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

      {/* Internal note */}
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

      {/* Reply to complainant */}
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
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

// ── Complainant PII card ──────────────────────────────────────────────────────

function ComplainantCard({ ticket }: { ticket: TicketDetail }) {
  const [pii, setPii] = useState<GrievancePii | null>(null);
  const [piiLoading, setPiiLoading] = useState(false);
  const [piiError, setPiiError] = useState<string | null>(null);
  const [phoneRevealed, setPhoneRevealed] = useState(false);

  // Fetch name automatically (non-sensitive)
  useEffect(() => {
    if (!ticket.grievance_id) return;
    setPiiLoading(true);
    getGrievancePii(ticket.grievance_id)
      .then(setPii)
      .catch(() => setPiiError("Could not load complainant details"))
      .finally(() => setPiiLoading(false));
  }, [ticket.grievance_id]);

  function handleReveal() {
    setPhoneRevealed(true);
    // INTEGRATION POINT: log reveal action via POST /api/v1/tickets/{id}/actions
    // action_type: "REVEAL_CONTACT" — so audit trail records who viewed PII and when
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
          <div className="flex items-center gap-1.5">
            <span className="text-gray-400">Phone:</span>
            {phoneRevealed && pii?.phone_number ? (
              <span className="font-mono">{pii.phone_number}</span>
            ) : (
              <>
                <span className="text-gray-300 font-mono">••••••••</span>
                <button
                  onClick={handleReveal}
                  className="text-blue-500 hover:text-blue-700 underline text-xs ml-0.5"
                >
                  Reveal
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
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function TicketDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { roleKeys, canSeeSeah } = useAuth();
  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [sla, setSla] = useState<SlaStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  useEffect(() => { load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <div className="p-8 text-gray-400 text-sm">Loading…</div>;
  if (error)   return <div className="p-8 text-red-500 text-sm">{error}</div>;
  if (!ticket) return null;

  // SEAH access guard (belt-and-suspenders — server already blocks)
  if (ticket.is_seah && !canSeeSeah) {
    return <div className="p-8 text-red-500 text-sm">Access denied.</div>;
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

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
            <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">Case Timeline</h2>
            <EventTimeline events={ticket.events} />
          </div>
        </div>

        {/* ── Right: actions ── */}
        <div className="space-y-4">

          {/* Complainant info card */}
          <ComplainantCard ticket={ticket} />

          {/* Assignment card */}
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">Assignment</h2>
            <div className="text-xs text-gray-600">
              {ticket.assigned_to_user_id ?? <span className="text-gray-400">Unassigned</span>}
            </div>
          </div>

          {/* Action panel */}
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">Actions</h2>
            <ActionPanel ticket={ticket} roleKeys={roleKeys} onRefresh={load} />
          </div>
        </div>
      </div>
    </div>
  );
}
