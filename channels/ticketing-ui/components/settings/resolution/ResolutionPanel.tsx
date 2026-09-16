// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * <ResolutionPanel> — what officers can choose when closing a case in this workflow (GRM-119,
 * `ui/08` frames 1–3). The one place resolution actions are managed.
 *
 * - Up to 8 actions, in order: reorder, remove, edit (where the viewer may), add from the actions this
 *   workflow can use, or create a new one.
 * - **Every change saves at once** and applies to the next case closed — the list is read live, not
 *   versioned by *Publish*.
 * - A sensitive workflow lists nothing: one line, no controls.
 *
 * The server decides everything; this renders the flags it returns (`can_change`, `can_edit`, …).
 */
import React, { useCallback, useEffect, useState } from "react";
import {
  getWorkflowResolutionPanel,
  listAvailableResolutionActions,
  setWorkflowResolutionActions,
  type ResolutionActionRow,
  type WorkflowDefinition,
  type WorkflowResolutionPanel,
} from "@/lib/api";
import { friendlyError } from "@/components/settings/lib/friendlyError";
import { resolutionPanelState } from "@/lib/resolution";
import { ResolutionActionDialog } from "@/components/settings/resolution/ResolutionActionDialog";

const SEARCH_DEBOUNCE_MS = 250;

