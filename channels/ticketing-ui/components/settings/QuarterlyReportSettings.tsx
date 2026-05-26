"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Loader2, Trash2 } from "lucide-react";
import {
  currentQuarterKey,
  deleteQuarterlyAssignment,
  getQuarterlyPlan,
  listRoles,
  saveQuarterlySchedule,
  type QuarterlyPlanResponse,
} from "@/lib/api";

function nextQuarterKey(qk: string): string {
  const [y, q] = qk.split("-Q").map(Number);
  if (q === 4) return `${y + 1}-Q1`;
  return `${y}-Q${q + 1}`;
}

function prevQuarterKey(qk: string): string {
  const [y, q] = qk.split("-Q").map(Number);
  if (q === 1) return `${y - 1}-Q4`;
  return `${y}-Q${q - 1}`;
}

export function QuarterlyReportSettings() {
  const [quarterKey, setQuarterKey] = useState(currentQuarterKey());
  const [plan, setPlan] = useState<QuarterlyPlanResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dayOfMonth, setDayOfMonth] = useState(5);
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [scheduleSaved, setScheduleSaved] = useState(false);
  const [roleLabels, setRoleLabels] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [p, roles] = await Promise.all([
        getQuarterlyPlan(quarterKey),
        listRoles().catch(() => []),
      ]);
      setPlan(p);
      setDayOfMonth(p.schedule.day_of_month);
      const labels: Record<string, string> = {};
      for (const r of roles) labels[r.role_key] = r.display_name || r.role_key;
      setRoleLabels(labels);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load quarterly plan");
      setPlan(null);
    } finally {
      setLoading(false);
    }
  }, [quarterKey]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleSaveSchedule() {
    setSavingSchedule(true);
    setScheduleSaved(false);
    try {
      await saveQuarterlySchedule(dayOfMonth);
      setScheduleSaved(true);
      setTimeout(() => setScheduleSaved(false), 2500);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSavingSchedule(false);
    }
  }

  async function handleDelete(assignmentId: string) {
    if (!confirm("Remove this saved report from the quarterly plan?")) return;
    setError("");
    try {
      await deleteQuarterlyAssignment(assignmentId);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  }

  const maxPerRole = plan?.max_per_role ?? 3;
  const allowedRoles = plan?.limits.allowed_recipient_roles;

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h2 className="text-base font-semibold text-gray-800 mb-0.5">Quarterly report plan</h2>
        <p className="text-xs text-gray-500 leading-relaxed">
          Save up to <strong>{maxPerRole}</strong> reports per role per calendar quarter. On the
          scheduled day, each saved report is emailed once to every officer with that role (one
          attachment per email).
        </p>
        {plan?.limits && (
          <p className="text-xs text-gray-600 mt-2">
            IT cap: {plan.limits.max_reports_per_role_per_quarter} reports / role / quarter.
            {!plan.limits.quarterly_email_enabled && (
              <span className="text-red-600"> Email dispatch is disabled.</span>
            )}
          </p>
        )}
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          className="text-sm border border-gray-300 rounded px-2 py-1"
          onClick={() => setQuarterKey(prevQuarterKey(quarterKey))}
        >
          ←
        </button>
        <span className="text-sm font-semibold text-gray-800">{quarterKey}</span>
        <button
          type="button"
          className="text-sm border border-gray-300 rounded px-2 py-1"
          onClick={() => setQuarterKey(nextQuarterKey(quarterKey))}
        >
          →
        </button>
      </div>

      {error && (
        <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>
      )}

      <section className="bg-white border border-gray-200 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">Send schedule</h3>
        <label className="text-xs text-gray-500 block mb-1">Day of month (Jan / Apr / Jul / Oct)</label>
        <div className="flex items-center gap-3">
          <input
            type="number"
            min={1}
            max={28}
            value={dayOfMonth}
            onChange={(e) => setDayOfMonth(Number(e.target.value))}
            className="w-24 text-sm border border-gray-300 rounded px-2 py-1.5"
          />
          <button
            type="button"
            onClick={handleSaveSchedule}
            disabled={savingSchedule}
            className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded disabled:opacity-50"
          >
            {savingSchedule ? "Saving…" : "Save"}
          </button>
          {scheduleSaved && <span className="text-xs text-green-600">✓ Saved</span>}
        </div>
      </section>

      {loading ? (
        <p className="text-sm text-gray-500 flex items-center gap-2">
          <Loader2 size={16} className="animate-spin" /> Loading plan…
        </p>
      ) : !plan || plan.roles.length === 0 ? (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-5 text-sm text-gray-600">
          <p>No reports configured for {quarterKey} yet.</p>
          <p className="mt-2">
            <Link href="/reports" className="text-blue-600 hover:underline">
              Reports → Pivot table
            </Link>{" "}
            — build a report, then <strong>Save for quarterly send</strong> and pick role(s).
          </p>
          {allowedRoles && (
            <p className="text-xs text-gray-500 mt-2">
              Allowed roles: {allowedRoles.join(", ")}
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {plan.roles.map((block) => (
            <section key={block.role_key} className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold text-gray-800">
                  {roleLabels[block.role_key] ?? block.role_key}
                </h3>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full ${
                    block.count >= block.max
                      ? "bg-amber-100 text-amber-800"
                      : "bg-gray-100 text-gray-600"
                  }`}
                >
                  {block.count} / {block.max} reports
                </span>
              </div>
              <ul className="space-y-2">
                {block.assignments.map((a) => (
                  <li
                    key={a.id}
                    className="flex items-center justify-between text-sm border border-gray-100 rounded px-3 py-2"
                  >
                    <div>
                      <span className="font-medium text-gray-800">{a.name}</span>
                      <span className="text-xs text-gray-500 ml-2">
                        {a.template.kind === "pivot" ? "Pivot" : "Overview (4 sheets)"}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleDelete(a.id)}
                      className="text-gray-400 hover:text-red-600 p-1"
                      title="Remove"
                    >
                      <Trash2 size={14} />
                    </button>
                  </li>
                ))}
              </ul>
              {block.count >= block.max && (
                <p className="text-xs text-amber-700 mt-2">
                  Slot full — remove a report or pick another role to add more.
                </p>
              )}
            </section>
          ))}
        </div>
      )}

      <p className="text-xs text-gray-500">
        <Link href="/reports" className="text-blue-600 hover:underline">
          Add reports from the Reports page
        </Link>
      </p>
    </div>
  );
}
