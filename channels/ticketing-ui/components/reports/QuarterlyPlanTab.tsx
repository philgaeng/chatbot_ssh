"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, Plus, Trash2 } from "lucide-react";
import {
  createQuarterlyAssignments,
  currentQuarterKey,
  deleteQuarterlyAssignment,
  getQuarterlyLibrary,
  getQuarterlyPlan,
  listRoles,
  saveQuarterlySchedule,
  type QuarterlyAssignment,
  type QuarterlyPlanResponse,
  type QuarterlyReportLibraryItem,
} from "@/lib/api";

function nextQuarterKey(qk: string): string {
  const [y, q] = qk.split("-Q").map(Number);
  return q === 4 ? `${y + 1}-Q1` : `${y}-Q${q + 1}`;
}

function prevQuarterKey(qk: string): string {
  const [y, q] = qk.split("-Q").map(Number);
  return q === 1 ? `${y - 1}-Q4` : `${y}-Q${q - 1}`;
}

type ReportGroup = {
  name: string;
  kind: string;
  roles: { assignmentId: string; roleKey: string; label: string }[];
};

function groupAssignments(
  assignments: QuarterlyAssignment[],
  roleLabels: Record<string, string>,
): ReportGroup[] {
  const map = new Map<string, ReportGroup>();
  for (const a of assignments) {
    if (!map.has(a.name)) {
      map.set(a.name, {
        name: a.name,
        kind: a.template.kind,
        roles: [],
      });
    }
    map.get(a.name)!.roles.push({
      assignmentId: a.id,
      roleKey: a.role_key,
      label: roleLabels[a.role_key] ?? a.role_key,
    });
  }
  return Array.from(map.values()).sort((x, y) => x.name.localeCompare(y.name));
}

