/** Client-side preview of organization_id (aligned with ticketing API rules). */

const ORG_NAME_TOKEN_RE = /[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\b)|\d+/g;

function splitOrgNameTokens(name: string): string[] {
  const parts = name.trim().split(/[\s_\-/]+/).filter(Boolean);
  const tokens: string[] = [];
  for (const p of parts) {
    const found = p.match(ORG_NAME_TOKEN_RE);
    if (!found || found.length === 0) {
      const alnum = p.replace(/[^a-zA-Z0-9]/g, "");
      if (alnum) tokens.push(alnum);
      continue;
    }
    for (const s of found) {
      const alnum = s.replace(/[^a-zA-Z0-9]/g, "");
      if (alnum) tokens.push(alnum);
    }
  }
  return tokens;
}

function slugCoreFromOrgName(name: string): string {
  const tokens = splitOrgNameTokens(name);
  if (tokens.length === 0) return "";
  if (tokens.length === 1) {
    const t = tokens[0];
    if (/^\d+$/.test(t)) return t;
    if (t.length <= 3) return t.toUpperCase();
    return t.slice(0, 6).toUpperCase();
  }
  let core = tokens.map((t) => (/^\d+$/.test(t) ? t : t[0].toUpperCase())).join("");
  if (core.length > 12) core = core.slice(0, 12);
  return core;
}

export function generateOrgId(name: string, country: string, existingIds: Set<string>): string {
  const core = slugCoreFromOrgName(name);
  if (!core) return "";
  const base = !country || core === "ADB" ? core : `${country}_${core}`;
  if (!existingIds.has(base)) return base;
  let n = 2;
  while (n < 100000) {
    const suffix = `_${n}`;
    const prefixLen = Math.max(0, 64 - suffix.length);
    const cand = base.slice(0, prefixLen) + suffix;
    if (!existingIds.has(cand)) return cand;
    n += 1;
  }
  return base;
}
