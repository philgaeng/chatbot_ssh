/** Tailwind `md` breakpoint — viewports at or below this use /m/* routes. */
export const MOBILE_MAX_WIDTH_PX = 767;

export const PUBLIC_ROUTES = ["/login", "/auth/callback"];
export const PUBLIC_ROUTE_PREFIXES = ["/login/", "/closure/"];

export function isPublicRoute(pathname: string): boolean {
  return PUBLIC_ROUTES.includes(pathname) || PUBLIC_ROUTE_PREFIXES.some((p) => pathname.startsWith(p));
}

export function isMobileUserAgent(ua: string): boolean {
  return /Android|webOS|iPhone|iPod|BlackBerry|IEMobile|Opera Mini|Mobile/i.test(ua);
}

export function isMobileViewport(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia(`(max-width: ${MOBILE_MAX_WIDTH_PX}px)`).matches;
}

/** Map a desktop path to its mobile equivalent, or null if unchanged. */
export function toMobilePath(pathname: string, search = ""): string | null {
  if (pathname.startsWith("/m")) return null;

  const ticketDetail = pathname.match(/^\/tickets\/([^/]+)$/);
  if (ticketDetail) return `/m/tickets/${ticketDetail[1]}${search}`;
  if (pathname === "/queue") return `/m/queue${search}`;
  if (pathname === "/tickets") return `/m/tickets${search}`;
  if (pathname === "/") return `/m/queue${search}`;

  return null;
}

/** Map a mobile path to its desktop equivalent, or null if unchanged. */
export function toDesktopPath(pathname: string, search = ""): string | null {
  if (!pathname.startsWith("/m")) return null;

  const ticketDetail = pathname.match(/^\/m\/tickets\/([^/]+)$/);
  if (ticketDetail) return `/tickets/${ticketDetail[1]}${search}`;
  if (pathname === "/m/queue" || pathname === "/m/tasks") return `/queue${search}`;
  if (pathname === "/m/tickets") return `/tickets${search}`;

  return null;
}

export function defaultQueuePath(): string {
  if (typeof window !== "undefined" && isMobileViewport()) return "/m/queue";
  return "/queue";
}

export function ticketDetailPath(ticketId: string): string {
  if (typeof window !== "undefined" && isMobileViewport()) return `/m/tickets/${ticketId}`;
  return `/tickets/${ticketId}`;
}
