"use client";

import { useEffect, useMemo, useState } from "react";
import { Eye } from "lucide-react";
import { addViewer, removeViewer, listOfficers } from "@/lib/api";
import type { TicketViewer, OfficerBrief } from "@/lib/api";

// ── Add viewer sheet ──────────────────────────────────────────────────────────

function AddViewerSheet({
  ticketId,
  onClose,
  onAdded,
}: {
  ticketId: string;
  onClose: () => void;
  onAdded: () => void;
}) {
  const [userId, setUserId] = useState("");
  const [officers, setOfficers] = useState<OfficerBrief[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    listOfficers().then(setOfficers).catch(() => {});
  }, []);

  const filtered = useMemo(
    () => officers.filter((o) =>
      userId ? o.user_id.toLowerCase().includes(userId.toLowerCase()) : true
    ).slice(0, 8),
    [officers, userId],
  );

  const submit = async (uid: string) => {
    const target = uid.trim();
    if (!target) return;
    setSubmitting(true);
    setErr(null);
    try {
      await addViewer(ticketId, target);
      onAdded();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setErr(msg.includes("409") ? "Already a viewer." : "Failed to add viewer.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end" onClick={onClose}>
      <div
        className="bg-white rounded-t-2xl shadow-xl p-5 max-h-[70vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="w-12 h-1 bg-gray-300 rounded-full mx-auto mb-4" />
        <h3 className="text-base font-semibold text-gray-900 mb-3 flex items-center gap-1.5">
          <Eye size={15} strokeWidth={2} className="text-gray-500" />
          Add viewer
        </h3>

        <input
          type="text"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          placeholder="Search officer user ID…"
          className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm mb-2 focus:outline-none focus:border-blue-500"
          autoFocus
        />

        {err && <div className="text-xs text-red-500 mb-2">{err}</div>}

        <div className="overflow-y-auto flex-1">
          {filtered.map((o) => (
            <button
              key={o.user_id}
              onClick={() => submit(o.user_id)}
              disabled={submitting}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl active:bg-gray-50 text-left"
            >
              <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-sm font-semibold text-blue-600">
                {o.user_id.charAt(0).toUpperCase()}
              </div>
              <div>
                <div className="text-sm font-medium text-gray-800">{o.user_id}</div>
                <div className="text-xs text-gray-400">{o.role_keys.join(", ")}</div>
              </div>
            </button>
          ))}
          {userId && !filtered.find((o) => o.user_id === userId) && (
            <button
              onClick={() => submit(userId)}
              disabled={submitting}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl bg-blue-50 text-left mt-1"
            >
              <span className="text-sm text-blue-700">Add &ldquo;{userId}&rdquo; directly</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Viewers bar ───────────────────────────────────────────────────────────────

export function ViewersBar({
  viewers,
  canManage,
  ticketId,
  onChanged,
}: {
  viewers: TicketViewer[];
  canManage: boolean;
  ticketId: string;
  onChanged: () => void;
}) {
  const [showAdd, setShowAdd] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);

  const handleRemove = async (userId: string) => {
    setRemoving(userId);
    try {
      await removeViewer(ticketId, userId);
      onChanged();
    } finally {
      setRemoving(null);
    }
  };

  if (viewers.length === 0 && !canManage) return null;

  return (
    <>
      <div className="flex items-center gap-2 px-4 py-1.5 bg-gray-50 border-b border-gray-100 overflow-x-auto scrollbar-none">
        <span className="inline-flex items-center gap-1 text-[11px] text-gray-400 shrink-0">
          <Eye size={11} strokeWidth={2} />
          Viewers:
        </span>
        {viewers.length === 0
          ? <span className="text-[11px] text-gray-300 italic">None yet</span>
          : viewers.map((v) => (
            <div
              key={v.viewer_id}
              className="flex items-center gap-1 bg-white border border-gray-200 rounded-full px-2 py-0.5 text-[11px] text-gray-600 shrink-0"
            >
              <span>@{v.user_id.split("-")[0]}</span>
              {canManage && (
                <button
                  onClick={() => handleRemove(v.user_id)}
                  disabled={removing === v.user_id}
                  className="text-gray-300 hover:text-red-400 leading-none"
                >
                  ×
                </button>
              )}
            </div>
          ))
        }
        {canManage && (
          <button
            onClick={() => setShowAdd(true)}
            className="shrink-0 flex items-center gap-1 bg-blue-50 border border-blue-200 rounded-full px-2 py-0.5 text-[11px] text-blue-600 font-medium"
          >
            + Add
          </button>
        )}
      </div>

      {showAdd && (
        <AddViewerSheet
          ticketId={ticketId}
          onClose={() => setShowAdd(false)}
          onAdded={() => { setShowAdd(false); onChanged(); }}
        />
      )}
    </>
  );
}
