/**
 * Server-side session helpers shared by proxy.ts and the backend route handler.
 *
 * The access token lives only in an HttpOnly cookie, so browser JavaScript can
 * never read it. Claims decoded here are used for routing decisions only; the
 * backend verifies the signature and the user on every API request.
 */
export const SESSION_COOKIE = "af_session";
export type Portal = "admin" | "company";
export type SessionHint = { role: Portal; exp: number };

export function readSessionHint(token: string | undefined): SessionHint | null {
  if (!token) return null;
  try {
    const payload = token.split(".")[1];
    const json = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
    if ((json.role !== "admin" && json.role !== "company") || typeof json.exp !== "number") return null;
    if (json.exp * 1000 <= Date.now()) return null;
    return { role: json.role, exp: json.exp };
  } catch {
    return null;
  }
}

/** Only allow redirects back into the signed-in user's own portal. */
export function safeNext(next: string | null | undefined, portal: Portal): string {
  const base = `/${portal}`;
  if (!next || next.startsWith("//") || next.includes("\\")) return base;
  return next === base || next.startsWith(`${base}/`) || next.startsWith(`${base}?`) ? next : base;
}
