"use client";

export interface ClosureCaseHeader {
  reference: string;
  complaint_date?: string | null;
  resolved_date?: string | null;
  resolution_duration_days?: number | null;
  resolved_by?: string | null;
  project_name?: string | null;
  package_label?: string | null;
}

export interface ClosureOfficerMetrics {
  complaint_category?: string | null;
  escalated_yn?: string | null;
  stage_at_resolution?: string | null;
  stage_level_at_resolution?: string | null;
  days_spent_overdue?: number | null;
  sla_breached_yn?: string | null;
  resolution_category?: string | null;
  instance?: string | null;
  location_display?: string | null;
}

function MetaRow({ label, value }: { label: string; value?: string | number | null }) {
  if (value === undefined || value === null || value === "") return null;
  return (
    <p className="text-sm text-gray-600">
      <span className="font-medium text-gray-800">{label}:</span> {value}
    </p>
  );
}

export function ClosureSummaryBody({
  caseHeader,
  officerMetrics,
  publicView,
  officerFindings,
}: {
  caseHeader?: ClosureCaseHeader | null;
  officerMetrics?: ClosureOfficerMetrics | null;
  publicView?: {
    resolution_category_label?: string;
    resolution_text_public?: string;
    findings_summary_public?: string;
  } | null;
  officerFindings?: string | null;
}) {
  const duration = caseHeader?.resolution_duration_days;
  const durationLabel =
    typeof duration === "number"
      ? `${duration} day${duration === 1 ? "" : "s"}`
      : null;

  return (
    <div className="space-y-4 text-sm">
      {caseHeader && (
        <section className="bg-white border border-gray-200 rounded-lg p-4">
          <h2 className="font-semibold text-gray-900 mb-3">Case details</h2>
          <div className="space-y-1">
            <MetaRow label="Reference" value={caseHeader.reference} />
            <MetaRow label="Date of complaint" value={caseHeader.complaint_date} />
            <MetaRow label="Resolved" value={caseHeader.resolved_date} />
            <MetaRow label="Resolution duration" value={durationLabel} />
            <MetaRow label="Resolved by" value={caseHeader.resolved_by} />
            <MetaRow label="Project" value={caseHeader.project_name} />
            <MetaRow label="Package" value={caseHeader.package_label} />
          </div>
        </section>
      )}

      {officerMetrics && (
        <section className="bg-white border border-blue-100 rounded-lg p-4">
          <h2 className="font-semibold text-gray-900 mb-3">Officer view</h2>
          <div className="space-y-1">
            <MetaRow label="Complaint category" value={officerMetrics.complaint_category} />
            <MetaRow label="Escalated" value={officerMetrics.escalated_yn} />
            <MetaRow
              label="Stage at resolution"
              value={
                officerMetrics.stage_at_resolution
                  ? `${officerMetrics.stage_at_resolution}${
                      officerMetrics.stage_level_at_resolution
                        ? ` (${officerMetrics.stage_level_at_resolution})`
                        : ""
                    }`
                  : officerMetrics.stage_level_at_resolution
              }
            />
            <MetaRow
              label="Days spent overdue"
              value={
                typeof officerMetrics.days_spent_overdue === "number"
                  ? officerMetrics.days_spent_overdue
                  : null
              }
            />
            <MetaRow label="SLA breached" value={officerMetrics.sla_breached_yn} />
            <MetaRow label="Resolution category" value={officerMetrics.resolution_category} />
            <MetaRow label="Instance" value={officerMetrics.instance} />
            {officerMetrics.location_display && (
              <MetaRow label="Location" value={officerMetrics.location_display} />
            )}
          </div>
        </section>
      )}

      {officerFindings && (
        <section className="bg-white border border-gray-200 rounded-lg p-4">
          <h2 className="font-semibold text-gray-900 mb-2">Investigation summary (officers)</h2>
          <p className="text-gray-800 whitespace-pre-wrap leading-relaxed">{officerFindings}</p>
        </section>
      )}

      {publicView && (
        <section className="bg-white border rounded-lg p-4">
          <h2 className="font-semibold mb-2">Public view (complainant)</h2>
          {publicView.resolution_category_label && (
            <p>
              <strong>Outcome:</strong> {publicView.resolution_category_label}
            </p>
          )}
          {publicView.resolution_text_public && (
            <p className="mt-2 whitespace-pre-wrap text-gray-800">{publicView.resolution_text_public}</p>
          )}
          {publicView.findings_summary_public && (
            <p className="mt-2 whitespace-pre-wrap text-gray-700">{publicView.findings_summary_public}</p>
          )}
        </section>
      )}
    </div>
  );
}
