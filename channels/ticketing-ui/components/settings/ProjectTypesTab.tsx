// SPDX-License-Identifier: Apache-2.0

"use client";

/**
 * <ProjectTypesTab> — authoring project types (doc 14 §4, DECISION-author-defined-slots §3.1).
 *
 * A project type is the template a project is built from: the workflows it runs and the
 * organizations it must name. Creating a project is pick the organization → pick one of its
 * types → name the rest. Everything here is what "the rest" is measured against.
 *
 * No organization is special. Each one named on a project sees that project's grievances in its
 * reports (DECISION-organization-membership, 2026-08-04) — which is why the old "a grievance is
 * recorded against" picker is gone.
 *
 * Two rules shape this screen:
 *   • **A type with a live project is frozen** (§8). Not a disabled form — a read-only summary
 *     plus "Use as template", which copies it so the copy can be edited freely. Name and
 *     description stay editable either way: a name is not configuration.
 *   • **The workflow cards are the project screen's cards** (<WorkflowBindingCards>), because a
 *     type is mostly a bundle of workflows and the two must not drift apart.
 *
 * Copy: docs/ticketing_system/ui/05_ui_copy_style.md — plain words, no keys or slugs on screen.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createProjectType,
  duplicateProjectType,
  listOrganizations,
  listProjectTypes,
  listTemplates,
  listWorkflowRoutingOptions,
  listWorkflows,
  updateProjectType,
  type OrganizationItem,
  type ProjectTypeItem,
  type TypeActorRoleDef,
  type TypeWorkflowBinding,
  type WorkflowDefinition,
  type WorkflowRoutingOptions,
} from "@/lib/api";
import { useAuth } from "@/app/providers/AuthProvider";
import { friendlyError } from "@/components/settings/lib/friendlyError";
import { WorkflowBindingCards } from "@/components/settings/workflows/WorkflowBindingCards";
import {
  emptyBinding,
  type WorkflowBindingDraft,
} from "@/components/settings/workflows/workflowHelpers";

const OWNER_CATEGORIES = new Set(["government", "local_government", "donor"]);

/** Organizations that may own a template: the top two levels of the tree — a ministry and its
 *  departments (Department of Roads, Department of Irrigation …), or a donor. A contractor is
 *  named *by* a project; it does not hand out templates, and there are dozens of them.
 *  Mirrors `project_types.OWNER_CATEGORIES` / `OWNER_MAX_DEPTH` on the server. */
function templateOwnerChoices(orgs: OrganizationItem[]): OrganizationItem[] {
  const byId = new Map(orgs.map((o) => [o.organization_id, o]));
  const depth = (o: OrganizationItem): number => {
    if (!o.parent_organization_id) return 1;
    const parent = byId.get(o.parent_organization_id);
    return parent ? depth(parent) + 1 : 2; // parent outside the list ⇒ treat as a child of a root
  };
  return orgs.filter(
    (o) =>
      o.is_active
      && OWNER_CATEGORIES.has((o.org_category ?? "").toLowerCase())
      && depth(o) <= 2,
  );
}

/** A key is never typed or shown — it is derived once from the name and then never changes,
 *  because filled organizations point at it. */
function keyFromLabel(label: string, taken: Set<string>): string {
  const base = (label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "role")
    .replace(/^([^a-z])/, "role_$1")
    .slice(0, 60);
  let key = base;
  let n = 2;
  while (taken.has(key)) key = `${base}_${n++}`;
  return key;
}

function bindingsToDrafts(bindings: TypeWorkflowBinding[]): WorkflowBindingDraft[] {
  if (!bindings.length) return [emptyBinding(10, true)];
  return bindings.map((b, i) => ({
    localId: `b-${i}-${b.workflow_id || "empty"}`,
    display_label: b.display_label,
    workflow_id: b.workflow_id,
    classifications: b.classifications ?? [],
    intake_route: b.intake_route ?? null,
    is_default: b.is_default,
    sort_order: b.sort_order || (i + 1) * 10,
  }));
}

