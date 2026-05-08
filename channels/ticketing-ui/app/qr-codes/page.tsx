"use client";

import { useEffect, useState } from "react";
import { listMyPackagesQr, type PackageQrItem } from "@/lib/api";
import { IconQrCodes, IconDownload } from "@/lib/icons";

// ── QR image URL via qrserver.com (no npm needed) ─────────────────────────────
function qrImageUrl(data: string, size = 220) {
  return `https://api.qrserver.com/v1/create-qr-code/?size=${size}x${size}&margin=10&data=${encodeURIComponent(data)}`;
}

// ── Copy-to-clipboard helper ──────────────────────────────────────────────────
function useCopy() {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  function copy(text: string, key: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2000);
    });
  }
  return { copy, copiedKey };
}

// ── Package QR card ───────────────────────────────────────────────────────────
function PackageQrCard({ item }: { item: PackageQrItem }) {
  const { copy, copiedKey } = useCopy();
  const imgUrl = qrImageUrl(item.scan_url);

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden flex flex-col">
      {/* Card header */}
      <div className="bg-slate-700 text-white px-4 py-3">
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-sm font-semibold">{item.package_code}</span>
          <span className="text-xs text-slate-300">{item.project_code}</span>
        </div>
        <p className="text-xs text-slate-300 mt-0.5 truncate">{item.name}</p>
      </div>

      {/* QR code image */}
      <div className="flex justify-center px-6 pt-5 pb-3">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={imgUrl}
          alt={`QR code for ${item.package_code}`}
          width={220}
          height={220}
          className="rounded border border-gray-100"
        />
      </div>

      {/* Token + URL row */}
      <div className="px-4 pb-2 space-y-1">
        <div className="flex items-center justify-between bg-gray-50 rounded px-3 py-1.5">
          <span className="font-mono text-xs text-gray-500">token</span>
          <span className="font-mono text-sm text-gray-800">{item.token}</span>
        </div>
        <button
          onClick={() => copy(item.scan_url, item.token)}
          className="w-full text-left bg-gray-50 rounded px-3 py-1.5 hover:bg-blue-50 transition group"
        >
          <span className="font-mono text-[11px] text-gray-500 break-all leading-tight">
            {item.scan_url}
          </span>
          <span className="block text-xs text-blue-500 mt-0.5 group-hover:text-blue-700">
            {copiedKey === item.token ? "✓ Copied!" : "Copy URL"}
          </span>
        </button>
      </div>

      {/* Actions */}
      <div className="px-4 pb-4 pt-1">
        <a
          href={qrImageUrl(item.scan_url, 600)}
          download={`qr-${item.package_code.replace(/\//g, "-")}.png`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-center gap-1.5 w-full bg-slate-700 hover:bg-slate-800 text-white text-sm font-medium py-2 rounded-lg transition"
        >
          <IconDownload size={14} strokeWidth={2} />
          Download PNG
        </a>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function QrCodesPage() {
  const [items, setItems]     = useState<PackageQrItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState("");

  useEffect(() => {
    listMyPackagesQr()
      .then(setItems)
      .catch((e) => setError(e?.message ?? "Failed to load packages"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <IconQrCodes size={20} strokeWidth={1.75} className="text-slate-700" />
            <h1 className="text-xl font-bold text-gray-900">QR Codes</h1>
          </div>
          <p className="text-sm text-gray-500">
            Scan codes for your packages. Post them at site offices so complainants can file grievances directly.
          </p>
        </div>
        <button
          onClick={() => window.print()}
          className="hidden sm:flex items-center gap-1.5 text-sm border border-gray-300 text-gray-600 hover:bg-gray-50 px-4 py-2 rounded-lg transition"
        >
          🖨 Print all
        </button>
      </div>

      {/* States */}
      {loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-gray-100 rounded-xl h-80 animate-pulse" />
          ))}
        </div>
      )}

      {!loading && error && (
        <div className="text-center py-16">
          <p className="text-red-600 text-sm">{error}</p>
          <button
            onClick={() => { setError(""); setLoading(true); listMyPackagesQr().then(setItems).catch((e) => setError(e?.message ?? "Failed")).finally(() => setLoading(false)); }}
            className="mt-3 text-sm text-blue-600 hover:underline"
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="text-center py-16">
          <IconQrCodes size={40} strokeWidth={1} className="text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 text-sm">No packages assigned to your account.</p>
          <p className="text-gray-400 text-xs mt-1">Contact your administrator to be assigned to a package.</p>
        </div>
      )}

      {!loading && !error && items.length > 0 && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {items.map((item) => (
              <PackageQrCard key={item.package_id} item={item} />
            ))}
          </div>
          <p className="text-xs text-gray-400 text-center mt-6">
            Each QR code links directly to the GRM chatbot pre-filled with this package's project and location.
            Post it at your site office, works camp, or notice board.
          </p>
        </>
      )}
    </div>
  );
}
