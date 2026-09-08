const allowedRoots = new Set(["auth", "tenant", "audit", "organization"]);
const routeSegment = /^[a-z][a-z-]*$/;

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: Request, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  if (
    path.length === 0 ||
    !allowedRoots.has(path[0]) ||
    path.some((segment) => !routeSegment.test(segment))
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

  const upstream = await fetch(upstreamUrl, {
    method: request.method,
    headers,
    body:
      request.method === "GET" || request.method === "HEAD"
        ? undefined
        : await request.arrayBuffer(),
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