export function ProjectTypesTab() {
  const { isSuperAdmin, canConfigureSensitive, adminWorkflowTracks } = useAuth();
  const [types, setTypes] = useState<ProjectTypeItem[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([]);
  const [wfTemplates, setWfTemplates] = useState<WorkflowDefinition[]>([]);
  const [routingOptions, setRoutingOptions] = useState<WorkflowRoutingOptions | null>(null);
  const [orgs, setOrgs] = useState<OrganizationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [msgTone, setMsgTone] = useState<"ok" | "error">("ok");
  const [openKey, setOpenKey] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [t, w] = await Promise.all([
        listProjectTypes(false),
        listWorkflows().then((r) => r.items),
      ]);
      setTypes(t);
      setWorkflows(w);
    } catch (e: unknown) {
      setError(friendlyError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    listTemplates().then((r) => setWfTemplates(r.items)).catch(() => {});
    listWorkflowRoutingOptions().then(setRoutingOptions).catch(() => {});
    listOrganizations().then(setOrgs).catch(() => {});
  }, []);

  /** A confirmation. Green, and it clears itself. */
  function flash(t: string) {
    setMsgTone("ok");
    setMsg(t);
    setTimeout(() => setMsg(""), 3000);
  }

  /** A refusal. Red, and it stays until the next action — a rule the user has to read and act
   *  on is not a toast. Both used to go through `flash()` into one green line, so a 422 saying
   *  "name at least one organization" arrived looking like success (2026-08-08, Philippe:
   *  "can you explain this bug? I was not able to create a new type"). */
  function fail(t: string) {
    setMsgTone("error");
    setMsg(t);
  }

  const orgName = useCallback(
    (id: string | null) => orgs.find((o) => o.organization_id === id)?.name ?? id ?? "",
    [orgs],
  );

  function canEditWorkflowTrack(track: "standard" | "seah") {
    if (isSuperAdmin) return true;
    return adminWorkflowTracks.includes(track);
  }

  function replaceType(updated: ProjectTypeItem) {
    setTypes((prev) => {
      const has = prev.some((x) => x.type_key === updated.type_key);
      return has ? prev.map((x) => (x.type_key === updated.type_key ? updated : x)) : [...prev, updated];
    });
  }

  async function handleCreate() {
    const label = newName.trim();
    if (!label) return;
    // With one organization that can own templates, there is no choice to make — pre-fill it.
    // Only on CREATE: silently re-homing a type someone already shared would be a config change
    // nobody asked for.
    const owners = templateOwnerChoices(orgs);
    try {
      const created = await createProjectType({
        type_key: keyFromLabel(label, new Set(types.map((t) => t.type_key))),
        label,
        actor_roles: [],
        workflow_bindings: [],
        owner_organization_id: owners.length === 1 ? owners[0].organization_id : null,
        is_active: false,
      });
      replaceType(created);
      setCreating(false);
      setNewName("");
      setOpenKey(created.type_key);
      flash("Project type created. Set it up, then turn it on.");
    } catch (e: unknown) {
      fail(friendlyError(e));
    }
  }

  if (loading) return <p className="text-sm text-gray-400 animate-pulse">Loading project types…</p>;
  if (error) return <p className="text-sm text-red-500">{error}</p>;

  return (
    <div className="max-w-3xl">
      <p className="text-sm text-gray-600 mb-1">
        A project type is a template. It sets the workflows a project runs and the organizations it
        must name — so every project of the same kind is set up the same way.
      </p>
      <p className="text-xs text-gray-400 mb-4">
        Once a project is live on a type, its setup can no longer change. Copy the type to make
        changes.
      </p>
      {msg && (
        <p
          role={msgTone === "error" ? "alert" : undefined}
          className={`text-xs font-medium mb-3 ${
            msgTone === "error"
              ? "rounded border border-red-200 bg-red-50 px-3 py-2 text-red-700"
              : "text-green-700"
          }`}
        >
          {msg}
        </p>
      )}

      <div className="border border-gray-200 rounded-lg overflow-hidden divide-y divide-gray-100 mb-4">
        {types.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-8">
            No project types yet. Create one to start a project from it.
          </p>
        ) : (
          types.map((t) => (
            <div key={t.type_key} className="px-5 py-4">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-gray-800">{t.label}</span>
                    {t.active_project_count > 0 && (
                      <span className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-full px-2 py-0.5">
                        In use — {t.active_project_count} live{" "}
                        {t.active_project_count === 1 ? "project" : "projects"}
                      </span>
                    )}
                    {!t.is_active && (
                      <span className="text-xs text-gray-500 border border-gray-200 rounded-full px-2 py-0.5">
                        Not offered
                      </span>
                    )}
                  </div>
                  {t.description && <p className="text-xs text-gray-500 mt-1">{t.description}</p>}
                  <p className="text-xs text-gray-400 mt-2">
                    {t.owner_organization_id
                      ? `For ${orgName(t.owner_organization_id)}`
                      : "For every organization"}
                    {" · "}
                    {t.workflow_bindings.length}{" "}
                    {t.workflow_bindings.length === 1 ? "workflow" : "workflows"}
                    {" · "}
                    {t.actor_roles.length}{" "}
                    {t.actor_roles.length === 1 ? "organization" : "organizations"}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setOpenKey(openKey === t.type_key ? null : t.type_key)}
                  className="text-sm text-blue-600 hover:underline shrink-0"
                >
                  {openKey === t.type_key ? "Close" : t.active_project_count > 0 ? "View" : "Edit"}
                </button>
              </div>

              {openKey === t.type_key && (
                <ProjectTypeEditor
                  type={t}
                  orgs={orgs}
                  isSuperAdmin={isSuperAdmin}
                  workflows={workflows}
                  wfTemplates={wfTemplates}
                  routingOptions={routingOptions}
                  canEditWorkflowTrack={canEditWorkflowTrack}
                  canSeeSeah={!!canConfigureSensitive}
                  takenKeys={types.map((x) => x.type_key)}
                  onSaved={(updated) => {
                    replaceType(updated);
                    flash("Saved ✓");
                  }}
                  onCopied={(copy) => {
                    replaceType(copy);
                    setOpenKey(copy.type_key);
                    flash("Copy created. Edit it, then turn it on.");
                  }}
                  onError={fail}
                />
              )}
            </div>
          ))
        )}
      </div>

      {creating ? (
        <div className="rounded-lg border border-gray-200 p-4 space-y-3">
          <label className="text-xs font-medium text-gray-600 block" htmlFor="new-type-name">
            What kind of project is this?
          </label>
          <input
            id="new-type-name"
            autoFocus
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void handleCreate()}
            placeholder="e.g. Donor-funded road"
            className="w-full max-w-sm text-sm border border-gray-300 rounded px-3 py-1.5"
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => void handleCreate()}
              disabled={!newName.trim()}
              className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded hover:bg-blue-700 disabled:opacity-50"
            >
              Create
            </button>
            <button
              type="button"
              onClick={() => { setCreating(false); setNewName(""); }}
              className="text-sm text-gray-500 px-3 py-1.5"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setCreating(true)}
          className="text-sm font-semibold text-blue-600 border border-dashed border-blue-200 bg-blue-50 rounded px-3 py-1.5 hover:bg-blue-100"
        >
          + New project type
        </button>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

