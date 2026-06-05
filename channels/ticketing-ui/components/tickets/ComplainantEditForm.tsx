"use client";

import { useEffect, useMemo, useState } from "react";
import {
  patchComplainant,
  type ComplainantPatchPayload,
  type GrievancePii,
  type TicketDetail,
} from "@/lib/api";
import {
  complainantIdentityOnFile,
  phoneTelHref,
} from "@/lib/complainant-contact";
import { formatUserFacingError } from "@/lib/user-messages";
import {
  IconActiveSession,
  IconExpiredSession,
  IconRevealStatement,
} from "@/lib/icons";
import { ComplainantMapLink } from "@/components/tickets/ComplainantMapLink";

const LOCATION_FIELDS: { key: keyof ComplainantPatchPayload; label: string }[] = [
  { key: "complainant_address", label: "Address" },
  { key: "complainant_village", label: "Village / Tole" },
  { key: "complainant_ward", label: "Ward No." },
  { key: "complainant_municipality", label: "Municipality / VDC" },
  { key: "complainant_district", label: "District" },
  { key: "complainant_province", label: "Province" },
  { key: "complainant_email", label: "Email" },
];

function buildFormState(
  pii: GrievancePii | null,
  canFillName: boolean,
  canFillPhone: boolean,
): ComplainantPatchPayload {
  return {
    complainant_full_name: canFillName ? "" : (pii?.complainant_name ?? ""),
    complainant_phone: canFillPhone ? "" : (pii?.phone_number ?? ""),
    complainant_address: (pii?.address as string | undefined) ?? "",
    complainant_municipality: (pii?.municipality as string | undefined) ?? "",
    complainant_district: (pii?.district as string | undefined) ?? "",
    complainant_province: (pii?.province as string | undefined) ?? "",
    complainant_email: pii?.email ?? "",
    complainant_village: (pii?.village as string | undefined) ?? "",
    complainant_ward: (pii?.ward as string | undefined) ?? "",
  };
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1">
      {children}
    </label>
  );
}

const inputClass =
  "w-full text-sm border border-gray-200 rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white";

interface ComplainantEditFormProps {
  ticket: TicketDetail;
  pii: GrievancePii | null;
  variant?: "desktop" | "mobile";
  onSaved?: () => void;
  onCancel?: () => void;
  onRevealOriginal?: () => void;
}

