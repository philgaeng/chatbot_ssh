import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { isMobileUserAgent, isPublicRoute, toMobilePath } from "@/lib/mobile-routes";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (isPublicRoute(pathname)) return NextResponse.next();
  if (pathname.startsWith("/api") || pathname.startsWith("/_next")) return NextResponse.next();

  const ua = request.headers.get("user-agent") ?? "";
  if (!isMobileUserAgent(ua)) return NextResponse.next();

  const mobilePath = toMobilePath(pathname, request.nextUrl.search);
  if (!mobilePath) return NextResponse.next();

  return NextResponse.redirect(new URL(mobilePath, request.url));
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
