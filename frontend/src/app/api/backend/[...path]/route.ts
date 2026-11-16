import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE } from "@/lib/session";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
const FORWARDED_HEADERS = ["content-type", "idempotency-key"];
type RouteContext = { params: Promise<{ path: string[] }> };

function secureCookies(request: NextRequest) {
  if (process.env.COOKIE_SECURE === "true") return true;
  if (process.env.COOKIE_SECURE === "false") return false;
  const proto = request.headers.get("x-forwarded-proto") ?? request.nextUrl.protocol.replace(":", "");
  return proto === "https";
}

function sessionCookie(request: NextRequest, token: string, maxAge: number) {
  return { name: SESSION_COOKIE, value: token, httpOnly: true, sameSite: "lax" as const,
    secure: secureCookies(request), path: "/", maxAge };
}

/** Reject state-changing requests that a different site initiated (CSRF). */
function crossSite(request: NextRequest) {
  if (request.method === "GET" || request.method === "HEAD") return false;
  const origin = request.headers.get("origin");
  if (!origin) return request.headers.get("sec-fetch-site") === "cross-site";
  const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host");
  try { return new URL(origin).host !== host; } catch { return true; }
}

async function forward(request: NextRequest, apiPath: string, token?: string) {
  const headers = new Headers();
  for (const name of FORWARDED_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  // Never trust an Authorization header from the browser; only the cookie counts.
  if (token) headers.set("authorization", `Bearer ${token}`);
  // Client address for sign-in throttling (the backend trusts it only when configured to).
  const forwardedFor = request.headers.get("x-forwarded-for");
  if (forwardedFor) headers.set("x-forwarded-for", forwardedFor);
  const url = new URL(`/api/v1/${apiPath}`, BACKEND_URL);
  url.search = request.nextUrl.search;
  return fetch(url, {
    method: request.method, headers, cache: "no-store", redirect: "error",
    body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.text(),
  });
}

async function login(request: NextRequest) {
  const response = await forward(request, "auth/login");
  const body = await response.json().catch(() => ({ detail: "Sign-in failed" }));
  if (!response.ok) return NextResponse.json(body, { status: response.status });
  const maxAge = Math.max(0, Math.floor((Date.parse(body.expires_at) - Date.now()) / 1000));
  // The token goes into the HttpOnly cookie only; the browser receives the profile.
  const result = NextResponse.json({ user: body.user, expires_at: body.expires_at });
  result.cookies.set(sessionCookie(request, body.access_token, maxAge));
  return result;
}

async function logout(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  // Revoke the token server-side first; clear the cookie even if the backend is unreachable.
  if (token) await forward(request, "auth/logout", token).catch(() => undefined);
  const result = NextResponse.json({ status: "signed_out" });
  result.cookies.set(sessionCookie(request, "", 0));
  return result;
}

async function proxy(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  if (path.some((part) => part === "." || part === ".." || /[/\\]/.test(part))) {
    return NextResponse.json({ detail: "Invalid backend path" }, { status: 400 });
  }
  if (crossSite(request)) return NextResponse.json({ detail: "Cross-site request blocked" }, { status: 403 });
  const apiPath = path.map(encodeURIComponent).join("/");
  try {
    if (request.method === "POST" && apiPath === "auth/login") return await login(request);
    if (request.method === "POST" && apiPath === "auth/logout") return await logout(request);
    const response = await forward(request, apiPath, request.cookies.get(SESSION_COOKIE)?.value);
    const result = new NextResponse(response.body, {
      status: response.status,
      headers: { "content-type": response.headers.get("content-type") ?? "application/json" },
    });
    // An expired or revoked session is cleared so the next navigation goes to sign-in.
    if (response.status === 401) result.cookies.set(sessionCookie(request, "", 0));
    return result;
  } catch {
    return NextResponse.json({ detail: "Backend unavailable" }, { status: 503 });
  }
}

export const GET = proxy;
export const POST = proxy;
