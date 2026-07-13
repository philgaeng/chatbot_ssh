"use client";

/**
 * <ReviewHoldersModal> — the roster of officers holding a position type (DESIGN §D3,
 * Frame 06). Editing a position's default role never silently re-syncs the officers who
 * already hold it (doc 16 §4); this modal makes that drift *visible* — one row per holder
 * with their organisation and whether the position is still active.
 *
 * Note: the batch "re-sync selected" writer is a documented backend GAP (frame-06 §4 /
 * §7.1 — no HTTP surface yet). Until it lands this surface is review-only; it does not
 * fabricate a re-sync path.
 */

import { useEffect, useState } from "react";

import {
  listPositionTypeHolders,
  type PositionTypeItem,
  type PositionHolder,
} from "@/lib/api";
import { text as textTokens } from "@/lib/design-tokens";
import { RoleLabel } from "@/components/shared/RoleLabel";
import { ErrorCard } from "@/components/ui/ErrorCard";

export function ReviewHoldersModal({
  positionType,
  orgNames,
  newDefaultRoleKey,
  onClose,
}: {
  positionType: PositionTypeItem;
  /** organization_id → display name (from the org list). */
  orgNames: Map<string, string>;
  /** The role the position now defaults to (shown for context after an edit). */
  newDefaultRoleKey?: string;
  onClose: () => void;
}) {
  const [holders, setHolders] = useState<PositionHolder[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const load = () => {
    setLoading(true);
    setFailed(false);
    listPositionTypeHolders(positionType.position_type_id, false)
      .then(setHolders)
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  };

  useEffect(load, [positionType.position_type_id]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="max-h-[85vh] w-full max-w-xl overflow-hidden rounded-xl bg-white shadow-xl">
        <div className="flex items-center justify-between bg-slate-700 px-6 py-4 text-white">
          <div className="font-semibold">Officers holding this position</div>
          <button
            type="button"
            onClick={onClose}
            className="text-xl leading-none text-slate-300 hover:text-white"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="max-h-[calc(85vh-8rem)] space-y-3 overflow-y-auto p-6">
          <p className={`text-sm ${textTokens.body}`}>
            These officers hold{" "}
            <span className="font-medium">{positionType.display_name}</span>. Their role was not
            changed automatically.
            {newDefaultRoleKey && (
              <>
                {" "}
                The position now defaults to <RoleLabel roleKey={newDefaultRoleKey} />.
              </>
            )}
          </p>

          {loading ? (
            <div className="space-y-2" aria-busy>
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-8 animate-pulse rounded bg-gray-100" />
              ))}
            </div>
          ) : failed ? (
            <ErrorCard message="Couldn't load the holders." onRetry={load} />
          ) : holders && holders.length === 0 ? (
            <p className={`text-sm ${textTokens.secondary}`}>No officers hold this position yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className={`border-b border-gray-200 text-left text-xs ${textTokens.secondary}`}>
                    <th className="py-2 pr-3 font-medium">Officer</th>
                    <th className="py-2 pr-3 font-medium">Organisation</th>
                    <th className="py-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {holders?.map((h) => (
                    <tr key={h.officer_position_id} className="border-b border-gray-100">
                      <td className={`py-2 pr-3 ${textTokens.body}`}>{h.user_id}</td>
                      <td className={`py-2 pr-3 ${textTokens.body}`}>
                        {orgNames.get(h.organization_id) ?? h.organization_id}
                      </td>
                      <td className="py-2">
                        {h.is_active ? (
                          <span className="rounded border border-green-200 bg-green-50 px-1.5 py-0.5 text-xs font-medium text-green-700">
                            Active
                          </span>
                        ) : (
                          <span className="rounded border border-gray-200 bg-gray-100 px-1.5 py-0.5 text-xs font-medium text-gray-600">
                            Ended
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <p className={`text-xs ${textTokens.muted}`}>
            Re-syncing these officers to the new default role is coming soon.
          </p>
        </div>

        <div className="flex justify-end border-t border-gray-100 px-6 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded bg-blue-600 px-4 py-1.5 text-sm font-medium text-white transition hover:bg-blue-700"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

export default ReviewHoldersModal;
