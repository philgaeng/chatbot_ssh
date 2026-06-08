"use client";

import type { ReactNode } from "react";
import type { GrievancePii, TicketDetail } from "@/lib/api";
import {
  complainantContactDisplay,
  phoneTelHref,
} from "@/lib/complainant-contact";
import {
  IconActiveSession,
  IconExpiredSession,
  IconRevealStatement,
} from "@/lib/icons";
import { ComplainantMapLink } from "@/components/tickets/ComplainantMapLink";

interface ComplainantContactFieldsProps {
  ticket: TicketDetail;
  pii: GrievancePii | null;
  /** When true, use compact mobile sheet rows instead of desktop inline rows. */
  variant?: "desktop" | "mobile";
  onRevealOriginal?: () => void;
}

function ContactRow({
  label,
  children,
  variant,
}: {
  label: string;
  children: ReactNode;
  variant: "desktop" | "mobile";
}) {
  if (variant === "mobile") {
    return (
      <div className="px-5 py-3.5 border-b border-gray-50">
        <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide mb-0.5">
          {label}
        </div>
        <div className="text-sm text-gray-800 leading-snug">{children}</div>
      </div>
    );
  }
  return (
    <div>
      <span className="text-gray-400">{label}:</span> {children}
    </div>
  );
}

export function ComplainantContactFields({
  ticket,
  pii,
  variant = "desktop",
  onRevealOriginal,
}: ComplainantContactFieldsProps) {
  const maskSensitive = Boolean(ticket.is_seah);
  const phone = complainantContactDisplay(pii?.phone_number, maskSensitive);
  const tel = !maskSensitive ? phoneTelHref(pii?.phone_number) : null;
  const textClass =
    variant === "desktop" ? "text-gray-800" : "";

  const phoneContent =
    tel && phone !== "—" ? (
      <a
        href={tel}
        className={`text-blue-600 font-medium underline underline-offset-2 ${textClass}`}
      >
        {phone}
      </a>
    ) : (
      <span className={variant === "desktop" ? "text-gray-800" : ""}>{phone}</span>
    );

  const sessionRow =
    variant === "mobile" ? (
      <ContactRow label="Session" variant={variant}>
        {ticket.session_id ? (
          <span className="inline-flex items-center gap-1 text-green-600 font-medium">
            <IconActiveSession size={12} strokeWidth={2} />
            Active
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-red-500 font-medium">
            <IconExpiredSession size={12} strokeWidth={2} />
            Expired — SMS fallback
          </span>
        )}
      </ContactRow>
    ) : (
      <div>
        <span className="text-gray-400">Session:</span>{" "}
        {ticket.session_id ? (
          <span className="inline-flex items-center gap-1 text-green-600">
            <IconActiveSession size={12} strokeWidth={2} />
            Active
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-red-500">
            <IconExpiredSession size={12} strokeWidth={2} />
            Expired — SMS fallback
          </span>
        )}
      </div>
    );

  const body =
    variant === "desktop" ? (
      <div className="text-xs space-y-1.5 text-gray-700">
        <ContactRow label="Name" variant={variant}>
          <span className="text-gray-800">
            {complainantContactDisplay(pii?.complainant_name, maskSensitive)}
          </span>
        </ContactRow>
        <div>
          <span className="text-gray-400">Ref:</span> {ticket.complainant_id ?? "—"}
        </div>
        <ContactRow label="Phone" variant={variant}>
          {phoneContent}
        </ContactRow>
        <ContactRow label="Email" variant={variant}>
          <span className="text-gray-800">
            {complainantContactDisplay(pii?.email, maskSensitive)}
          </span>
        </ContactRow>
        <ContactRow label="Address" variant={variant}>
          <span className="text-gray-800">
            {complainantContactDisplay(pii?.address, maskSensitive)}
          </span>
        </ContactRow>
        {pii?.municipality ? (
          <div>
            <span className="text-gray-400">Municipality:</span> {String(pii.municipality)}
          </div>
        ) : null}
        {pii?.district ? (
          <div>
            <span className="text-gray-400">District:</span> {String(pii.district)}
          </div>
        ) : null}
        <ComplainantMapLink pii={pii} ticket={ticket} variant="desktop" />
        {sessionRow}
      </div>
    ) : (
      <>
        {maskSensitive && (
          <div className="mx-5 mt-3 mb-2 bg-amber-50 border border-amber-100 rounded-xl px-4 py-2.5 text-xs text-amber-800">
            SEAH case — contact details are masked. Use Reveal original statement for audited
            access to sensitive content.
          </div>
        )}
        <ContactRow label="Name" variant={variant}>
          {complainantContactDisplay(pii?.complainant_name, maskSensitive)}
        </ContactRow>
        <ContactRow label="Complainant ref" variant={variant}>
          {ticket.complainant_id ?? "—"}
        </ContactRow>
        <ContactRow label="Phone" variant={variant}>
          {phoneContent}
        </ContactRow>
        <ContactRow label="Email" variant={variant}>
          {complainantContactDisplay(pii?.email, maskSensitive)}
        </ContactRow>
        <ContactRow label="Address" variant={variant}>
          {complainantContactDisplay(pii?.address, maskSensitive)}
        </ContactRow>
        {pii?.municipality ? (
          <ContactRow label="Municipality" variant={variant}>
            {String(pii.municipality)}
          </ContactRow>
        ) : null}
        {pii?.district ? (
          <ContactRow label="District" variant={variant}>
            {String(pii.district)}
          </ContactRow>
        ) : null}
        <ComplainantMapLink pii={pii} ticket={ticket} variant="mobile" />
        {sessionRow}
      </>
    );

  return (
    <>
      {body}
      {maskSensitive && ticket.grievance_id && onRevealOriginal && variant === "desktop" && (
        <div className="border-t border-gray-100 pt-2 mt-1">
          <button
            type="button"
            onClick={onRevealOriginal}
            className="text-xs text-red-700 hover:text-red-900 underline flex items-center gap-1"
          >
            <IconRevealStatement size={13} strokeWidth={2} />
            Reveal original statement
          </button>
        </div>
      )}
      {maskSensitive && ticket.grievance_id && onRevealOriginal && variant === "mobile" && (
        <div className="px-5 py-4 border-t border-gray-100">
          <button
            type="button"
            onClick={onRevealOriginal}
            className="text-sm text-red-700 font-medium flex items-center gap-2"
          >
            <IconRevealStatement size={16} strokeWidth={2} />
            Reveal original statement
          </button>
        </div>
      )}
    </>
  );
}