export function ComplainantEditForm({
  ticket,
  pii,
  variant = "desktop",
  onSaved,
  onCancel,
  onRevealOriginal,
}: ComplainantEditFormProps) {
  const isMobile = variant === "mobile";
  const maskSensitive = Boolean(ticket.is_seah);
  const canFillName = !maskSensitive && !complainantIdentityOnFile(pii?.complainant_name);
  const canFillPhone = !maskSensitive && !complainantIdentityOnFile(pii?.phone_number);

  const [form, setForm] = useState<ComplainantPatchPayload>(() =>
    buildFormState(pii, canFillName, canFillPhone),
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setForm(buildFormState(pii, canFillName, canFillPhone));
  }, [
    ticket.ticket_id,
    pii?.complainant_name,
    pii?.phone_number,
    pii?.address,
    pii?.municipality,
    canFillName,
    canFillPhone,
  ]);

  const helpText = useMemo(() => {
    if (maskSensitive) {
      return "SEAH case — edit address and location below. Name and phone use the audited reveal flow.";
    }
    if (canFillName || canFillPhone) {
      return "Add name or phone if the chatbot did not collect them. Once saved, those fields cannot be changed here.";
    }
    return "Update address and location. Name and phone are already on file and cannot be changed here.";
  }, [maskSensitive, canFillName, canFillPhone]);

  async function handleSave() {
    const payload: ComplainantPatchPayload = {};
    if (canFillName && form.complainant_full_name?.trim()) {
      payload.complainant_full_name = form.complainant_full_name.trim();
    }
    if (canFillPhone && form.complainant_phone?.trim()) {
      payload.complainant_phone = form.complainant_phone.trim();
    }
    for (const { key } of LOCATION_FIELDS) {
      const val = form[key];
      if (val?.trim()) payload[key] = val.trim();
    }
    if (Object.keys(payload).length === 0) {
      onCancel?.();
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await patchComplainant(ticket.ticket_id, payload);
      onSaved?.();
      if (!isMobile) onCancel?.();
    } catch (e) {
      setError(formatUserFacingError(e).message);
    } finally {
      setSaving(false);
    }
  }

  const phoneOnFile = complainantIdentityOnFile(pii?.phone_number);
  const phoneTel = phoneOnFile ? phoneTelHref(pii?.phone_number) : null;

  return (
    <div className={isMobile ? "px-5 pb-6" : ""}>
      <p className={`text-xs text-gray-500 ${isMobile ? "mb-4" : "mb-4"}`}>
        {helpText} All changes are logged in the case timeline.
      </p>

      <div className="space-y-3">
        {isMobile && (
          <div className="pb-1 border-b border-gray-100">
            <FieldLabel>Complainant ref</FieldLabel>
            <p className="text-sm text-gray-800">{ticket.complainant_id ?? "—"}</p>
          </div>
        )}

        {canFillName ? (
          <div>
            <FieldLabel>Full name</FieldLabel>
            <input
              type="text"
              value={form.complainant_full_name ?? ""}
              onChange={(e) =>
                setForm((f) => ({ ...f, complainant_full_name: e.target.value }))
              }
              className={`${inputClass} border-amber-200 focus:ring-amber-400`}
              placeholder="Enter complainant name"
            />
          </div>
        ) : phoneOnFile || complainantIdentityOnFile(pii?.complainant_name) ? (
          <div className={isMobile ? "py-1" : "text-xs text-gray-600"}>
            <FieldLabel>Name</FieldLabel>
            <p className="text-sm text-gray-800">{pii?.complainant_name}</p>
          </div>
        ) : null}

        {canFillPhone ? (
          <div>
            <FieldLabel>Phone number</FieldLabel>
            <input
              type="tel"
              value={form.complainant_phone ?? ""}
              onChange={(e) =>
                setForm((f) => ({ ...f, complainant_phone: e.target.value }))
              }
              className={`${inputClass} border-amber-200 focus:ring-amber-400`}
              placeholder="e.g. +97798XXXXXXXX"
            />
          </div>
        ) : phoneOnFile ? (
          <div className={isMobile ? "py-1" : "text-xs text-gray-600"}>
            <FieldLabel>Phone</FieldLabel>
            {phoneTel ? (
              <a
                href={phoneTel}
                className="text-sm text-blue-600 font-medium underline underline-offset-2"
              >
                {pii?.phone_number}
              </a>
            ) : (
              <p className="text-sm text-gray-800">{pii?.phone_number}</p>
            )}
          </div>
        ) : null}

        {LOCATION_FIELDS.map(({ key, label }) => (
          <div key={key}>
            <FieldLabel>{label}</FieldLabel>
            <input
              type={key === "complainant_email" ? "email" : "text"}
              value={form[key] ?? ""}
              onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
              className={inputClass}
              placeholder={`Enter ${label.toLowerCase()}`}
            />
          </div>
        ))}

        <ComplainantMapLink
          pii={pii}
          ticket={ticket}
          variant={isMobile ? "mobile" : "desktop"}
          embedded={isMobile}
        />

        {isMobile && (
          <div className="pt-1 border-t border-gray-100">
            <FieldLabel>Session</FieldLabel>
            {ticket.session_id ? (
              <p className="text-sm text-green-600 font-medium inline-flex items-center gap-1">
                <IconActiveSession size={14} strokeWidth={2} />
                Active
              </p>
            ) : (
              <p className="text-sm text-red-500 font-medium inline-flex items-center gap-1">
                <IconExpiredSession size={14} strokeWidth={2} />
                Expired — SMS fallback
              </p>
            )}
          </div>
        )}
      </div>

      {maskSensitive && ticket.grievance_id && onRevealOriginal && (
        <button
          type="button"
          onClick={onRevealOriginal}
          className={`mt-4 text-sm text-red-700 font-medium flex items-center gap-2 ${
            isMobile ? "w-full justify-center py-2" : ""
          }`}
        >
          <IconRevealStatement size={16} strokeWidth={2} />
          Reveal original statement
        </button>
      )}

      {error && <p className="text-xs text-red-600 mt-3">{error}</p>}

      <div className={`flex gap-2 ${isMobile ? "mt-5 sticky bottom-0 bg-white pt-2" : "mt-5"}`}>
        <button
          type="button"
          onClick={() => void handleSave()}
          disabled={saving}
          className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-semibold py-3 rounded-xl"
        >
          {saving ? "Saving…" : "Save changes"}
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            disabled={saving}
            className="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm font-medium py-3 rounded-xl"
          >
            {isMobile ? "Close" : "Cancel"}
          </button>
        )}
      </div>
    </div>
  );
}
