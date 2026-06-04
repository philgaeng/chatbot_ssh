/** Display helpers for grievance summary / categories from API (may be JSON arrays). */

export function formatGrievanceCategories(raw: string | null | undefined): string {
  if (!raw?.trim()) return "";
  const trimmed = raw.trim();
  try {
    const parsed = JSON.parse(trimmed);
    if (Array.isArray(parsed)) {
      return parsed.map((c) => String(c).trim()).filter(Boolean).join(", ");
    }
  } catch {
    /* plain string */
  }
  return trimmed;
}
