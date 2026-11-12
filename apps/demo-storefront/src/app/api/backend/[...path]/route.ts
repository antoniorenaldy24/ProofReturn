import { NextRequest, NextResponse } from "next/server";

const BACKEND_BASE = process.env.BACKEND_URL || "http://localhost:8000";
const BOOTSTRAP_KEY = process.env.DEMO_BOOTSTRAP_KEY || "1d6a639071cc81affa41f198ba4bebb7866efb1fc55846cbcbcb0535336e065d";

async function proxy(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const targetPath = `/v1/${path.join("/")}`;
  const url = new URL(req.url);
  const targetUrl = `${BACKEND_BASE}${targetPath}${url.search}`;

  const headers = new Headers();
  headers.set("Accept", "application/json");
  headers.set("X-Demo-Bootstrap-Key", BOOTSTRAP_KEY);

  const auth = req.headers.get("Authorization");
  if (auth) headers.set("Authorization", auth);

  const idempotency = req.headers.get("Idempotency-Key");
  if (idempotency) headers.set("Idempotency-Key", idempotency);

  const init: RequestInit = {
    method: req.method,
    headers,
  };

  if (["POST", "PUT", "PATCH"].includes(req.method)) {
    const contentType = req.headers.get("content-type");
    if (contentType) headers.set("Content-Type", contentType);
    init.body = await req.text();
  }

  try {
    const res = await fetch(targetUrl, init);
    const data = await res.text();
    return new NextResponse(data, {
      status: res.status,
      headers: {
        "Content-Type": res.headers.get("Content-Type") || "application/json",
      },
    });
  } catch (err: any) {
    return NextResponse.json(
      { error: "Backend proxy unreachable", detail: err.message },
      { status: 502 }
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const DELETE = proxy;
