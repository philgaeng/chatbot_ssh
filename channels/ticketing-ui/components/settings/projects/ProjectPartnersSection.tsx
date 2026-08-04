"use client";

/**
 * <ProjectPartnersSection> — Partner organizations (doc 13 §5B order 5, wireframe ui/04).
 *
 * The reconciled model (DECISION-project-participants-and-supervision, 2026-07-10):
 *   • ONE implementing agency — the signing ministry, the routing and reporting anchor.
 *     Government bodies only.
 *   • ZERO OR MORE donors — drives the guardrail that keeps a donor informed at the last level.
 *
 * Replaces the old "Project actors" table (organization × free `org_role` dropdown × Add
 * officer), which edited the deprecated per-project actor-role catalog. Officers are staffed
 * under Project-wide staffing, never here — that separation is the whole point of the 07-10
 * decision, and mixing them was why the old table needed an "Add officer" column.
 */
import { useEffect, useState } from "react";
import {
  addProjectDonor,
  listProjectDonors,
  removeProjectDonor,
  updateProject,
  type OrganizationItem,
  type ProjectDonorItem,
  type ProjectItem,
} from "@/lib/api";
import { friendlyError } from "@/components/settings/lib/friendlyError";

const GOVERNMENT_CATEGORIES = new Set(["government", "local_government"]);

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? "").join("");
}