function ProjectTypeEditor({
  type: initial,
  orgs,
  isSuperAdmin,
  workflows,
  wfTemplates,
  routingOptions,
  canEditWorkflowTrack,
  canSeeSeah,
  takenKeys,
  onSaved,
  onCopied,
  onError,
}: {
  type: ProjectTypeItem;
  orgs: OrganizationItem[];
  isSuperAdmin: boolean;
  workflows: WorkflowDefinition[];
  wfTemplates: WorkflowDefinition[];
  routingOptions: WorkflowRoutingOptions | null;
  canEditWorkflowTrack: (track: "standard" | "seah") => boolean;
  canSeeSeah: boolean;
  takenKeys: string[];
  onSaved: (t: ProjectTypeItem) => void;
  onCopied: (t: ProjectTypeItem) => void;
  onError: (msg: string) => void;
}) {
  const frozen = initial.active_project_count > 0;

  const [label, setLabel] = useState(initial.label);
  const [description, setDescription] = useState(initial.description ?? "");
  const [roles, setRoles] = useState<TypeActorRoleDef[]>(() => initial.actor_roles.map((r) => ({ ...r })));
  const [rows, setRows] = useState<WorkflowBindingDraft[]>(() => bindingsToDrafts(initial.workflow_bindings));
  const [owner, setOwner] = useState<string | null>(initial.owner_organization_id);
  const [offered, setOffered] = useState(initial.is_active);
  const [saving, setSaving] = useState(false);
  const [copying, setCopying] = useState(false);
  const [copyName, setCopyName] = useState(`${initial.label} (copy)`);

  useEffect(() => {
    setLabel(initial.label);
    setDescription(initial.description ?? "");
    setRoles(initial.actor_roles.map((r) => ({ ...r })));
    setRows(bindingsToDrafts(initial.workflow_bindings));
    setOwner(initial.owner_organization_id);
    setOffered(initial.is_active);
  }, [initial]);

  const workflowName = useCallback(
    (id: string) => workflows.find((w) => w.workflow_id === id)?.display_name ?? "Not chosen",
    [workflows],
  );
  const orgName = (id: string | null) => orgs.find((o) => o.organization_id === id)?.name ?? id ?? "";

  const ownerChoices = useMemo(() => templateOwnerChoices(orgs), [orgs]);

  /** Keys for rows that don't have one yet, derived from the name once and then fixed —
   *  `project_organizations.org_role` points at them, so renaming a row never orphans a
   *  filled organization. */
  const rolesWithKeys = useMemo(() => {
    const taken = new Set(roles.map((r) => r.key).filter(Boolean));
    return roles.map((r) => {
      if (r.key) return r;
      const key = keyFromLabel(r.label || "", taken);
      taken.add(key);
      return { ...r, key };
    });
  }, [roles]);

  function patchRole(i: number, patch: Partial<TypeActorRoleDef>) {
    setRoles((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }

  function addRole() {
    setRoles((prev) => [
      ...prev,
      { key: "", label: "", description: "", required: false, required_package: false, scope: "project" },
    ]);
  }

  function removeRole(i: number) {
    setRoles((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function save() {
    const cleaned = rolesWithKeys
      .filter((r) => (r.label ?? "").trim())
      .map((r) => ({
        key: r.key,
        label: r.label.trim(),
        description: (r.description ?? "").trim(),
        required: !!r.required,
        required_package: !!r.required_package,
        scope: r.scope || "project",
      }));
    const bindings = rows
      .filter((r) => r.display_label.trim() && r.workflow_id)
      .map((r, i) => ({
        display_label: r.display_label.trim(),
        workflow_id: r.workflow_id,
        classifications: r.classifications,
        intake_route: r.is_default ? null : r.intake_route,
        is_default: r.is_default,
        sort_order: r.sort_order || (i + 1) * 10,
      }));
    if (bindings.length && bindings.filter((b) => b.is_default).length !== 1) {
      onError("One workflow must be the default.");
      return;
    }
    setSaving(true);
    try {
      const updated = await updateProjectType(initial.type_key, {
        label: label.trim() || initial.label,
        description: description.trim() || null,
        actor_roles: cleaned,
        workflow_bindings: bindings,
        owner_organization_id: isSuperAdmin ? owner : undefined,
        is_active: offered,
      });
      onSaved(updated);
    } catch (e: unknown) {
      onError(friendlyError(e));
    } finally {
      setSaving(false);
    }
  }

  /** Frozen types keep their name editable — that is the whole point of the amendment (§8). */
  async function saveNameOnly() {
    setSaving(true);
    try {
      const updated = await updateProjectType(initial.type_key, {
        label: label.trim() || initial.label,
        description: description.trim() || null,
      });
      onSaved(updated);
    } catch (e: unknown) {
      onError(friendlyError(e));
    } finally {
      setSaving(false);
    }
  }

  async function copy() {
    const name = copyName.trim();
    if (!name) return;
    setSaving(true);
    try {
      const created = await duplicateProjectType(initial.type_key, {
        type_key: keyFromLabel(name, new Set(takenKeys)),
        label: name,
      });
      setCopying(false);
      onCopied(created);
    } catch (e: unknown) {
      onError(friendlyError(e));
    } finally {
      setSaving(false);
    }
  }

  const nameFields = (
    <div className="grid gap-3 sm:grid-cols-2">
      <div>
        <label className="text-xs font-medium text-gray-600 block mb-1" htmlFor={`t-label-${initial.type_key}`}>
          Name
        </label>
        <input
          id={`t-label-${initial.type_key}`}
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          className="w-full text-sm border border-gray-300 rounded px-3 py-1.5"
        />
      </div>
      <div>
        <label className="text-xs font-medium text-gray-600 block mb-1" htmlFor={`t-desc-${initial.type_key}`}>
          Description
        </label>
        <input
          id={`t-desc-${initial.type_key}`}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="What kind of project uses this"
          className="w-full text-sm border border-gray-300 rounded px-3 py-1.5"
        />
      </div>
    </div>
  );

  const copyBox = copying ? (
    <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 space-y-2">
      <label className="text-xs font-medium text-gray-700 block" htmlFor={`copy-${initial.type_key}`}>
        Name for the copy
      </label>
      <input
        id={`copy-${initial.type_key}`}
        autoFocus
        value={copyName}
        onChange={(e) => setCopyName(e.target.value)}
        className="w-full max-w-sm text-sm border border-gray-300 rounded px-3 py-1.5 bg-white"
      />
      <p className="text-xs text-gray-500">
        The copy starts turned off, so it is not offered for new projects until you finish it.
        Projects on this type are not touched.
      </p>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={saving || !copyName.trim()}
          onClick={() => void copy()}
          className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? "Copying…" : "Create the copy"}
        </button>
        <button type="button" onClick={() => setCopying(false)} className="text-sm text-gray-500 px-3 py-1.5">
          Cancel
        </button>
      </div>
    </div>
  ) : (
    <button
      type="button"
      onClick={() => setCopying(true)}
      className="text-sm font-semibold text-blue-600 border border-blue-200 bg-blue-50 rounded px-3 py-1.5 hover:bg-blue-100"
    >
      Use as template
    </button>
  );

  // ── Frozen: a summary of what projects run, plus the two ways out ───────────
  if (frozen) {
    return (
      <div className="mt-4 pt-4 border-t border-gray-100 space-y-4">
        <p className="text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded px-3 py-2">
          {initial.active_project_count} live{" "}
          {initial.active_project_count === 1 ? "project uses" : "projects use"} this type, so its
          setup cannot change — officers are working those grievances now. Copy it to make changes,
          or deactivate the project first, fix the type, then activate it again.
        </p>

        {nameFields}
        <button
          type="button"
          disabled={saving}
          onClick={() => void saveNameOnly()}
          className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save name"}
        </button>

        <div>
          <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-2">Workflows</div>
          {initial.workflow_bindings.length === 0 ? (
            <p className="text-xs text-gray-400 italic">None.</p>
          ) : (
            <ul className="space-y-1.5">
              {initial.workflow_bindings.map((b) => (
                <li key={`${b.display_label}-${b.workflow_id}`} className="text-sm text-gray-700">
                  <span className="font-medium">{b.display_label}</span>{" "}
                  <span className="text-gray-400">— {workflowName(b.workflow_id)}</span>
                  {b.is_default && <span className="text-xs text-gray-500"> · used when nothing else matches</span>}
                  {!!b.classifications?.length && (
                    <span className="text-xs text-gray-500"> · {b.classifications.join(", ")}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-2">
            Organizations a project must name
          </div>
          {initial.actor_roles.length === 0 ? (
            <p className="text-xs text-gray-400 italic">None.</p>
          ) : (
            <ul className="space-y-1.5">
              {initial.actor_roles.map((r) => (
                <li key={r.key} className="text-sm text-gray-700">
                  <span className="font-medium">{r.label}</span>
                  {r.required && <span className="text-xs text-red-700"> · required</span>}
                  {r.required_package && <span className="text-xs text-gray-500"> · for each package</span>}
                  {r.description && <span className="block text-xs text-gray-500">{r.description}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>

        <p className="text-xs text-gray-500">
          {initial.owner_organization_id
            ? `Only ${orgName(initial.owner_organization_id)} can use this type.`
            : "Every organization can use this type."}
        </p>

        {copyBox}
      </div>
    );
  }

  // ── Editable ───────────────────────────────────────────────────────────────
  return (
    <div className="mt-4 pt-4 border-t border-gray-100 space-y-6">
      {nameFields}

      <div>
        <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1">
          Organizations a project must name
        </div>
        <p className="text-xs text-gray-500 mb-2">
          Use the words on your contract — the project screen shows exactly these.
        </p>
        {roles.length === 0 ? (
          <p className="text-xs text-gray-400 italic">
            None yet. Add the organizations every project of this kind has.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] font-bold uppercase tracking-wider text-gray-400 text-left">
                  <th className="pb-1 pr-3 font-bold">Name</th>
                  <th className="pb-1 pr-3 font-bold">What it does on the project</th>
                  <th className="pb-1 px-2 font-bold text-center whitespace-nowrap">Must be named</th>
                  <th className="pb-1 px-2 font-bold text-center whitespace-nowrap">For each package</th>
                  <th className="pb-1" />
                </tr>
              </thead>
              <tbody>
                {roles.map((r, i) => (
                  <tr key={r.key || `new-${i}`} className="align-middle">
                    <td className="py-1 pr-3">
                      <input
                        value={r.label}
                        onChange={(e) => patchRole(i, { label: e.target.value })}
                        placeholder="e.g. Executing Agency"
                        aria-label="Organization name"
                        className="w-full min-w-[150px] text-sm font-medium border border-gray-300 rounded px-2 py-1.5"
                      />
                    </td>
                    <td className="py-1 pr-3">
                      <input
                        value={r.description ?? ""}
                        onChange={(e) => patchRole(i, { description: e.target.value })}
                        placeholder="Optional"
                        aria-label="What this organization does on the project"
                        className="w-full min-w-[180px] text-sm border border-gray-300 rounded px-2 py-1.5"
                      />
                    </td>
                    <td className="py-1 px-2 text-center">
                      <input
                        type="checkbox"
                        checked={!!r.required}
                        onChange={(e) => patchRole(i, { required: e.target.checked })}
                        aria-label={`${r.label || "This organization"} must be named before go-live`}
                      />
                    </td>
                    <td className="py-1 px-2 text-center">
                      <input
                        type="checkbox"
                        checked={!!r.required_package}
                        onChange={(e) => patchRole(i, { required_package: e.target.checked })}
                        aria-label={`${r.label || "This organization"} is named for each package`}
                      />
                    </td>
                    <td className="py-1 pl-2 text-right">
                      <button
                        type="button"
                        onClick={() => removeRole(i)}
                        className="text-xs font-semibold text-red-600 hover:underline"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <button
          type="button"
          onClick={addRole}
          className="mt-2 text-sm font-semibold text-blue-600 border border-dashed border-blue-200 bg-blue-50 rounded px-3 py-1.5 hover:bg-blue-100"
        >
          + Add an organization
        </button>
        <p className="text-xs text-gray-500 mt-2">
          Every organization named on a project sees that project&apos;s grievances in its
          reports. One named for a single package sees that package only.{" "}
          <span className="text-gray-400">
            &ldquo;Must be named&rdquo; blocks go-live until the project names it.
          </span>
        </p>
      </div>

      <div>
        <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-2">Workflows</div>
        <WorkflowBindingCards
          rows={rows}
          onChange={setRows}
          workflows={workflows}
          wfTemplates={wfTemplates}
          routingOptions={routingOptions}
          readOnly={false}
          busy={saving}
          canEditWorkflowTrack={canEditWorkflowTrack}
          canSeeSeah={canSeeSeah}
        />
      </div>

      {isSuperAdmin && (
        <div>
          <label className="text-[10px] font-bold uppercase tracking-wider text-gray-400 block mb-1" htmlFor={`owner-${initial.type_key}`}>
            Who can use this type
          </label>
          <select
            id={`owner-${initial.type_key}`}
            value={owner ?? ""}
            onChange={(e) => setOwner(e.target.value || null)}
            className="w-full max-w-sm text-sm border border-gray-300 rounded px-2 py-1.5"
          >
            <option value="">Every organization</option>
            {ownerChoices.map((o) => (
              <option key={o.organization_id} value={o.organization_id}>{o.name}</option>
            ))}
          </select>
          <p className="text-xs text-gray-500 mt-1">
            The organization it is offered to, and the offices under it. Leave it shared with
            every organization if it is not specific to one.
          </p>
        </div>
      )}

      <div>
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={offered}
            disabled={roles.length === 0}
            onChange={(e) => setOffered(e.target.checked)}
          />
          Can be chosen when creating a project
        </label>
        <p className="text-xs text-gray-500 mt-1 ml-6">
          Turn this off and no new project can use this type. Projects already using it keep
          working.
        </p>
      </div>

      {/* An empty type saves fine — it is authored empty and filled in. What it cannot do is
          be turned ON empty (2026-08-08): a project built from it would open its Organizations
          section to a dead end, and nobody would see its grievances, since an organization sees
          a project's grievances only by being named on it. The API refuses that too (422). */}
      {roles.length === 0 && (
        <p className="max-w-xl rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          Name at least one organization before turning this type on. Projects built from it can
          only name the organizations listed here, and an organization must be named to see the
          project&apos;s grievances.
        </p>
      )}

      <div className="flex items-center gap-3">
        <button
          type="button"
          disabled={saving}
          onClick={() => void save()}
          className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save project type"}
        </button>
        {copyBox}
      </div>
    </div>
  );
}
