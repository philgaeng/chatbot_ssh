/** Display helpers for grievance summary / categories from API (may be JSON arrays). */

export function parseGrievanceCategoryList(raw: string | null | undefined): string[] {
  if (!raw?.trim()) return [];
  const trimmed = raw.trim();
  try {
    const parsed = JSON.parse(trimmed);
    if (Array.isArray(parsed)) {
      return parsed.map((c) => String(c).trim()).filter(Boolean);
    }
  } catch {
    /* fall through — comma-separated or single value */
  }
  if (trimmed.includes(",")) {
    return trimmed.split(",").map((c) => c.trim()).filter(Boolean);
  }
  return [trimmed];
}

export function formatGrievanceCategories(raw: string | null | undefined): string {
  return parseGrievanceCategoryList(raw).join(", ");
}

export function grievanceCategoriesToPayload(categories: string[]): string {
  return JSON.stringify(categories.map((c) => c.trim()).filter(Boolean));
}

export function categoriesSelectionEqual(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  const sortedA = [...a].sort();
  const sortedB = [...b].sort();
  return sortedA.every((v, i) => v === sortedB[i]);
}