export function ResolutionPanel({
  workflow,
  onBlocksPublishChange,
}: {
  workflow: WorkflowDefinition;
  /** Tells the editor whether Publish must wait for an action. */
  onBlocksPublishChange?: (blocks: boolean) => void;
}) {
  const [panel, setPanel] = useState<WorkflowResolutionPanel | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ResolutionActionRow[]>([]);
  const [dialog, setDialog] = useState<{ editing?: ResolutionActionRow; label?: string } | null>(null);

  const load = useCallback(async () => {
    try {
      setPanel(await getWorkflowResolutionPanel(workflow.workflow_id));
      setError("");
    } catch (e: unknown) {
      setError(friendlyError(e));
    }
  }, [workflow.workflow_id]);

  useEffect(() => {
    let alive = true;
    getWorkflowResolutionPanel(workflow.workflow_id)
      .then((p) => alive && setPanel(p))
      .catch((e: unknown) => alive && setError(friendlyError(e)));
    return () => { alive = false; };
  }, [workflow.workflow_id]);

  const state = panel ? resolutionPanelState(panel, workflow.status === "published") : null;

  useEffect(() => {
    if (state) onBlocksPublishChange?.(state.blocksPublish);
  }, [state?.blocksPublish, onBlocksPublishChange]); // eslint-disable-line react-hooks/exhaustive-deps

  // The picker: actions this workflow can use and does not offer, narrowed as the admin types.
  useEffect(() => {
    if (!adding) return;
    let alive = true;
    const timer = setTimeout(() => {
      listAvailableResolutionActions(workflow.workflow_id, query)
        .then((rows) => alive && setResults(rows))
        .catch(() => alive && setResults([]));
    }, SEARCH_DEBOUNCE_MS);
    return () => { alive = false; clearTimeout(timer); };
  }, [adding, query, workflow.workflow_id, panel]);

  async function save(codes: string[]) {
    setBusy(true);
    setError("");
    try {
      setPanel(await setWorkflowResolutionActions(workflow.workflow_id, codes));
    } catch (e: unknown) {
      // The list goes back to how it was, with the reason in one line (frame 5).
      setError(friendlyError(e));
      await load();
    } finally {
      setBusy(false);
    }
  }

  if (!panel || !state) {
    return (
      <section className="mt-8" aria-labelledby="resolution-panel-title">
        <h3 id="resolution-panel-title" className="text-sm font-semibold text-gray-700">What officers can choose when closing a case</h3>
        {error ? <p className="text-xs text-red-600 mt-2">{error}</p> : <p className="text-xs text-gray-400 mt-2">Loading…</p>}
      </section>
    );
  }

  if (panel.is_sensitive) {
    return (
      <section className="mt-8" aria-labelledby="resolution-panel-title">
        <h3 id="resolution-panel-title" className="text-sm font-semibold text-gray-700">What officers can choose when closing a case</h3>
        <p className="text-sm text-gray-500 mt-2">
          SEAH workflows do not record a resolution action. Officers describe the outcome in writing only.
        </p>
      </section>
    );
  }

  const codes = panel.actions.map((a) => a.code);
  const move = (i: number, by: number) => {
    const next = [...codes];
    [next[i], next[i + by]] = [next[i + by], next[i]];
    void save(next);
  };
  const typed = query.trim();
  const exact = results.some((r) => r.label.toLowerCase() === typed.toLowerCase())
    || panel.actions.some((a) => a.label.toLowerCase() === typed.toLowerCase());

  return (
    <section className="mt-8" aria-labelledby="resolution-panel-title">
      <div className="flex items-baseline justify-between mb-2">
        <h3 id="resolution-panel-title" className="text-sm font-semibold text-gray-700">
          What officers can choose when closing a case
        </h3>
        <span className="text-xs text-gray-500">{state.countLabel}</span>
      </div>

      <ul className="border border-gray-200 rounded-lg divide-y divide-gray-100">
        {panel.actions.map((a, i) => (
          <li key={a.code} className="flex items-center gap-2 px-3 py-2">
            {panel.can_change && (
              <span className="flex flex-col shrink-0">
                <button type="button" aria-label={`Move ${a.label} up`} disabled={busy || i === 0} onClick={() => move(i, -1)}
                  className="text-gray-400 hover:text-gray-700 disabled:opacity-20 text-xs leading-none">▲</button>
                <button type="button" aria-label={`Move ${a.label} down`} disabled={busy || i === codes.length - 1} onClick={() => move(i, 1)}
                  className="text-gray-400 hover:text-gray-700 disabled:opacity-20 text-xs leading-none">▼</button>
              </span>
            )}
            <span className="flex-1 min-w-0">
              <span className="text-sm text-gray-800">{a.label}</span>
              {a.counts_as_label && <span className="block text-xs text-gray-400">counts as {a.counts_as_label}</span>}
            </span>
            {a.can_edit && (
              <button type="button" onClick={() => setDialog({ editing: a })} disabled={busy}
                className="text-xs text-blue-600 hover:underline px-1">Edit</button>
            )}
            {panel.can_change && (
              <button type="button" onClick={() => save(codes.filter((c) => c !== a.code))}
                disabled={busy || !state.canRemove}
                title={state.canRemove ? undefined : "A published workflow needs at least one action"}
                className="text-xs text-gray-500 hover:text-red-600 px-1 disabled:opacity-40">Remove</button>
            )}
          </li>
        ))}
        {panel.actions.length === 0 && <li className="px-3 py-3 text-sm text-gray-400">No actions yet.</li>}
      </ul>

      {panel.can_change && !adding && (
        <button type="button" onClick={() => { setAdding(true); setQuery(""); }} disabled={busy || state.full}
          className="mt-2 text-sm text-blue-600 hover:underline disabled:opacity-40 disabled:no-underline">
          + Add an action
        </button>
      )}
      {adding && (
        <div className="mt-2 border border-dashed border-gray-300 rounded-lg p-3 space-y-1">
          <input autoFocus type="search" value={query} onChange={(e) => setQuery(e.target.value)}
            placeholder="Search actions, or type a new one…" aria-label="Add an action"
            className="w-full text-sm border border-gray-300 rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-400" />
          <ul>
            {results.map((r) => (
              <li key={r.code}>
                <button type="button" disabled={busy} onClick={() => { setAdding(false); void save([...codes, r.code]); }}
                  className="w-full text-left text-sm text-gray-800 hover:bg-gray-50 px-2 py-1 rounded">
                  {r.label}
                </button>
              </li>
            ))}
            {typed && !exact && (
              <li>
                <button type="button" onClick={() => { setAdding(false); setDialog({ label: typed }); }}
                  className="w-full text-left text-sm text-blue-700 hover:bg-blue-50 px-2 py-1 rounded">
                  + Create &ldquo;{typed}&rdquo;
                </button>
              </li>
            )}
          </ul>
          <button type="button" onClick={() => setAdding(false)} className="text-xs text-gray-500 hover:text-gray-700">Cancel</button>
        </div>
      )}

      {state.hint && <p className="text-xs text-gray-500 mt-2">{state.hint}</p>}
      {error && <p role="alert" className="text-xs text-red-600 mt-2">{error}</p>}
      <p className="text-xs text-gray-400 mt-2">Changes save at once and apply to the next case closed.</p>

      {dialog && (
        <ResolutionActionDialog
          workflowId={workflow.workflow_id}
          panel={panel}
          editing={dialog.editing}
          initialLabel={dialog.label}
          onClose={() => setDialog(null)}
          onSaved={() => { setDialog(null); void load(); }}
        />
      )}
    </section>
  );
}
