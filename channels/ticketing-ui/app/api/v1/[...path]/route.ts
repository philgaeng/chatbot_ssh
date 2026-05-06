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
 * a `grm_mock_user` cookie (JSON: {user_id, role_keys[]}).  This proxy
 * reads it and injects X-Internal-User-Id / X-Internal-Role headers so the
 * FastAPI backend sees the correct mock officer rather than the default
 * mock-super-admin fallback.
 */
import { type NextRequest, NextResponse } from "next/server";

const UPSTREAM = process.env.TICKETING_API_URL ?? "http://localhost:5002";

async function proxy(
  req: NextRequest,
  path: string[],
): Promise<NextResponse> {
  const { search } = new URL(req.url);
  const target = `${UPSTREAM}/api/v1/${path.join("/")}${search}`;

  // Forward all headers except host (would cause SNI mismatch inside Docker)
  const fwdHeaders = new Headers();
  for (const [k, v] of req.headers.entries()) {
    if (k.toLowerCase() === "host") continue;
    fwdHeaders.set(k, v);
  }

  // Dev-bypass identity: inject X-Internal-User-Id / X-Internal-Role from the
  // grm_mock_user cookie (set by the MockRoleSwitcher in the UI header).
  // In production this cookie is never set so this is effectively a no-op.
  // req.cookies.get() already URL-decodes the cookie value — parse directly.
  const mockCookieRaw = req.cookies.get("grm_mock_user")?.value;
  if (mockCookieRaw) {
    try {
      const identity = JSON.parse(mockCookieRaw) as {
        user_id: string;
        role_keys: string[];
        organization_id?: string;
      };
      if (identity.user_id) {
        fwdHeaders.set("x-internal-user-id", identity.user_id);
        fwdHeaders.set("x-internal-role", identity.role_keys.join(","));
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
