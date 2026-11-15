import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

type Context = { params: Promise<{ path: string[] }> };

async function readBoundedBody(request: NextRequest, maxBytes: number): Promise<ArrayBuffer | null> {
  if (!request.body) return null;
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > maxBytes) {
        await reader.cancel();
        throw new Error("body-too-large");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const joined = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { joined.set(chunk, offset); offset += chunk.byteLength; }
  return joined.buffer;
}

async function forward(request: NextRequest, context: Context) {
  const contentLength = Number(request.headers.get("content-length") || 0);
  const { path } = await context.params;
  const isReportUpload = path.join("/") === "api/v1/reports/extract";
  const maxBody = isReportUpload ? 10 * 1024 * 1024 + 256 * 1024 : 16_384;
  if (contentLength > maxBody) return NextResponse.json({ detail: isReportUpload ? "The report exceeds the 10 MB limit." : "Request body too large." }, { status: 413 });
  const apiOrigin = process.env.API_BASE_URL || (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");
  if (!apiOrigin) return NextResponse.json({ detail: "API_BASE_URL is not configured." }, { status: 503 });
  const isPrivate = (path[0] === "api" && path[1] === "v1" && path[2] === "history") || isReportUpload;
  if (isPrivate && request.method !== "GET") {
    const origin = request.headers.get("origin");
    if (origin && origin !== new URL(request.url).origin) return NextResponse.json({ detail: "Request origin is not allowed." }, { status: 403 });
  }
  const supabase = await createClient();
  let accessToken: string | undefined;
  if (supabase) {
    const { data: claimsData } = await supabase.auth.getClaims();
    if (claimsData?.claims) {
      const { data } = await supabase.auth.getSession();
      accessToken = data.session?.access_token;
    }
  }
  if (isPrivate && !accessToken) return NextResponse.json({ detail: "Sign in to access account history." }, { status: 401 });
  let body: ArrayBuffer | null = null;
  if (request.method !== "GET" && request.method !== "HEAD") {
    try { body = await readBoundedBody(request, maxBody); }
    catch { return NextResponse.json({ detail: isReportUpload ? "The report exceeds the 10 MB limit." : "Request body too large." }, { status: 413 }); }
  }
  const target = new URL(`${apiOrigin.replace(/\/$/, "")}/${path.map(encodeURIComponent).join("/")}${new URL(request.url).search}`);
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  if (accessToken) headers.set("authorization", `Bearer ${accessToken}`);
  const forwardedFor = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim().slice(0, 64);
  if (forwardedFor && /^[a-fA-F0-9:.]+$/.test(forwardedFor)) headers.set("x-dms-rate-key", forwardedFor);
  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(isReportUpload ? 45_000 : 12_000),
    });
  } catch {
    return NextResponse.json({ detail: "The research API is unavailable. Please try again shortly." }, { status: 503 });
  }
  const responseHeaders = new Headers();
  for (const header of ["content-type", "content-disposition", "retry-after"]) {
    const value = upstream.headers.get(header);
    if (value) responseHeaders.set(header, value);
  }
  responseHeaders.set("cache-control", "no-store");
  return new NextResponse(await upstream.arrayBuffer(), { status: upstream.status, headers: responseHeaders });
}

export const GET = forward;
export const POST = forward;
export const DELETE = forward;
