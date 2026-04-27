"use client";

/**
 * VaultReveal — controlled access to original grievance content.
 *
 * Per docs/PRIVACY.md and docs/Refactor specs/May5_seah/06_vault_reveal_audit_and_ui_controls.md:
 *   - Officer must supply a reason code + policy acknowledgement before access is granted.
 *   - Content is shown in a time-limited overlay (TTL: 120s standard, 60s SEAH).
 *   - Copy / cut / context-menu are blocked (deterrence only — screenshots cannot be prevented).
 *   - A diagonal watermark with actor + timestamp + case ref is rendered over the content.
 *   - Session is auto-closed on expiry or when the browser tab is hidden.
 *   - Every access attempt (granted or denied) is audit-logged on the backend.
 *
 * Components exported:
 *   RevealModal   — reason code form + policy acknowledgement
 *   RevealOverlay — read-only content viewer with watermark + countdown
 */

import { useEffect, useRef, useState } from "react";
import {
  closeReveal,
  revealOriginal,
  REVEAL_REASON_CODES,
  type RevealSession,
} from "@/lib/api";

// ── RevealModal ───────────────────────────────────────────────────────────────

export function RevealModal({
  ticketId,
  isSeah,
  onClose,
  onGranted,
}: {
  ticketId: string;
  isSeah: boolean;
  onClose: () => void;
  onGranted: (session: RevealSession) => void;
}) {
  const [reasonCode, setReasonCode] = useState("");
  const [reasonText, setReasonText] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ttlSeconds = isSeah ? 60 : 120;
  const needsText = reasonCode === "other";
  const canSubmit =
    reasonCode.length > 0 &&
    acknowledged &&
    (!needsText || reasonText.trim().length > 0) &&
    !loading;

  async function handleSubmit() {
    if (!canSubmit) return;
    setLoading(true);
    setError(null);
    try {
      const session = await revealOriginal(ticketId, {
        reason_code: reasonCode,
        reason_text: reasonText || undefined,
      });
      if (session.granted) {
        onGranted(session);
      } else {
        setError(`Access denied: ${session.deny_code ?? "policy check failed"}`);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md p-6 space-y-4">

        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-gray-800">
              {isSeah ? "🔒 Reveal original SEAH statement" : "📄 Reveal original statement"}
            </h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Access is audited and time-limited ({ttlSeconds} seconds).
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl leading-none shrink-0"
            aria-label="Cancel"
          >
            ×
          </button>
        </div>

        {/* SEAH warning banner */}
        {isSeah && (
          <div className="bg-red-50 border border-red-200 rounded p-3 text-xs text-red-700">
            ⚠️ <strong>SEAH case.</strong> This access is subject to strict rate limits,
            enhanced alerting, and mandatory reporting requirements.
          </div>
        )}

        {/* Reason code */}
        <div>
          <label className="text-xs font-medium text-gray-600 block mb-1">
            Reason for access <span className="text-red-500">*</span>
          </label>
          <select
            value={reasonCode}
            onChange={(e) => setReasonCode(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded px-2 py-2 focus:outline-none focus:ring-1 focus:ring-blue-400"
          >
            <option value="">— Select a reason —</option>
            {REVEAL_REASON_CODES.map((r) => (
              <option key={r.code} value={r.code}>
                {r.label}
              </option>
            ))}
          </select>
        </div>

        {/* Free text note */}
        <div>
          <label className="text-xs font-medium text-gray-600 block mb-1">
            Additional notes{needsText && <span className="text-red-500"> *</span>}
          </label>
          <textarea
            value={reasonText}
            onChange={(e) => setReasonText(e.target.value)}
            rows={2}
            placeholder={
              needsText
                ? "Required: describe the specific need for access…"
                : "Optional: describe the specific need…"
            }
            className="w-full text-sm border border-gray-200 rounded px-2 py-1.5 resize-none focus:outline-none focus:ring-1 focus:ring-blue-400"
          />
        </div>

        {/* Policy acknowledgement */}
        <label className="flex items-start gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={acknowledged}
            onChange={(e) => setAcknowledged(e.target.checked)}
            className="mt-0.5 shrink-0"
          />
          <span className="text-xs text-gray-600 leading-relaxed">
            I acknowledge that this access is logged and audited. I will not copy, share,
            or retain the original statement outside of official case records.
          </span>
        </label>

        {error && (
          <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">
            {error}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2 justify-end pt-1">
          <button
            onClick={onClose}
            className="text-sm text-gray-600 hover:text-gray-800 px-3 py-1.5"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="text-sm bg-red-700 text-white rounded px-4 py-1.5 hover:bg-red-800 disabled:opacity-40 disabled:cursor-not-allowed transition"
          >
            {loading ? "Requesting access…" : "Request access"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── RevealOverlay ─────────────────────────────────────────────────────────────

export function RevealOverlay({
  session,
  ticketId,
  onClose,
}: {
  session: RevealSession;
  ticketId: string;
  onClose: () => void;
}) {
  const expiresAt = session.expires_at_utc ? new Date(session.expires_at_utc) : null;
  const totalSeconds = session.ttl_seconds ?? 120;

  const [secondsLeft, setSecondsLeft] = useState<number>(() => {
    if (!expiresAt) return totalSeconds;
    return Math.max(0, Math.floor((expiresAt.getTime() - Date.now()) / 1000));
  });

  const closedRef = useRef(false);

  async function handleClose(reason = "user_closed") {
    if (closedRef.current) return;
    closedRef.current = true;
    if (session.reveal_session_id) {
      await closeReveal(ticketId, session.reveal_session_id, reason).catch(() => {});
    }
    onClose();
  }

  // Countdown — auto-close on expiry
  useEffect(() => {
    const iv = setInterval(() => {
      const remaining = expiresAt
        ? Math.max(0, Math.floor((expiresAt.getTime() - Date.now()) / 1000))
        : 0;
      setSecondsLeft(remaining);
      if (remaining <= 0 && !closedRef.current) {
        clearInterval(iv);
        handleClose("expired");
      }
    }, 500);
    return () => clearInterval(iv);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-close when tab is hidden (best effort)
  useEffect(() => {
    function onVisibility() {
      if (document.hidden) handleClose("tab_hidden");
    }
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Escape key closes
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") handleClose("user_closed");
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const content = session.content ?? {};
  const pctLeft = Math.min(100, Math.max(0, (secondsLeft / totalSeconds) * 100));
  const barColor =
    secondsLeft <= 15 ? "bg-red-500" : secondsLeft <= 30 ? "bg-amber-400" : "bg-blue-400";
  const timerColor =
    secondsLeft <= 15
      ? "text-red-600 font-bold"
      : secondsLeft <= 30
      ? "text-amber-600 font-semibold"
      : "text-gray-500";

  const mm = String(Math.floor(secondsLeft / 60)).padStart(2, "0");
  const ss = String(secondsLeft % 60).padStart(2, "0");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80">
      <div
        className="relative bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col"
        // ── Containment controls (deterrence — screenshots cannot be fully prevented) ──
        style={{ userSelect: "none" }}
        onCopy={(e) => e.preventDefault()}
        onCut={(e) => e.preventDefault()}
        onContextMenu={(e) => e.preventDefault()}
      >

        {/* ── Diagonal watermark ── */}
        <div
          className="absolute inset-0 pointer-events-none z-10 flex items-center justify-center overflow-hidden"
          aria-hidden
        >
          {Array.from({ length: 10 }).map((_, i) => (
            <div
              key={i}
              className="absolute text-gray-300 font-mono text-xs opacity-50 whitespace-nowrap"
              style={{
                transform: `rotate(-25deg) translateY(${(i - 5) * 42}px)`,
                letterSpacing: "0.05em",
              }}
            >
              {session.watermark_text ?? "RESTRICTED ACCESS"} &nbsp;&nbsp;&nbsp;
              {session.watermark_text ?? "RESTRICTED ACCESS"}
            </div>
          ))}
        </div>

        {/* ── Header ── */}
        <div className="relative z-20 flex items-center justify-between px-5 py-3 border-b border-red-200 bg-red-50 shrink-0">
          <div className="flex items-center gap-4">
            <span className="text-sm font-semibold text-red-800">
              📄 Original statement — READ ONLY
            </span>
            <span className={`text-xs font-mono ${timerColor}`}>
              ⏱ {mm}:{ss}
            </span>
          </div>
          <button
            onClick={() => handleClose("user_closed")}
            className="text-sm text-red-700 hover:text-red-900 underline"
          >
            Close
          </button>
        </div>

        {/* ── Content ── */}
        <div className="relative z-20 flex-1 overflow-y-auto p-5 space-y-4">

          {/* Original narrative */}
          {content.grievance_description ? (
            <div>
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1.5">
                Original Statement
              </div>
              <div className="text-sm text-gray-800 leading-relaxed bg-gray-50 rounded-lg p-4 border border-gray-200">
                {String(content.grievance_description)}
              </div>
            </div>
          ) : (
            <div className="text-sm text-gray-400 italic">
              Original narrative not available in this environment.
            </div>
          )}

          {/* Complainant details */}
          {(content.complainant_name || content.phone_number || content.email || content.address) && (
            <div>
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1.5">
                Complainant Details
              </div>
              <div className="text-sm bg-gray-50 rounded-lg p-4 border border-gray-200 space-y-1.5">
                {content.complainant_name && (
                  <div>
                    <span className="text-gray-400">Name: </span>
                    <span className="text-gray-800">{String(content.complainant_name)}</span>
                  </div>
                )}
                {content.phone_number && (
                  <div>
                    <span className="text-gray-400">Phone: </span>
                    <span className="text-gray-800 font-mono">{String(content.phone_number)}</span>
                  </div>
                )}
                {content.email && (
                  <div>
                    <span className="text-gray-400">Email: </span>
                    <span className="text-gray-800">{String(content.email)}</span>
                  </div>
                )}
                {content.address && (
                  <div>
                    <span className="text-gray-400">Address: </span>
                    <span className="text-gray-800">{String(content.address)}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Audit notice */}
          <div className="text-xs text-gray-400 italic border-t border-gray-100 pt-3">
            Session {session.reveal_session_id ?? "—"} · This access is logged and audited.
            Content will auto-hide when the timer expires.
          </div>
        </div>

        {/* ── TTL progress bar ── */}
        <div className="relative z-20 h-1.5 bg-gray-100 shrink-0">
          <div
            className={`h-full transition-all duration-500 ${barColor}`}
            style={{ width: `${pctLeft}%` }}
          />
        </div>
      </div>
    </div>
  );
}
