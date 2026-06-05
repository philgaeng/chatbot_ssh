/** Parse complainant map-pin coordinates and build Google Maps links. */

export interface MapCoordinates {
  lat: number;
  lng: number;
}

const MAP_PIN_IN_LABEL = /Map pin\s*\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)/i;

export function parseLocationGeo(raw: unknown): MapCoordinates | null {
  if (raw == null) return null;

  let obj: Record<string, unknown>;
  if (typeof raw === "string") {
    const text = raw.trim();
    if (!text.startsWith("{")) return null;
    try {
      const parsed = JSON.parse(text) as unknown;
      if (!parsed || typeof parsed !== "object") return null;
      obj = parsed as Record<string, unknown>;
    } catch {
      return null;
    }
  } else if (typeof raw === "object") {
    obj = raw as Record<string, unknown>;
  } else {
    return null;
  }

  const lat = Number(obj.lat);
  const lng = Number(obj.lng);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return null;
  return { lat, lng };
}

/** Fallback when only ticketing cache has the display label from map-pin submit. */
export function coordsFromGrievanceLocation(
  label: string | null | undefined,
): MapCoordinates | null {
  if (!label?.trim()) return null;
  const match = MAP_PIN_IN_LABEL.exec(label);
  if (!match) return null;
  const lat = Number(match[1]);
  const lng = Number(match[2]);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  return { lat, lng };
}

export function resolveMapCoordinates(
  locationGeo: unknown,
  grievanceLocation?: string | null,
): MapCoordinates | null {
  return parseLocationGeo(locationGeo) ?? coordsFromGrievanceLocation(grievanceLocation);
}

export function googleMapsUrl(lat: number, lng: number): string {
  return `https://www.google.com/maps?q=${lat},${lng}`;
}
