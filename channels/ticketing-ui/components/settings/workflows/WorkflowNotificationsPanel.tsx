"use client";

/**
 * <WorkflowNotificationsPanel> — per-workflow notification rules matrix
 * (event × tier × channel), per Spec 12 §4. SEAH workflows expose a reduced event set.
 *
 * Extracted verbatim from `app/settings/page.tsx` (T3-05) — no behaviour change.
 */
import React, { useState, useEffect } from "react";
import { getNotificationRules, saveNotificationRules, type NotificationRulesValue } from "@/lib/api";
import { friendlyError } from "@/components/settings/lib/friendlyError";
import {
  NOTIFICATION_EVENTS,
  SEAH_EVENTS,
  NOTIF_TIERS,
  NOTIF_CHANNELS,
} from "@/components/settings/workflows/workflowHelpers";

export function WorkflowNotificationsPanel({ workflowSlug }: { workflowSlug: "standard" | "seah" }) {
  const [open, setOpen] = useState(false);
  const [rules, setRules] = useState<Record<string, Record<string, string[]>>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const events = workflowSlug === "seah"
    ? NOTIFICATION_EVENTS.filter(e => SEAH_EVENTS.has(e.key))
    : NOTIFICATION_EVENTS;

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    getNotificationRules()
      .then(value => setRules(value[workflowSlug] ?? {}))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [open, workflowSlug]);

  function toggle(event: string, tier: string, channel: string) {
    setRules(prev => {
      const evRules = { ...prev };
      const tierChannels: string[] = [...(evRules[event]?.[tier] ?? [])];
      const idx = tierChannels.indexOf(channel);
      if (idx >= 0) tierChannels.splice(idx, 1); else tierChannels.push(channel);
      return { ...evRules, [event]: { ...(evRules[event] ?? {}), [tier]: tierChannels } };
    });
  }

  async function handleSave() {
    setSaving(true);
    setErr("");
    try {
      const current = await getNotificationRules().catch(() => ({} as NotificationRulesValue));
      const fullValue = { ...current, [workflowSlug]: rules };
      await saveNotificationRules(fullValue);
      setSaved(true); setTimeout(() => setSaved(false), 2000);
    } catch (e: unknown) {
      setErr(friendlyError(e));
    } finally {
      setSaving(false);
    }
  }

  const isChecked = (event: string, tier: string, ch: string) =>
    (rules[event]?.[tier] ?? []).includes(ch);

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden mt-2">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition text-sm font-medium text-gray-700"
      >
        <span>Notification rules — {workflowSlug === "seah" ? "SEAH" : "Standard"}</span>
        <span className="text-gray-400 text-xs">{open ? "▲ collapse" : "▼ expand"}</span>
      </button>

      {open && (
        <div className="p-4">
          {loading ? (
            <div className="text-xs text-gray-400 text-center py-4">Loading…</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr>
                    <th className="text-left font-medium text-gray-500 pb-2 pr-4 whitespace-nowrap">Event</th>
                    {NOTIF_TIERS.map(tier => (
                      <th key={tier} className="text-center font-medium text-gray-500 pb-2 px-2 capitalize min-w-[90px]" colSpan={3}>
                        {tier}
                      </th>
                    ))}
                  </tr>
                  <tr>
                    <th />
                    {NOTIF_TIERS.map(tier =>
                      NOTIF_CHANNELS.map(ch => (
                        <th key={`${tier}-${ch}`} className="text-center text-[10px] text-gray-400 pb-2 px-1 uppercase">{ch}</th>
                      ))
                    )}
                  </tr>
                </thead>
                <tbody>
                  {events.map((ev, i) => (
                    <tr key={ev.key} className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                      <td className="py-1.5 pr-4 font-medium text-gray-700 whitespace-nowrap">{ev.label}</td>
                      {NOTIF_TIERS.map(tier =>
                        NOTIF_CHANNELS.map(ch => (
                          <td key={`${tier}-${ch}`} className="text-center py-1.5 px-1">
                            <button
                              type="button"
                              onClick={() => toggle(ev.key, tier, ch)}
                              className={`w-5 h-5 rounded border flex items-center justify-center mx-auto transition ${
                                isChecked(ev.key, tier, ch)
                                  ? "bg-blue-600 border-blue-600 text-white"
                                  : "border-gray-300 text-transparent hover:border-blue-400"
                              }`}
                            >
                              ✓
                            </button>
                          </td>
                        ))
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {err && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-2 py-1 mt-3">{err}</p>
          )}

          <div className="flex justify-between items-center mt-4 pt-3 border-t border-gray-100">
            <p className="text-[11px] text-gray-400">Changes apply to new events only — in-flight tickets unaffected.</p>
            <button onClick={handleSave} disabled={saving || loading}
              className={`text-xs px-4 py-1.5 rounded font-medium transition ${
                saved ? "bg-green-600 text-white" : "bg-blue-600 text-white hover:bg-blue-700"
              } disabled:opacity-50`}>
              {saved ? "✓ Saved" : saving ? "Saving…" : "Save rules"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
