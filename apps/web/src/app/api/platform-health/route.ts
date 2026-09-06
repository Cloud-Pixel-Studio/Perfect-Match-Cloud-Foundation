import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(): Promise<NextResponse> {
  const endpoint = process.env.API_INTERNAL_URL ?? "http://api:8000";
  try {
    const response = await fetch(`${endpoint}/health`, { cache: "no-store" });
    const body: unknown = await response.json();
    return NextResponse.json(body, { status: response.status });
  } catch {
    return NextResponse.json(
      {
        status: "unavailable",
        version: "unknown",
        dependencies: { database: "unknown", object_storage: "unknown" },
      },
      { status: 503 },
    );
  }
}
