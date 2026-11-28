import { employeePhotoUploadLimit, isAllowedIdentityPath } from "../../../../lib/identity-path";

type RouteContext = { params: Promise<{ path: string[] }> };

async function readPhotoUpload(request: Request): Promise<Uint8Array<ArrayBuffer> | null> {
  if (Number(request.headers.get("content-length")) > employeePhotoUploadLimit) return null;
  const reader = request.body?.getReader();
  if (!reader) return new Uint8Array(0);
  const chunks: Uint8Array[] = [];
  let length = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > employeePhotoUploadLimit) {
        await reader.cancel();
        return null;
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const body = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return body;
}

async function proxy(request: Request, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  if (
    !isAllowedIdentityPath(path)
  ) {
    return Response.json({ detail: "identity route not found" }, { status: 404 });
  }

  const endpoint = process.env.API_INTERNAL_URL ?? "http://api:8000";
  const incomingUrl = new URL(request.url);
  const upstreamUrl = new URL(`/${path.map(encodeURIComponent).join("/")}`, endpoint);
  upstreamUrl.search = incomingUrl.search;

  const headers = new Headers();
  for (const name of ["accept", "content-type", "cookie", "origin", "x-csrf-token"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }

  const photoUpload = request.method === "PUT" && path[0] === "employees" && path[3] === "photo";
  const body = photoUpload
    ? await readPhotoUpload(request)
    : request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer();
  if (body === null) return Response.json({ detail: "portrait exceeds 2 MB" }, { status: 413 });

  const upstream = await fetch(upstreamUrl, {
    method: request.method,
    headers,
    body,
    redirect: "manual",
  });

  return new Response(upstream.body, {
    status: upstream.status,
    headers: upstream.headers,
  });
}

export const dynamic = "force-dynamic";
export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
