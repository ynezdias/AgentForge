import { NextResponse, type NextRequest } from "next/server";
import { readSessionHint, SESSION_COOKIE, type Portal } from "@/lib/session";

/**
 * Route protection for the two portals. This is a navigation guard only: the
 * backend still authenticates and authorizes every API call independently.
 */
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const session = readSessionHint(request.cookies.get(SESSION_COOKIE)?.value);
  const portal: Portal | null = pathname.startsWith("/admin") ? "admin" : pathname.startsWith("/company") ? "company" : null;

  if (portal) {
    if (session?.role === portal) return NextResponse.next();
    const login = new URL(`/login/${portal}`, request.url);
    login.searchParams.set("next", `${pathname}${search}`);
    return NextResponse.redirect(login);
  }
  // Signed-in users visiting their own login page go straight to their portal.
  const loginPortal = pathname.match(/^\/login\/(admin|company)\/?$/)?.[1] as Portal | undefined;
  if (loginPortal && session?.role === loginPortal) {
    return NextResponse.redirect(new URL(`/${loginPortal}`, request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/admin", "/admin/:path*", "/company", "/company/:path*", "/login/:path*"],
};
