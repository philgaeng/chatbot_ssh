"use client";

/**
 * <OrgEditor> — create/edit an org unit (DESIGN §4.2, Frame 02/12).
 *
 * Fields: name (EN), Nepali name, org_category (root only — children inherit),
 * unit_type, parent (picker, cycle-guarded), territory (location code + includes
 * children), email, address. On create it runs the SH-4 dedup soft-flag
 * (`findDuplicateOrganizations`) — a non-blocking warning, never a hard stop.
 *
 * Root-creation gating (§2.5): a new institutional root (government / local
 * government / donor) is super_admin only → gated by `canCreateRoot`; a third_party
 * (company/contractor) root is delegable → `canEdit`. Server is the source of truth;
 * this is defense-in-depth, and any 403/422 surfaces via <ErrorNotice>.
 */

import { useEffect, useMemo, useState } from "react";

import {
  createOrganization,
  updateOrganization,
  findDuplicateOrganizations,
  type OrganizationItem,
  type OrganizationCreate,
  type OrganizationUpdate,
  type DuplicateCandidateItem,
} from "@/lib/api";
import { text as textTokens } from "@/lib/design-tokens";
import { Bilingual } from "@/components/shared/Bilingual";
import { ErrorNotice } from "@/components/shared/ErrorNotice";
import { ProvenanceHint } from "@/components/shared/ProvenanceHint";

import {
  ORG_CATEGORIES,
  UNIT_TYPES,
  orgCategoryLabel,
  unitTypeLabel,
  isInstitutionalCategory,
  descendantIds,
  buildForest,
  findNode,
} from "./orgVocab";

type Mode = "create" | "edit";

