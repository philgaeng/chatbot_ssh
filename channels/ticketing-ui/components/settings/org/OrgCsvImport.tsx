"use client";

/**
 * <OrgCsvImport> — whole-file validate → preview → single-transaction import
 * (DESIGN §4.2, Frame 02; OC-01 endpoint). The server validates the entire file
 * first; on any error nothing is written and it returns 422 {message, errors[]}.
 *
 * `importOrganizations` throws on a non-2xx response with the raw body embedded in
 * the Error message, so a failed dry-run/import is caught here and its per-row errors
 * are pulled out and rendered as friendly lines (never a raw JSON dump).
 */

import { useState } from "react";

import {
  importOrganizations,
  getOrgImportTemplateCsvUrl,
  type OrgImportResult,
} from "@/lib/api";
import { text as textTokens } from "@/lib/design-tokens";
import { ErrorNotice } from "@/components/shared/ErrorNotice";

/** Pull a `{message, errors[]}` payload out of a thrown import Error, best-effort. */
function extractRowErrors(err: unknown): { message: string | null; errors: string[] } {
  const raw = err instanceof Error ? err.message : String(err);
  const start = raw.indexOf("{");
  if (start === -1) return { message: raw || null, errors: [] };
  try {
    const parsed = JSON.parse(raw.slice(start)) as {
      message?: string;
      errors?: unknown;
      detail?: unknown;
    };
    // R5 (BUILD-REVIEW M3a): FastAPI nests the structured 422 under `detail`:
    // {"detail":{"message":..,"errors":[..]}}. Unwrap it (top-level was never populated).
    const d = parsed.detail;
    const src =
      d && typeof d === "object" && !Array.isArray(d)
        ? (d as { message?: string; errors?: unknown })
        : parsed;
    const errors = Array.isArray(src.errors)
      ? src.errors.map((e) => String(e))
      : Array.isArray(d)
        ? d.map((e) => String(e))
        : [];
    const message =
      typeof src.message === "string"
        ? src.message
        : typeof d === "string"
          ? d
          : null;
    return { message, errors };
  } catch {
    return { message: raw || null, errors: [] };
  }
}

export function OrgCsvImport({
  onImported,
  onClose,
}: {
  /** Called after a successful (non-dry-run) import so the tree can refresh. */
  onImported: () => void;
  onClose: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<OrgImportResult | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [rowErrors, setRowErrors] = useState<string[]>([]);
  const [done, setDone] = useState<OrgImportResult | null>(null);

  function reset(f: File | null) {
    setFile(f);
    setPreview(null);
    setError(null);
    setRowErrors([]);
    setDone(null);
  }

  async function run(dryRun: boolean) {
    if (!file) return;
    setBusy(true);
    setError(null);
    setRowErrors([]);
    try {
      const result = await importOrganizations(file, { dry_run: dryRun });
      if (dryRun) {
        setPreview(result);
      } else {
        setDone(result);
        onImported();
      }
    } catch (e) {
      const { message, errors } = extractRowErrors(e);
      setRowErrors(errors);
      setError(errors.length > 0 ? (message ?? "Some rows could not be imported.") : e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="max-h-[90vh] w-full max-w-lg overflow-hidden rounded-xl bg-white shadow-xl">
        <div className="flex items-center justify-between bg-slate-700 px-6 py-4 text-white">
          <div className="font-semibold">Import organisations from CSV</div>
          <button
            type="button"
            onClick={onClose}
            className="text-xl leading-none text-slate-300 hover:text-white"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="max-h-[calc(90vh-8rem)] space-y-4 overflow-y-auto p-6">
          <p className={`text-sm ${textTokens.body}`}>
            Upload a CSV of offices. The whole file is checked first — if anything is wrong,
            nothing is saved and each problem is listed by row.
          </p>

          <a
            href={getOrgImportTemplateCsvUrl()}
            className="inline-block text-sm font-medium text-blue-700 underline hover:no-underline"
          >
            Download the CSV template
          </a>

          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">CSV file</label>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => reset(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-gray-700 file:mr-3 file:rounded file:border-0 file:bg-blue-50 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-blue-700 hover:file:bg-blue-100"
            />
          </div>

          <ErrorNotice error={rowErrors.length > 0 ? null : error} />

          {rowErrors.length > 0 && (
            <div className="rounded border border-red-200 bg-red-50 px-3 py-2">
              <p className="text-sm font-medium text-red-800">
                Nothing was imported — please fix these and try again:
              </p>
              <ul className="mt-1 list-disc space-y-0.5 pl-5">
                {rowErrors.map((msg, i) => (
                  <li key={i} className="text-sm text-red-700">
                    {msg}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {preview && !done && (
            <div className="rounded border border-blue-200 bg-blue-50 px-3 py-2">
              <p className="text-sm font-medium text-blue-800">
                Preview looks good — {preview.organizations_upserted}{" "}
                {preview.organizations_upserted === 1 ? "office" : "offices"} will be added or updated.
              </p>
              {preview.errors.length > 0 && (
                <ul className="mt-1 list-disc space-y-0.5 pl-5">
                  {preview.errors.map((msg, i) => (
                    <li key={i} className="text-sm text-blue-700">
                      {msg}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {done && (
            <div className="rounded border border-green-200 bg-green-50 px-3 py-2">
              <p className="text-sm font-medium text-green-700">
                Imported {done.organizations_upserted}{" "}
                {done.organizations_upserted === 1 ? "office" : "offices"}.
              </p>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 border-t border-gray-100 px-6 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded px-4 py-1.5 text-sm text-gray-500 hover:text-gray-700"
          >
            {done ? "Close" : "Cancel"}
          </button>
          {!done && (
            <>
              <button
                type="button"
                onClick={() => void run(true)}
                disabled={!file || busy}
                className="rounded border border-blue-300 px-4 py-1.5 text-sm font-medium text-blue-700 transition hover:bg-blue-50 disabled:opacity-50"
              >
                {busy ? "Checking…" : "Preview"}
              </button>
              <button
                type="button"
                onClick={() => void run(false)}
                disabled={!file || busy || !preview}
                className="rounded bg-blue-600 px-4 py-1.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
              >
                {busy ? "Importing…" : "Import"}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default OrgCsvImport;
