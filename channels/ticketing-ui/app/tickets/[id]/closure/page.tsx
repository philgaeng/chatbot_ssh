"use client";

import { use, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { getResolvedSummary, triggerResolvedSummary, type ResolvedSummaryResponse } from "@/lib/api";

function localizeClosurePublicUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    if (url.startsWith("/")) return url;
    const parsed = new URL(url);
    if (parsed.pathname.startsWith("/closure/")) {
      return `${parsed.pathname}${parsed.search}${parsed.hash}`;
    }
    return url;
  } catch {
    return url;
  }
}

export default function OfficerClosurePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [data, setData] = useState<ResolvedSummaryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [missing, setMissing] = useState(false);
  const [noResolutionRecord, setNoResolutionRecord] = useState(false);
  const [queueing, setQueueing] = useState(false);
  const [queued, setQueued] = useState(false);
  const [polling, setPolling] = useState(false);
  const pollAttempts = useRef(0);
  const autoQueuedOnce = useRef(false);

  const loadSummary = () =>
    getResolvedSummary(id)
      .then((res) => {
        setData(res);
        setError(null);
        setMissing(false);
        setNoResolutionRecord(false);
      })
      .catch((e) => {
        const msg = String(e);
        setData(null);
        if (msg.includes("API 404") && msg.includes("Resolved summary not found")) {
          setMissing(true);
          setNoResolutionRecord(false);
          setError(null);
          return;
        }
        if (msg.toLowerCase().includes("no resolution record")) {
          setMissing(false);
          setNoResolutionRecord(true);
          setPolling(false);
          setError(
            "This resolved ticket has no saved resolution record, so a closure summary cannot be generated. Open the case and complete resolution details first.",
          );
          return;
        }
        setPolling(false);
        setMissing(false);
        setNoResolutionRecord(false);
        setError(msg);
      });

  useEffect(() => {
    void loadSummary();
  }, [id]);

  useEffect(() => {
    if (!polling) return;
    const timer = window.setInterval(() => {
      pollAttempts.current += 1;
      void loadSummary();
      if (pollAttempts.current >= 30) {
        setPolling(false);
        setError("Summary generation is taking longer than expected. Please reopen this page shortly.");
      }
    }, 3000);
    return () => window.clearInterval(timer);
  }, [polling]);

  useEffect(() => {
    if (data?.generation_status === "complete") {
      setPolling(false);
      setMissing(false);
      setQueueing(false);
      setQueued(false);
      pollAttempts.current = 0;
      autoQueuedOnce.current = false;
      setError(null);
    }
  }, [data]);

  useEffect(() => {
    if (!missing || queueing || polling || queued || autoQueuedOnce.current) return;
    autoQueuedOnce.current = true;
    void handleQueueSummary();
  }, [missing, queueing, polling, queued]);

  async function handleQueueSummary() {
    setQueueing(true);
    setError(null);
    try {
      await triggerResolvedSummary(id, true);
      setQueued(true);
      setPolling(true);
      pollAttempts.current = 0;
      window.setTimeout(() => {
        void loadSummary();
      }, 1200);
    } catch (e) {
      setError(String(e));
    } finally {
      setQueueing(false);
    }
  }

  const pub = data?.summary_public_json as Record<string, string> | null | undefined;
  const complainantLink = localizeClosurePublicUrl(data?.closure_public_url);

  return (
    <div className="max-w-2xl mx-auto p-6">
      <Link href={`/tickets/${id}`} className="text-sm text-blue-600 hover:underline">← Back to case</Link>
      <h1 className="text-xl font-bold mt-4 mb-2">Case closure summary</h1>
      {error && <p className="text-red-600 text-sm">{error}</p>}
      {!data && !error && !missing && !noResolutionRecord && <p className="text-gray-500">Loading…</p>}
      {noResolutionRecord && !data && (
        <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-900">
          <p className="mb-3">
            This resolved ticket has no resolution record. A closure summary cannot be generated for it yet.
          </p>
          <Link
            href={`/tickets/${id}`}
            className="inline-block rounded border border-red-300 bg-white px-3 py-1.5 text-red-700 hover:bg-red-100"
          >
            Open case
          </Link>
        </div>
      )}
      {missing && !data && (
        <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 space-y-2">
          <p>This ticket is resolved, but its closure summary has not been generated yet.</p>
          {queued && (
            <p className="text-amber-700">
              Generation queued. This page will update automatically when summary generation is complete.
            </p>
          )}
          {(queueing || polling) && (
            <p className="text-amber-700">{queueing ? "Queueing summary generation..." : "Generating summary..."}</p>
          )}
        </div>
      )}
      {data && (
        <>
          <p className="text-sm text-gray-500 mb-4">
            Status: {data.generation_status}
            {complainantLink && (
              <> · <a href={complainantLink} className="text-blue-600 underline" target="_blank" rel="noreferrer">Complainant link</a></>
            )}
          </p>
          {pub && (
            <div className="space-y-4 text-sm">
              <section className="bg-white border rounded-lg p-4">
                <h2 className="font-semibold mb-2">Public view (complainant)</h2>
                <p><strong>Outcome:</strong> {pub.resolution_category_label}</p>
                <p className="mt-2 whitespace-pre-wrap">{pub.resolution_text_public}</p>
                {pub.findings_summary_public && (
                  <p className="mt-2 whitespace-pre-wrap text-gray-700">{pub.findings_summary_public}</p>
                )}
              </section>
            </div>
          )}
          {data.generation_status !== "complete" && (
            <p className="text-amber-700 text-sm mt-4">Summary is still generating. Refresh in a moment.</p>
          )}
        </>
      )}
    </div>
  );
}
