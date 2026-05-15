/**
 * GRM API proxy — /api/v1/* → TICKETING_API_URL/api/v1/*
 *
 * Reads TICKETING_API_URL at **request time** (not build time), so the
 * Docker service name (http://ticketing_api:5002) works without baking
 * anything into the image.
 *
 * Browser only needs port 3001. No CORS issues.
 *
 * Dev-bypass identity: when NEXT_PUBLIC_BYPASS_AUTH=true the browser sets
 * a `grm_bypass_user` cookie (JSON: {user_id, role_keys[], organization_id?}).
 * This proxy injects X-Internal-User-Id / X-Internal-Role / optional
 * X-Internal-Organization-Id so the backend matches the selected roster officer.
 */
import { type NextRequest, NextResponse } from "next/server";

const UPSTREAM = process.env.TICKETING_API_URL ?? "http://localhost:5002";

// Hop-by-hop headers (RFC 7230 §6.1) — must NOT be forwarded by a proxy.
// undici (Node 18+ fetch) explicitly refuses any of these in the request
// headers and throws UND_ERR_INVALID_ARG, which surfaces here as a 500.
// Browsers / load balancers happily set Connection/Keep-Alive on inbound
// requests, so the proxy has to filter them out before the upstream fetch.
const HOP_BY_HOP = new Set([
  "host",                  // SNI mismatch inside Docker; preserved by upstream's Host
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

async function proxy(
  req: NextRequest,
  path: string[],
): Promise<NextResponse> {
  const { search } = new URL(req.url);
  const target = `${UPSTREAM}/api/v1/${path.join("/")}${search}`;

  const fwdHeaders = new Headers();
  for (const [k, v] of req.headers.entries()) {
    if (HOP_BY_HOP.has(k.toLowerCase())) continue;
    fwdHeaders.set(k, v);
  }

  // Dev-bypass identity (demo build): grm_bypass_user from BypassRoleSwitcher.
  const bypassCookieRaw = req.cookies.get("grm_bypass_user")?.value;
  if (bypassCookieRaw) {
    try {
      const identity = JSON.parse(bypassCookieRaw) as {
        user_id: string;
        role_keys: string[];
        organization_id?: string;
      };
      if (identity.user_id) {
        fwdHeaders.set("x-internal-user-id", identity.user_id);
        fwdHeaders.set("x-internal-role", identity.role_keys.join(","));
        const org = (identity.organization_id ?? "").trim();
        if (org) {
          fwdHeaders.set("x-internal-organization-id", org);
        }
      }
    } catch {
      // malformed cookie — fall through to backend default
    }
  }

  const hasBody = req.method !== "GET" && req.method !== "HEAD";

  const upstream = await fetch(target, {
    method: req.method,
    headers: fwdHeaders,
    // Pass the raw body stream through (handles JSON, multipart, binary)
    body: hasBody ? req.body : undefined,
    // Required for streaming request body in Node.js ≥ 18
    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-ignore — duplex is a Node fetch option, not in TS types
    duplex: "half",
  });

  return new NextResponse(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: upstream.headers,
  });
}

type Params = { params: Promise<{ path: string[] }> };

const handler = async (req: NextRequest, { params }: Params) => {
  const { path } = await params;
  return proxy(req, path);
};

export const GET     = handler;
export const POST    = handler;
export const PUT     = handler;
export const PATCH   = handler;
export const DELETE  = handler;
export const HEAD    = handler;
export const OPTIONS = handler;
