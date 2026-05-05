"use client";

import { useEffect, useMemo, useState } from "react";
import { Eye, Users } from "lucide-react";
import { addViewer, removeViewer, addInformed, listOfficers } from "@/lib/api";
import type { TicketViewer, OfficerBrief } from "@/lib/api";

// ── Add officer sheet (shared by both Informed and Observer flows) ────────────

function AddOfficerSheet({
  ticketId,
  tier,
  onClose,
  onAdded,
}: {
  ticketId: string;
  tier: "informed" | "observer";
  onClose: () => void;
  onAdded: () => void;
}) {
  const [query, setQuery] = useState("");
  const [officers, setOfficers] = useState<OfficerBrief[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    listOfficers().then(setOfficers).catch(() => {});
  }, []);

  const filtered = useMemo(
    () => officers.filter((o) =>
      query ? o.user_id.toLowerCase().includes(query.toLowerCase()) : true
    ).slice(0, 8),
    [officers, query],
  );

  const submit = async (uid: string) => {
    const target = uid.trim();
    if (!target) return;
    setSubmitting(true);
    setErr(null);
    try {
      if (tier === "informed") {
        await addInformed(ticketId, target);
      } else {
        await addViewer(ticketId, target);
      }
      onAdded();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg.includes("409")) setErr("Already a participant.");
      else if (msg.includes("403")) setErr("Permission denied — only the assigned officer can add to Informed.");
      else setErr("Failed to add.");
    } finally {
      setSubmitting(false);
    }
  };

  const label = tier === "informed" ? "Add to Informed" : "Add Observer";
  const accent = tier === "informed" ? "text-purple-700" : "text-gray-500";

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end" onClick={onClose}>
      <div
        className="bg-white rounded-t-2xl shadow-xl p-5 max-h-[70vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="w-12 h-1 bg-gray-300 rounded-full mx-auto mb-4" />
        <h3 className={`text-base font-semibold mb-3 flex items-center gap-1.5 ${accent}`}>
          {tier === "informed" ? <Users size={15} strokeWidth={2} /> : <Eye size={15} strokeWidth={2} />}
          {label}
        </h3>
        {tier === "informed" && (
          <p className="text-xs text-gray-400 mb-3">
            Informed officers can add notes and execute tasks. They do not gain workflow actions.
          </p>
        )}

        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search officer…"
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
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold ${
                tier === "informed" ? "bg-purple-100 text-purple-600" : "bg-blue-100 text-blue-600"
              }`}>
                {o.user_id.charAt(0).toUpperCase()}
              </div>
              <div>
                <div className="text-sm font-medium text-gray-800">{o.user_id}</div>
                <div className="text-xs text-gray-400">{o.role_keys.join(", ")}</div>
              </div>
            </button>
          ))}
          {query && !filtered.find((o) => o.user_id === query) && (
            <button
              onClick={() => submit(query)}
              disabled={submitting}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left mt-1 ${
                tier === "informed" ? "bg-purple-50" : "bg-blue-50"
              }`}
            >
              <span className={`text-sm ${tier === "informed" ? "text-purple-700" : "text-blue-700"}`}>
                Add &ldquo;{query}&rdquo; directly
              </span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Viewers / Tiers bar ───────────────────────────────────────────────────────

export function ViewersBar({
  viewers,
  canManage,
  ticketId,
  onChanged,
  isActor = false,
}: {
  viewers: TicketViewer[];
  canManage: boolean;
  ticketId: string;
  onChanged: () => void;
  /** True when the current user is the assigned Actor — can add to Informed */
  isActor?: boolean;
}) {
  const [showSheet, setShowSheet] = useState<"informed" | "observer" | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);

  const informed  = viewers.filter((v) => v.tier === "informed");
  const observers = viewers.filter((v) => v.tier === "observer");

  const handleRemove = async (userId: string) => {
    setRemoving(userId);
    try {
      await removeViewer(ticketId, userId);
      onChanged();
    } finally {
      setRemoving(null);
    }
  };

  const canAddInformed  = isActor || canManage;
  const canAddObserver  = canManage;

  if (informed.length === 0 && observers.length === 0 && !canAddInformed && !canAddObserver) return null;

  function Chip({ v }: { v: TicketViewer }) {
    const isInformed = v.tier === "informed";
    return (
      <div className={`flex items-center gap-1 border rounded-full px-2 py-0.5 text-[11px] shrink-0 ${
        isInformed
          ? "bg-purple-50 border-purple-200 text-purple-700"
          : "bg-white border-gray-200 text-gray-600"
      }`}>
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
    );
  }

  return (
    <>
      {/* Informed row */}
      {(informed.length > 0 || canAddInformed) && (
        <div className="flex items-center gap-2 px-4 py-1 bg-purple-50/60 border-b border-purple-100 overflow-x-auto scrollbar-none">
          <span className="inline-flex items-center gap-1 text-[11px] text-purple-400 shrink-0">
            <Users size={11} strokeWidth={2} />
            Informed:
          </span>
          {informed.length === 0
            ? <span className="text-[11px] text-purple-200 italic">None</span>
            : informed.map((v) => <Chip key={v.viewer_id} v={v} />)
          }
          {canAddInformed && (
            <button
              onClick={() => setShowSheet("informed")}
              className="shrink-0 flex items-center gap-1 bg-purple-100 border border-purple-200 rounded-full px-2 py-0.5 text-[11px] text-purple-700 font-medium"
            >
              + Add
            </button>
          )}
        </div>
      )}

      {/* Observer row */}
      {(observers.length > 0 || canAddObserver) && (
        <div className="flex items-center gap-2 px-4 py-1 bg-gray-50 border-b border-gray-100 overflow-x-auto scrollbar-none">
          <span className="inline-flex items-center gap-1 text-[11px] text-gray-400 shrink-0">
            <Eye size={11} strokeWidth={2} />
            Observers:
          </span>
          {observers.length === 0
            ? <span className="text-[11px] text-gray-300 italic">None</span>
            : observers.map((v) => <Chip key={v.viewer_id} v={v} />)
          }
          {canAddObserver && (
            <button
              onClick={() => setShowSheet("observer")}
              className="shrink-0 flex items-center gap-1 bg-blue-50 border border-blue-200 rounded-full px-2 py-0.5 text-[11px] text-blue-600 font-medium"
            >
              + Add
            </button>
          )}
        </div>
      )}

      {showSheet && (
        <AddOfficerSheet
          ticketId={ticketId}
          tier={showSheet}
          onClose={() => setShowSheet(null)}
          onAdded={() => { setShowSheet(null); onChanged(); }}
        />
      )}
    </>
  );
}