export function ProjectPartnersSection({
  project,
  orgs,
  canEdit,
  onUpdated,
  flash,
}: {
  project: ProjectItem;
  orgs: OrganizationItem[];
  canEdit: boolean;
  onUpdated: (p: ProjectItem) => void;
  flash: (msg: string) => void;
}) {
  const [donors, setDonors] = useState<ProjectDonorItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [changingAgency, setChangingAgency] = useState(false);
  const [addingDonor, setAddingDonor] = useState(false);

  useEffect(() => {
    setLoading(true);
    listProjectDonors(project.project_id)
      .then(setDonors)
      .catch(() => setDonors([]))
      .finally(() => setLoading(false));
  }, [project.project_id]);

  const agencyId = project.implementing_agency_org_id ?? null;
  const agency = orgs.find((o) => o.organization_id === agencyId) ?? null;

  const governmentOrgs = orgs.filter(
    (o) => o.is_active && GOVERNMENT_CATEGORIES.has((o.org_category ?? "").toLowerCase()),
  );
  const donorIds = new Set(donors.map((d) => d.organization_id));
  const donorCandidates = orgs.filter(
    (o) => o.is_active && (o.org_category ?? "").toLowerCase() === "donor" && !donorIds.has(o.organization_id),
  );

  async function setAgency(orgId: string) {
    setWorking(true);
    try {
      const updated = await updateProject(project.project_id, { implementing_agency_org_id: orgId });
      onUpdated(updated);
      setChangingAgency(false);
      flash("Saved ✓");
    } catch (e: unknown) {
      flash(friendlyError(e));
    } finally {
      setWorking(false);
    }
  }

  async function addDonor(orgId: string) {
    setWorking(true);
    try {
      const item = await addProjectDonor(project.project_id, orgId);
      setDonors((prev) => [...prev, item]);
      setAddingDonor(false);
      flash("Donor added ✓");
    } catch (e: unknown) {
      flash(friendlyError(e));
    } finally {
      setWorking(false);
    }
  }

  async function dropDonor(orgId: string) {
    setWorking(true);
    try {
      await removeProjectDonor(project.project_id, orgId);
      setDonors((prev) => prev.filter((d) => d.organization_id !== orgId));
      flash("Donor removed");
    } catch (e: unknown) {
      flash(friendlyError(e));
    } finally {
      setWorking(false);
    }
  }

  return (
    <div className="space-y-6 max-w-xl">
      {/* ── Implementing agency ── */}
      <div>
        <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-2">
          Implementing agency
        </div>
        {agency ? (
          <div className="flex items-center gap-3 rounded-lg border border-gray-200 px-3 py-2.5">
            <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-blue-50 text-[11px] font-bold text-blue-700">
              {initials(agency.name)}
            </span>
            <span className="flex-1 min-w-0">
              <span className="block text-sm font-medium text-gray-900 truncate">{agency.name}</span>
              <span className="block text-xs text-gray-500">Accountable for this project</span>
            </span>
            {canEdit && !changingAgency && (
              <button
                type="button"
                onClick={() => setChangingAgency(true)}
                className="text-xs font-semibold text-blue-600 border border-blue-200 bg-blue-50 rounded px-2 py-1"
              >
                Change
              </button>
            )}
          </div>
        ) : (
          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
            No implementing agency set. Choose the government body accountable for this project.
          </p>
        )}

        {canEdit && (changingAgency || !agency) && (
          <select
            value=""
            disabled={working}
            onChange={(e) => e.target.value && void setAgency(e.target.value)}
            className="mt-2 w-full text-sm border border-gray-300 rounded px-2 py-1.5"
            aria-label="Choose the implementing agency"
          >
            <option value="">— choose a government body —</option>
            {governmentOrgs.map((o) => (
              <option key={o.organization_id} value={o.organization_id}>{o.name}</option>
            ))}
          </select>
        )}
        <p className="text-xs text-gray-400 mt-1.5">
          The signing ministry — grievances and reports are anchored to it. Government bodies only.
        </p>
      </div>

      {/* ── Donors ── */}
      <div>
        <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-2">
          Donors <span className="normal-case tracking-normal font-normal text-gray-400">— optional</span>
        </div>
        {loading ? (
          <p className="text-xs text-gray-400 italic">Loading…</p>
        ) : donors.length === 0 ? (
          <p className="text-xs text-gray-400 italic mb-2">No donors on this project.</p>
        ) : (
          <ul className="space-y-1.5 mb-2">
            {donors.map((d) => (
              <li
                key={d.organization_id}
                className="flex items-center gap-3 rounded-lg border border-green-200 bg-green-50/50 px-3 py-2"
              >
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-green-100 text-[11px] font-bold text-green-800">
                  {initials(d.name ?? d.organization_id)}
                </span>
                <span className="flex-1 min-w-0 text-sm text-gray-900 truncate">{d.name ?? d.organization_id}</span>
                {canEdit && (
                  <button
                    type="button"
                    onClick={() => void dropDonor(d.organization_id)}
                    disabled={working}
                    className="text-xs font-semibold text-red-600 hover:underline disabled:opacity-40"
                  >
                    Remove
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}

        {canEdit && (
          addingDonor ? (
            <select
              value=""
              autoFocus
              disabled={working}
              onChange={(e) => e.target.value && void addDonor(e.target.value)}
              onBlur={() => setAddingDonor(false)}
              className="w-full text-sm border border-gray-300 rounded px-2 py-1.5"
              aria-label="Choose a donor"
            >
              <option value="">— choose a donor —</option>
              {donorCandidates.map((o) => (
                <option key={o.organization_id} value={o.organization_id}>{o.name}</option>
              ))}
            </select>
          ) : (
            <button
              type="button"
              onClick={() => setAddingDonor(true)}
              className="text-sm font-semibold text-blue-600 border border-dashed border-blue-200 bg-blue-50 rounded px-3 py-1.5 hover:bg-blue-100"
            >
              + Add a donor
            </button>
          )
        )}
        <p className="text-xs text-gray-400 mt-1.5">
          A donor must be kept informed at the workflow&apos;s last level — that check is on the
          go-live list. Sensitive grievances are excluded.
        </p>
      </div>

      <p className="text-xs text-gray-400 border-t border-gray-100 pt-3">
        Officers are not added here. Put people on levels under{" "}
        <span className="font-medium text-gray-500">Project-wide staffing</span>.
      </p>
    </div>
  );
}
