"use client";

import { useEffect, useRef, useState } from "react";
import { listLocations, type LocationNode } from "@/lib/api";

const LOC_LEVEL_LABELS: Record<number, string> = {
  1: "Province",
  2: "District",
  3: "Municipality",
};

const LOC_LEVEL_COLORS: Record<number, string> = {
  1: "bg-purple-100 text-purple-700",
  2: "bg-blue-100 text-blue-700",
  3: "bg-green-100 text-green-700",
};

/**
 * Autocomplete that searches the location tree (province / district / municipality).
 * Calls GET /api/v1/locations?q=<text> with a 220 ms debounce.
 */
export function LocationSearch({
  country = "NP",
  placeholder,
  excludeCodes = [],
  onSelect,
}: {
  country?: string;
  placeholder?: string;
  excludeCodes?: string[];
  onSelect: (code: string, name: string) => void;
}) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<LocationNode[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const excludeKey = excludeCodes.join(",");

  function getName(node: LocationNode) {
    return node.translations.find((t) => t.lang_code === "en")?.name ?? node.location_code;
  }

  useEffect(() => {
    if (q.trim().length < 2) {
      setHits([]);
      setOpen(false);
      return;
    }
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await listLocations({ country, q: q.trim(), limit: 8, active_only: true });
        setHits(res.filter((n) => !excludeCodes.includes(n.location_code)));
        setOpen(true);
      } catch {
        setHits([]);
      } finally {
        setLoading(false);
      }
    }, 220);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, country, excludeKey]);

  function handleSelect(node: LocationNode) {
    onSelect(node.location_code, getName(node));
    setQ("");
    setHits([]);
    setOpen(false);
  }

  return (
    <div className="relative">
      <div className="flex items-center gap-1.5 border border-gray-300 rounded px-2.5 py-1.5 focus-within:ring-1 focus-within:ring-blue-400 bg-white">
        <span className="text-gray-400 text-xs shrink-0 select-none">⌕</span>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onBlur={() => setTimeout(() => setOpen(false), 180)}
          onFocus={() => hits.length > 0 && setOpen(true)}
          placeholder={placeholder ?? "Search province, district or municipality…"}
          className="flex-1 text-sm bg-transparent outline-none min-w-0"
        />
        {loading && <span className="text-xs text-gray-300 animate-pulse shrink-0">…</span>}
        {q && (
          <button
            type="button"
            onClick={() => {
              setQ("");
              setHits([]);
              setOpen(false);
            }}
            className="text-gray-300 hover:text-gray-500 text-base leading-none shrink-0"
          >
            ×
          </button>
        )}
      </div>

      {open && hits.length > 0 && (
        <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden">
          {hits.map((node) => (
            <button
              key={node.location_code}
              type="button"
              onMouseDown={() => handleSelect(node)}
              className="w-full text-left px-3 py-2 hover:bg-blue-50 flex items-center gap-2 border-t border-gray-50 first:border-t-0 transition-colors"
            >
              <span
                className={`text-xs px-1.5 py-0.5 rounded font-medium shrink-0 ${LOC_LEVEL_COLORS[node.level_number] ?? "bg-gray-100 text-gray-600"}`}
              >
                {LOC_LEVEL_LABELS[node.level_number] ?? `L${node.level_number}`}
              </span>
              <span className="text-sm text-gray-800 flex-1 min-w-0 truncate">{getName(node)}</span>
              <span className="text-xs font-mono text-gray-400 shrink-0">{node.location_code}</span>
            </button>
          ))}
        </div>
      )}

      {open && q.trim().length >= 2 && !loading && hits.length === 0 && (
        <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg px-3 py-2.5">
          <span className="text-sm text-gray-400 italic">No locations match &ldquo;{q}&rdquo;</span>
        </div>
      )}
    </div>
  );
}

