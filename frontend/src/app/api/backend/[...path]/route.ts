import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  if (path.some((part) => part === "." || part === ".." || /[/\\]/.test(part))) {
    return NextResponse.json({ detail: "Invalid backend path" }, { status: 400 });
  }
  const headers = new Headers();
  for (const name of ["content-type", "x-demo-manager-token", "idempotency-key"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  try {
    const url = new URL(`/api/v1/${path.map(encodeURIComponent).join("/")}`, BACKEND_URL);
    url.search = request.nextUrl.search;
    const response = await fetch(url, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.text(),
      cache: "no-store",
      redirect: "error",
    });
    return new NextResponse(response.body, {
      status: response.status,
      headers: { "content-type": response.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return NextResponse.json({ detail: "Backend unavailable" }, { status: 503 });
  }
}

export const GET = proxy;
export const POST = proxy;
