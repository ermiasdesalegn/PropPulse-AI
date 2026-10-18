import type { NextRequest } from "next/server";

/**
 * Server-side proxy to the FastAPI backend. The admin key never reaches the browser.
 * Only /api/admin, /api/chat, /api/ingest and /api/cron paths are forwarded.
 */
const BACKEND_URL = (process.env.BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");
const ALLOWED_PREFIXES = ["api/admin/", "api/chat/", "api/ingest/", "api/cron/"];

async function forward(request: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const target = path.join("/");
  if (!ALLOWED_PREFIXES.some((prefix) => target.startsWith(prefix)) || target.includes("..")) {
    return Response.json({ detail: "Not found" }, { status: 404 });
  }

  const headers = new Headers({ "X-Admin-Key": process.env.ADMIN_API_KEY ?? "" });
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);

  try {
    const upstream = await fetch(`${BACKEND_URL}/${target}${request.nextUrl.search}`, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.text(),
      cache: "no-store",
    });
    return new Response(upstream.body, {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return Response.json({ detail: `Backend unreachable at ${BACKEND_URL}` }, { status: 502 });
  }
}

export const GET = forward;
export const POST = forward;
export const PATCH = forward;
export const DELETE = forward;