export function OrgEditor({
  mode,
  org,
  presetParentId = null,
  allOrgs,
  canEdit,
  canCreateRoot,
  onSaved,
  onCancel,
}: {
  mode: Mode;
  /** The org being edited (mode="edit"). */
  org?: OrganizationItem;
  /** Preset parent for "add child" (mode="create"). */
  presetParentId?: string | null;
  /** Full org list — powers the parent picker + cycle guard. */
  allOrgs: OrganizationItem[];
  canEdit: boolean;
  /** May create a new institutional (government/local-gov/donor) root. */
  canCreateRoot: boolean;
  onSaved: (org: OrganizationItem) => void;
  onCancel: () => void;
}) {
  const initialParent = mode === "edit" ? (org?.parent_organization_id ?? "") : (presetParentId ?? "");

  const [name, setName] = useState(org?.name ?? "");
  const [nameNe, setNameNe] = useState(org?.display_name_ne ?? "");
  const [parentId, setParentId] = useState<string>(initialParent ?? "");
  const [orgCategory, setOrgCategory] = useState<string>(org?.org_category ?? "government");
  const [unitType, setUnitType] = useState<string>(org?.unit_type ?? "");
  const [territoryCode, setTerritoryCode] = useState<string>(org?.territory_location_code ?? "");
  const [includesChildren, setIncludesChildren] = useState<boolean>(
    org?.territory_includes_children ?? false,
  );
  const [countryCode, setCountryCode] = useState<string>(org?.country_code ?? "NP");
  const [email, setEmail] = useState<string>(org?.email ?? "");
  const [address, setAddress] = useState<string>(org?.address ?? "");

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const [dupes, setDupes] = useState<DuplicateCandidateItem[]>([]);
  const [dupeChecking, setDupeChecking] = useState(false);
  const [dupesDismissed, setDupesDismissed] = useState(false);

  const isRoot = !parentId;

  // Parent options: exclude self + descendants (edit) so the UI never offers a cycle.
  const parentOptions = useMemo(() => {
    const forest = buildForest(allOrgs);
    let blocked = new Set<string>();
    if (mode === "edit" && org) {
      blocked.add(org.organization_id);
      const self = findNode(forest, org.organization_id);
      if (self) blocked = new Set([...blocked, ...descendantIds(self)]);
    }
    return allOrgs.filter((o) => !blocked.has(o.organization_id));
  }, [allOrgs, mode, org]);

  // Category inherited when a parent is set; show the parent's category read-only.
  const parentOrg = parentId ? allOrgs.find((o) => o.organization_id === parentId) : undefined;
  const inheritedCategory = parentOrg?.org_category;

  // Root-creation gating (defense-in-depth; server enforces).
  const rootCreationBlocked =
    isRoot &&
    ((isInstitutionalCategory(orgCategory) && !canCreateRoot) ||
      (!isInstitutionalCategory(orgCategory) && !canEdit));

  async function runDupeCheck() {
    if (mode !== "create" || name.trim().length < 3) return;
    setDupeChecking(true);
    setDupesDismissed(false);
    try {
      const candidates = await findDuplicateOrganizations({
        name: name.trim(),
        email: email.trim() || null,
        address: address.trim() || null,
        country_code: countryCode || null,
      });
      setDupes(candidates);
    } catch {
      // Dedup is a guardrail, never a gate — a failed check must not block create.
      setDupes([]);
    } finally {
      setDupeChecking(false);
    }
  }

  // Re-run the soft-flag check shortly after the name settles (create only).
  useEffect(() => {
    if (mode !== "create") return;
    const handle = setTimeout(() => void runDupeCheck(), 500);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name, email, address, countryCode]);

  async function handleSave() {
    if (!name.trim()) {
      setError("Please enter a name.");
      return;
    }
    if (rootCreationBlocked) {
      setError(
        isInstitutionalCategory(orgCategory)
          ? "Only a system administrator can create a new government, local-government, or development-partner root."
          : "You do not have permission to create a new top-level organisation.",
      );
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (mode === "create") {
        const payload: OrganizationCreate = {
          name: name.trim(),
          display_name_ne: nameNe.trim() || null,
          country_code: countryCode || null,
          parent_organization_id: parentId || null,
          unit_type: unitType || null,
          territory_location_code: territoryCode.trim() || null,
          territory_includes_children: includesChildren,
          email: email.trim() || null,
          address: address.trim() || null,
        };
        // Category is set on a root and inherited by children — only send it for a root.
        if (isRoot) payload.org_category = orgCategory;
        const created = await createOrganization(payload);
        onSaved(created);
      } else if (org) {
        const payload: OrganizationUpdate = {
          name: name.trim(),
          display_name_ne: nameNe.trim() || null,
          unit_type: unitType || null,
          territory_location_code: territoryCode.trim() || null,
          territory_includes_children: includesChildren,
          email: email.trim() || null,
          address: address.trim() || null,
        };
        // Reparent only when it actually changed (null detaches to root).
        const nextParent = parentId || null;
        if (nextParent !== (org.parent_organization_id ?? null)) {
          payload.parent_organization_id = nextParent;
        }
        // Category is editable only on a root; children inherit it.
        if (isRoot && orgCategory !== org.org_category) payload.org_category = orgCategory;
        const updated = await updateOrganization(org.organization_id, payload);
        onSaved(updated);
      }
    } catch (e) {
      setError(e);
      setSaving(false);
    }
  }

  const showDupes = mode === "create" && !dupesDismissed && dupes.length > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="max-h-[90vh] w-full max-w-lg overflow-hidden rounded-xl bg-white shadow-xl">
        <div className="flex items-center justify-between bg-slate-700 px-6 py-4 text-white">
          <div className="font-semibold">
            {mode === "create" ? "Add organisation" : "Edit organisation"}
          </div>
          <button
            type="button"
            onClick={onCancel}
            className="text-xl leading-none text-slate-300 hover:text-white"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="max-h-[calc(90vh-8rem)] space-y-4 overflow-y-auto p-6">
          <ErrorNotice error={error} />

          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">Name (English) *</label>
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Department of Roads"
              className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">Name (Nepali)</label>
            <input
              value={nameNe}
              onChange={(e) => setNameNe(e.target.value)}
              placeholder="सडक विभाग"
              className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
            {!nameNe.trim() && (
              <ProvenanceHint className="mt-1">
                No Nepali name yet — it can be added later, never invented.
              </ProvenanceHint>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500">Parent office</label>
              <select
                value={parentId}
                onChange={(e) => setParentId(e.target.value)}
                className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              >
                <option value="">— None (top-level / new root) —</option>
                {parentOptions.map((o) => (
                  <option key={o.organization_id} value={o.organization_id}>
                    {o.name}
                  </option>
                ))}
              </select>
              {mode === "edit" && (
                <ProvenanceHint className="mt-1">
                  Moving to a different parent may change this office&rsquo;s category to match.
                </ProvenanceHint>
              )}
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500">Office type</label>
              <select
                value={unitType}
                onChange={(e) => setUnitType(e.target.value)}
                className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              >
                <option value="">— Not set —</option>
                {UNIT_TYPES.map((ut) => (
                  <option key={ut} value={ut}>
                    {unitTypeLabel(ut)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {isRoot ? (
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500">Category</label>
              <select
                value={orgCategory}
                onChange={(e) => setOrgCategory(e.target.value)}
                className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              >
                {ORG_CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {orgCategoryLabel(c)}
                  </option>
                ))}
              </select>
              {rootCreationBlocked && (
                <ProvenanceHint className="mt-1">
                  {isInstitutionalCategory(orgCategory)
                    ? "Only a system administrator can create this kind of top-level organisation."
                    : "You do not have permission to create a new top-level organisation."}
                </ProvenanceHint>
              )}
            </div>
          ) : (
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500">Category</label>
              <div className={`text-sm ${textTokens.body}`}>
                {orgCategoryLabel(inheritedCategory) || "Inherited from the parent office"}
              </div>
              <ProvenanceHint className="mt-1">Inherited from the parent office.</ProvenanceHint>
            </div>
          )}

          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">
              Territory it covers (location code)
            </label>
            <input
              value={territoryCode}
              onChange={(e) => setTerritoryCode(e.target.value)}
              placeholder="e.g. NP-P1-JHA"
              className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
            <label className="mt-2 flex cursor-pointer items-center gap-2">
              <input
                type="checkbox"
                checked={includesChildren}
                onChange={(e) => setIncludesChildren(e.target.checked)}
                className="h-4 w-4 rounded"
              />
              <span className="text-sm text-gray-700">Also covers areas below it</span>
            </label>
            <ProvenanceHint className="mt-1">
              Territory is what makes this office routable when inviting officers.
            </ProvenanceHint>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500">Country code</label>
              <input
                value={countryCode}
                onChange={(e) => setCountryCode(e.target.value.toUpperCase())}
                placeholder="NP"
                maxLength={8}
                className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500">Contact email</label>
              <input
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="office@example.gov.np"
                className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-gray-500">Address</label>
            <input
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="Street, municipality, district"
              className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>

          {dupeChecking && (
            <p className={`text-xs ${textTokens.muted}`}>Checking for similar organisations…</p>
          )}

          {showDupes && (
            <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2">
              <p className="text-sm font-medium text-amber-800">
                This looks similar to {dupes.length === 1 ? "an existing organisation" : "existing organisations"}
              </p>
              <ul className="mt-1 space-y-1">
                {dupes.map((d) => (
                  <li key={d.organization_id} className="text-sm text-amber-800">
                    <span className="font-medium">
                      <Bilingual en={d.name} ne={null} showMissing={false} />
                    </span>
                    {d.reasons.length > 0 && (
                      <span className="text-amber-700"> — {d.reasons.join(", ")}</span>
                    )}
                  </li>
                ))}
              </ul>
              <p className="mt-1 text-xs text-amber-700">
                You can still create a new one — this is only a heads-up.
              </p>
              <button
                type="button"
                onClick={() => setDupesDismissed(true)}
                className="mt-1 text-xs font-medium text-amber-800 underline hover:no-underline"
              >
                Dismiss
              </button>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 border-t border-gray-100 px-6 py-4">
          <button
            type="button"
            onClick={onCancel}
            className="rounded px-4 py-1.5 text-sm text-gray-500 hover:text-gray-700"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving || !name.trim() || rootCreationBlocked}
            className="rounded bg-blue-600 px-4 py-1.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Saving…" : mode === "create" ? "Create organisation" : "Save changes"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default OrgEditor;