export function QuarterlyPlanTab({
  onError,
}: {
  onError: (msg: string | null) => void;
}) {
  const [quarterKey, setQuarterKey] = useState(currentQuarterKey());
  const [plan, setPlan] = useState<QuarterlyPlanResponse | null>(null);
  const [library, setLibrary] = useState<QuarterlyReportLibraryItem[]>([]);
  const [roleLabels, setRoleLabels] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [dayOfMonth, setDayOfMonth] = useState(5);
  const [savingSchedule, setSavingSchedule] = useState(false);

  const [selectedReportId, setSelectedReportId] = useState("");
  const [addRoles, setAddRoles] = useState<string[]>([]);
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    onError(null);
    try {
      const [p, lib, roles] = await Promise.all([
        getQuarterlyPlan(quarterKey),
        getQuarterlyLibrary(),
        listRoles().catch(() => []),
      ]);
      setPlan(p);
      setLibrary(lib);
      setDayOfMonth(p.schedule.day_of_month);
      const labels: Record<string, string> = {};
      for (const r of roles) labels[r.role_key] = r.display_name || r.role_key;
      setRoleLabels(labels);
      setSelectedReportId((prev) => {
        if (prev && lib.some((x) => x.id === prev)) return prev;
        return lib[0]?.id ?? "";
      });
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : "Failed to load quarterly plan");
    } finally {
      setLoading(false);
    }
  }, [quarterKey, onError]);

  useEffect(() => {
    load();
  }, [load]);

  const allAssignments = useMemo(() => {
    if (!plan) return [];
    return plan.roles.flatMap((r) => r.assignments);
  }, [plan]);

  const grouped = useMemo(
    () => groupAssignments(allAssignments, roleLabels),
    [allAssignments, roleLabels],
  );

  const roleChoices = useMemo(() => {
    const allowed = plan?.limits.allowed_recipient_roles;
    return Object.entries(roleLabels)
      .filter(([key]) => !allowed?.length || allowed.includes(key))
      .map(([key, label]) => ({ key, label }))
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [roleLabels, plan]);

  const slotsByRole = useMemo(() => {
    const m: Record<string, { count: number; max: number }> = {};
    if (!plan) return m;
    for (const r of plan.roles) {
      m[r.role_key] = { count: r.count, max: r.max };
    }
    for (const { key } of roleChoices) {
      if (!m[key]) m[key] = { count: 0, max: plan.max_per_role };
    }
    return m;
  }, [plan, roleChoices]);

  function toggleAddRole(roleKey: string) {
    setAddRoles((prev) =>
      prev.includes(roleKey) ? prev.filter((k) => k !== roleKey) : [...prev, roleKey],
    );
  }

  async function handleSaveSchedule() {
    setSavingSchedule(true);
    try {
      await saveQuarterlySchedule(dayOfMonth);
      await load();
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : "Failed to save schedule");
    } finally {
      setSavingSchedule(false);
    }
  }

  async function handleAddToPlan() {
    if (!selectedReportId) {
      onError("Choose a saved report.");
      return;
    }
    if (addRoles.length === 0) {
      onError("Choose at least one role to receive this report.");
      return;
    }
    setAdding(true);
    onError(null);
    try {
      await createQuarterlyAssignments({
        quarter_key: quarterKey,
        role_keys: addRoles,
        library_id: selectedReportId,
      });
      setAddRoles([]);
      await load();
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : "Failed to add to plan");
    } finally {
      setAdding(false);
    }
  }

  async function handleRemoveAssignment(assignmentId: string) {
    if (!confirm("Remove this role from the quarterly plan for this report?")) return;
    onError(null);
    try {
      await deleteQuarterlyAssignment(assignmentId);
      await load();
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : "Delete failed");
    }
  }

  const maxPerRole = plan?.max_per_role ?? 3;

  return (
    <div className="mt-4 space-y-6">
      <p className="text-sm text-gray-600">
        Plan which saved reports are emailed to which roles for each calendar quarter (max{" "}
        <strong>{maxPerRole}</strong> reports per role). Create report definitions on the{" "}
        <strong>Overview</strong> or <strong>Pivot table</strong> tabs first.
      </p>

      <div className="flex flex-wrap items-center gap-3">
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
        <span className="text-xs text-gray-500 ml-2">
          Send day:{" "}
          <input
            type="number"
            min={1}
            max={28}
            value={dayOfMonth}
            onChange={(e) => setDayOfMonth(Number(e.target.value))}
            className="w-12 border border-gray-300 rounded px-1 py-0.5 text-center"
          />{" "}
          of Jan / Apr / Jul / Oct
          <button
            type="button"
            onClick={handleSaveSchedule}
            disabled={savingSchedule}
            className="ml-2 text-blue-600 hover:underline disabled:opacity-50"
          >
            {savingSchedule ? "Saving…" : "Save"}
          </button>
        </span>
      </div>

      {loading ? (
        <p className="text-sm text-gray-500 flex items-center gap-2">
          <Loader2 size={16} className="animate-spin" /> Loading…
        </p>
      ) : (
        <>
          <section className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
              <h2 className="text-sm font-semibold text-gray-800">Scheduled for {quarterKey}</h2>
            </div>
            {grouped.length === 0 ? (
              <p className="text-sm text-gray-500 px-4 py-6">No reports scheduled yet for this quarter.</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-500 border-b border-gray-100">
                    <th className="px-4 py-2 font-medium">Report name</th>
                    <th className="px-4 py-2 font-medium">Format</th>
                    <th className="px-4 py-2 font-medium">Sends to roles</th>
                  </tr>
                </thead>
                <tbody>
                  {grouped.map((g) => (
                    <tr key={g.name} className="border-b border-gray-50 align-top">
                      <td className="px-4 py-3 font-medium text-gray-800">{g.name}</td>
                      <td className="px-4 py-3 text-gray-600">
                        {g.kind === "pivot" ? "Pivot table" : "Overview (4 sheets)"}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1.5">
                          {g.roles.map((r) => (
                            <span
                              key={r.assignmentId}
                              className="inline-flex items-center gap-1 text-xs bg-blue-50 text-blue-800 border border-blue-200 rounded-full pl-2 pr-1 py-0.5"
                            >
                              {r.label}
                              <button
                                type="button"
                                onClick={() => handleRemoveAssignment(r.assignmentId)}
                                className="p-0.5 hover:text-red-600 rounded"
                                title="Remove role"
                              >
                                <Trash2 size={12} />
                              </button>
                            </span>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="bg-white border border-blue-200 rounded-lg p-4">
            <h2 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-1">
              <Plus size={16} className="text-blue-600" /> Add to quarterly plan
            </h2>
            {library.length === 0 ? (
              <p className="text-sm text-gray-500">
                No saved reports yet. On the Overview or Pivot table tab, use{" "}
                <strong>Save to report library</strong>, then return here to assign roles.
              </p>
            ) : (
              <div className="space-y-4">
                <div>
                  <label className="text-xs font-medium text-gray-500 block mb-1">Saved report</label>
                  <select
                    value={selectedReportId}
                    onChange={(e) => setSelectedReportId(e.target.value)}
                    className="w-full max-w-md text-sm border border-gray-300 rounded px-2 py-2"
                  >
                    {library.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name} ({item.template.kind === "pivot" ? "Pivot" : "Overview"})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-500 block mb-2">
                    Send to roles (uses one slot per role for {quarterKey})
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {roleChoices.map((r) => {
                      const slot = slotsByRole[r.key];
                      const full = slot && slot.count >= slot.max;
                      const alreadyHas = grouped
                        .find((g) => g.name === library.find((l) => l.id === selectedReportId)?.name)
                        ?.roles.some((x) => x.roleKey === r.key);
                      return (
                        <label
                          key={r.key}
                          className={`inline-flex items-center gap-1.5 text-xs border rounded-full px-3 py-1 cursor-pointer ${
                            addRoles.includes(r.key)
                              ? "bg-blue-50 border-blue-300 text-blue-800"
                              : full && !alreadyHas
                                ? "bg-gray-100 border-gray-200 text-gray-400 cursor-not-allowed"
                                : "bg-gray-50 border-gray-200 text-gray-600"
                          }`}
                          title={
                            full && !alreadyHas
                              ? `${r.label} already has ${slot.max} reports this quarter`
                              : undefined
                          }
                        >
                          <input
                            type="checkbox"
                            className="sr-only"
                            disabled={full && !alreadyHas && !addRoles.includes(r.key)}
                            checked={addRoles.includes(r.key)}
                            onChange={() => toggleAddRole(r.key)}
                          />
                          {r.label}
                          {slot && (
                            <span className="opacity-70">
                              ({slot.count}/{slot.max})
                            </span>
                          )}
                        </label>
                      );
                    })}
                  </div>
                </div>
                <button
                  type="button"
                  disabled={adding || !selectedReportId || addRoles.length === 0}
                  onClick={handleAddToPlan}
                  className="text-sm bg-blue-600 text-white font-medium px-4 py-2 rounded-lg disabled:opacity-50"
                >
                  {adding ? "Adding…" : "Add to plan"}
                </button>
              </div>
            )}
          </section>

          {library.length > 0 && (
            <section className="text-xs text-gray-500">
              <p className="font-medium text-gray-600 mb-1">Report library ({library.length})</p>
              <ul className="list-disc pl-4 space-y-0.5">
                {library.map((item) => (
                  <li key={item.id}>
                    {item.name} — {item.template.kind === "pivot" ? "Pivot" : "Overview"}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}
