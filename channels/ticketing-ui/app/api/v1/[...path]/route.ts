/**
 * GRM API proxy — /api/v1/* → TICKETING_API_URL/api/v1/*
 *
 * Reads TICKETING_API_URL at **request time** (not build time), so the
 * Docker service name (http://ticketing_api:5002) works without baking
 * anything into the image.
 *
 * Browser only needs port 3001. No CORS issues.
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
