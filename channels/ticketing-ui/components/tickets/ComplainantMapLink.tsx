"use client";

import { MapPin } from "lucide-react";
import type { GrievancePii, TicketDetail } from "@/lib/api";
import { googleMapsUrl, resolveMapCoordinates } from "@/lib/location-geo";

interface ComplainantMapLinkProps {
  pii: GrievancePii | null;
  ticket?: TicketDetail;
  variant?: "desktop" | "mobile";
  /** Inside ComplainantEditForm — skip bottom-sheet row padding. */
  embedded?: boolean;
}

export function ComplainantMapLink({
  pii,
  ticket,
  variant = "desktop",
  embedded = false,
}: ComplainantMapLinkProps) {
  if (ticket?.is_seah) return null;

  const coords = resolveMapCoordinates(pii?.location_geo, ticket?.grievance_location);
  if (!coords) return null;

  const href = googleMapsUrl(coords.lat, coords.lng);
  const label = `${coords.lat.toFixed(5)}, ${coords.lng.toFixed(5)}`;

  if (variant === "mobile") {
    const link = (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-sm text-blue-600 font-medium underline underline-offset-2 inline-flex items-center gap-1.5"
      >
        <MapPin size={14} className="shrink-0" />
        Open in Google Maps
        <span className="text-gray-500 font-normal no-underline">({label})</span>
      </a>
    );
    if (embedded) {
      return (
        <div className="py-1">
          <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1">
            Map pin
          </p>
          {link}
        </div>
      );
    }
    return (
      <div className="px-5 py-3.5 border-b border-gray-50">
        <div className="text-[11px] font-semibold text-gray-400 uppercase tracking-wide mb-0.5">
          Map pin
        </div>
        {link}
      </div>
    );
  }

  return (
    <div>
      <span className="text-gray-400">Map pin:</span>{" "}
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-blue-600 font-medium underline underline-offset-2 inline-flex items-center gap-1"
      >
        <MapPin size={12} className="shrink-0" />
        Google Maps
        <span className="text-gray-500 font-normal">({label})</span>
      </a>
    </div>
  );
}
