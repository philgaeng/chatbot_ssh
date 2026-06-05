"use client";

import { useMemo, useState } from "react";
import { ChevronDown, ChevronUp, X } from "lucide-react";
import type { GrievanceCategoryOption } from "@/lib/api";

interface GrievanceCategoryMultiSelectProps {
  value: string[];
  onChange: (next: string[]) => void;
  options: GrievanceCategoryOption[];
  loading?: boolean;
  loadError?: string | null;
}

export function GrievanceCategoryMultiSelect({
  value,
  onChange,
  options,
  loading = false,
  loadError = null,
}: GrievanceCategoryMultiSelectProps) {
  const [open, setOpen] = useState(false);

  const optionKeys = useMemo(() => new Set(options.map((o) => o.key)), [options]);

  const extraSelected = useMemo(
    () => value.filter((v) => !optionKeys.has(v)),
    [value, optionKeys],
  );

  const grouped = useMemo(() => {
    const map = new Map<string, GrievanceCategoryOption[]>();
    for (const opt of options) {
      const group = opt.classification?.trim() || "Other";
      if (!map.has(group)) map.set(group, []);
      map.get(group)!.push(opt);
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [options]);

  function toggle(key: string) {
    onChange(
      value.includes(key) ? value.filter((c) => c !== key) : [...value, key],
    );
  }

  function remove(key: string) {
    onChange(value.filter((c) => c !== key));
  }

  return (
    <div className="space-y-2">
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {value.map((cat) => (
            <span
              key={cat}
              className="inline-flex items-center gap-1 max-w-full rounded-full bg-blue-50 border border-blue-200 text-blue-900 text-xs px-2.5 py-1"
            >
              <span className="truncate">{cat}</span>
              <button
                type="button"
                onClick={() => remove(cat)}
                className="shrink-0 text-blue-600 hover:text-blue-800"
                aria-label={`Remove ${cat}`}
              >
                <X size={12} />
              </button>
            </span>
          ))}
        </div>
      )}

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        disabled={loading}
        className="w-full flex items-center justify-between gap-2 text-sm border border-slate-200 rounded-lg px-3 py-2.5 bg-white hover:bg-slate-50 disabled:opacity-50"
      >
        <span className="text-left text-gray-700">
          {loading
            ? "Loading categories…"
            : value.length === 0
              ? "Select one or more categories"
              : `${value.length} categor${value.length === 1 ? "y" : "ies"} selected`}
        </span>
        {open ? <ChevronUp size={16} className="shrink-0 text-gray-400" /> : <ChevronDown size={16} className="shrink-0 text-gray-400" />}
      </button>

      {loadError && (
        <p className="text-xs text-amber-700">{loadError}</p>
      )}

      {open && !loading && (
        <div className="border border-slate-200 rounded-lg bg-white max-h-56 overflow-y-auto">
          {extraSelected.length > 0 && (
            <div className="px-3 py-2 border-b border-amber-100 bg-amber-50/60">
              <p className="text-[10px] font-semibold text-amber-800 uppercase tracking-wide mb-1.5">
                On this case (not in taxonomy)
              </p>
              {extraSelected.map((cat) => (
                <label
                  key={cat}
                  className="flex items-start gap-2 py-1 text-xs text-gray-800 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={value.includes(cat)}
                    onChange={() => toggle(cat)}
                    className="mt-0.5 rounded border-gray-300"
                  />
                  <span>{cat}</span>
                </label>
              ))}
            </div>
          )}

          {grouped.length === 0 ? (
            <p className="px-3 py-4 text-xs text-gray-500 italic">
              No categories in database. Ask an admin to seed grievance_classification_taxonomy.
            </p>
          ) : (
            grouped.map(([group, items]) => (
              <div key={group} className="border-b border-gray-100 last:border-b-0">
                <p className="px-3 pt-2 pb-1 text-[10px] font-semibold text-gray-500 uppercase tracking-wide sticky top-0 bg-white">
                  {group}
                </p>
                {items.map((opt) => (
                  <label
                    key={opt.key}
                    className="flex items-start gap-2 px-3 py-1.5 text-xs text-gray-800 hover:bg-slate-50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={value.includes(opt.key)}
                      onChange={() => toggle(opt.key)}
                      className="mt-0.5 rounded border-gray-300"
                    />
                    <span>
                      {opt.label}
                      {opt.high_priority && (
                        <span className="ml-1 text-[10px] text-amber-700 font-medium">High priority</span>
                      )}
                    </span>
                  </label>
                ))}
              </div>
            ))
          )}
        </div>
      )}

      <p className="text-[11px] text-gray-500">
        Choose from the official taxonomy; multiple categories allowed.
      </p>
    </div>
  );
}
