"use client";

import { useEffect, useState } from "react";
import {
  EMPTY_TICKET_LIST_FILTERS,
  filedPresetLabel,
  listPackages,
  listProjects,
  ticketListFiltersActive,
  type FiledDatePreset,
  type PackageItem,
  type ProjectItem,
  type TicketListFilterValues,
} from "@/lib/api";
import { X } from "lucide-react";

const PRIORITIES = ["NORMAL", "HIGH", "CRITICAL"] as const;

const FILED_PRESET_CHIPS: { value: Exclude<FiledDatePreset, "" | "custom">; label: string }[] = [
  { value: "today", label: "Today" },
  { value: "2d", label: "2d" },
  { value: "7d", label: "7d" },
  { value: "30d", label: "30d" },
  { value: "month", label: "This month" },
];

const fieldCls =
  "w-full border border-gray-300 rounded-xl px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500";

export function MobileTicketFiltersSheet({
  open,
  values,
  onChange,
  onClose,
  onApply,
}: {
  open: boolean;
  values: TicketListFilterValues;
  onChange: (next: TicketListFilterValues) => void;
  onClose: () => void;
  onApply: () => void;
}) {
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [packages, setPackages] = useState<PackageItem[]>([]);

  useEffect(() => {
    if (!open) return;
    listProjects().then(setProjects).catch(() => setProjects([]));
  }, [open]);

  useEffect(() => {
    if (!values.projectCode) {
      setPackages([]);
      return;
    }
    const project = projects.find((p) => p.short_code === values.projectCode);
    if (!project) {
      setPackages([]);
      return;
    }
    listPackages(project.project_id).then(setPackages).catch(() => setPackages([]));
  }, [values.projectCode, projects]);

  if (!open) return null;

  function patch(partial: Partial<TicketListFilterValues>) {
    const next = { ...values, ...partial };
    if (partial.projectCode !== undefined && partial.projectCode !== values.projectCode) {
      next.packageId = "";
    }
    if (partial.filedPreset !== undefined && partial.filedPreset !== "custom") {
      next.createdFrom = "";
      next.createdTo = "";
    }
    onChange(next);
  }

  function toggleFiledPreset(preset: FiledDatePreset) {
    if (values.filedPreset === preset) {
      patch({ filedPreset: "", createdFrom: "", createdTo: "" });
    } else {
      patch({ filedPreset: preset });
    }
  }

  const active = ticketListFiltersActive(values);

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end">
      <button
        type="button"
        className="absolute inset-0 bg-black/40"
        aria-label="Close filters"
        onClick={onClose}
      />
      <div className="relative bg-white rounded-t-2xl shadow-xl max-h-[85vh] flex flex-col safe-area-bottom">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 shrink-0">
          <h2 className="text-base font-semibold text-gray-900">Filter tickets</h2>
          <button type="button" onClick={onClose} className="p-2 text-gray-500" aria-label="Close">
            <X size={20} />
          </button>
        </div>

        <div className="overflow-y-auto px-4 py-4 space-y-4 flex-1">
          <label className="block">
            <span className="text-xs font-medium text-gray-500 mb-1 block">Search</span>
            <input
              type="search"
              value={values.q}
              onChange={(e) => patch({ q: e.target.value })}
              placeholder="ID, summary, assignee…"
              className={fieldCls}
            />
          </label>

          <label className="block">
            <span className="text-xs font-medium text-gray-500 mb-1 block">Priority</span>
            <select
              value={values.priority}
              onChange={(e) => patch({ priority: e.target.value })}
              className={fieldCls}
            >
              <option value="">Any priority</option>
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-xs font-medium text-gray-500 mb-1 block">SLA</span>
            <select value={values.sla} onChange={(e) => patch({ sla: e.target.value })} className={fieldCls}>
              <option value="">Any SLA status</option>
              <option value="overdue">Overdue</option>
              <option value="not_overdue">On track</option>
            </select>
          </label>

          <label className="block">
            <span className="text-xs font-medium text-gray-500 mb-1 block">Project</span>
            <select
              value={values.projectCode}
              onChange={(e) => patch({ projectCode: e.target.value })}
              className={fieldCls}
            >
              <option value="">All projects</option>
              {projects.map((p) => (
                <option key={p.project_id} value={p.short_code}>
                  {p.short_code} — {p.name}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-xs font-medium text-gray-500 mb-1 block">Package</span>
            <select
              value={values.packageId}
              onChange={(e) => patch({ packageId: e.target.value })}
              disabled={!values.projectCode}
              className={`${fieldCls} disabled:bg-gray-100 disabled:text-gray-400`}
            >
              <option value="">{values.projectCode ? "All packages" : "Select project first"}</option>
              {packages.map((p) => (
                <option key={p.package_id} value={p.package_id}>
                  {p.package_code} — {p.name}
                </option>
              ))}
            </select>
          </label>

          <div>
            <span className="text-xs font-medium text-gray-500 mb-2 block">Created</span>
            <div className="flex flex-wrap gap-2">
              {FILED_PRESET_CHIPS.map((chip) => (
                <button
                  key={chip.value}
                  type="button"
                  onClick={() => toggleFiledPreset(chip.value)}
                  className={`text-xs font-medium px-3 py-1.5 rounded-full border ${
                    values.filedPreset === chip.value
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-gray-600 border-gray-300"
                  }`}
                >
                  {chip.label}
                </button>
              ))}
              <button
                type="button"
                onClick={() => toggleFiledPreset("custom")}
                className={`text-xs font-medium px-3 py-1.5 rounded-full border ${
                  values.filedPreset === "custom"
                    ? "bg-blue-600 text-white border-blue-600"
                    : "bg-white text-gray-600 border-gray-300"
                }`}
              >
                Custom…
              </button>
            </div>
          </div>

          {values.filedPreset === "custom" && (
            <div className="grid grid-cols-2 gap-2">
              <label className="block">
                <span className="text-xs text-gray-500 mb-1 block">From</span>
                <input
                  type="date"
                  value={values.createdFrom}
                  onChange={(e) => patch({ createdFrom: e.target.value })}
                  className={fieldCls}
                />
              </label>
              <label className="block">
                <span className="text-xs text-gray-500 mb-1 block">To</span>
                <input
                  type="date"
                  value={values.createdTo}
                  onChange={(e) => patch({ createdTo: e.target.value })}
                  className={fieldCls}
                />
              </label>
            </div>
          )}

          {active && (
            <p className="text-xs text-blue-700 bg-blue-50 border border-blue-100 rounded-lg px-3 py-2">
              Active:{" "}
              {[
                values.q.trim() && `"${values.q.trim()}"`,
                values.priority,
                values.sla === "overdue" ? "Overdue" : values.sla === "not_overdue" ? "On track" : "",
                filedPresetLabel(values.filedPreset, values.createdFrom, values.createdTo),
                values.projectCode,
                values.packageId,
              ]
                .filter(Boolean)
                .join(" · ")}
            </p>
          )}
        </div>

        <div className="flex gap-2 px-4 py-3 border-t border-gray-100 shrink-0 pb-safe-bottom">
          <button
            type="button"
            onClick={() => onChange(EMPTY_TICKET_LIST_FILTERS)}
            className="flex-1 py-2.5 text-sm font-medium text-gray-600 border border-gray-300 rounded-xl"
          >
            Clear all
          </button>
          <button
            type="button"
            onClick={() => {
              onApply();
              onClose();
            }}
            className="flex-1 py-2.5 text-sm font-semibold text-white bg-blue-600 rounded-xl"
          >
            Apply filters
          </button>
        </div>
      </div>
    </div>
  );
}
