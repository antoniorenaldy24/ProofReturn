import { NextRequest, NextResponse } from "next/server";

const BACKEND_BASE = process.env.BACKEND_URL || "http://localhost:8000";
const BOOTSTRAP_KEY = process.env.DEMO_BOOTSTRAP_KEY || "1d6a639071cc81affa41f198ba4bebb7866efb1fc55846cbcbcb0535336e065d";

// Sensitive internal endpoints that MUST NEVER be exposed via public frontend proxy
const BLOCKED_PATH_PREFIXES = ["ops", "metrics", "auth/staff-token"];

// Endpoints allowed through the public demo proxy
const ALLOWED_PATH_PREFIXES = [
  "ready",
  "health",
  "passports",
  "orders",
  "returns",
  "simulate",
  "auth/shopper-magic-link",
];

async function proxy(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const pathStr = path.join("/");

  // 1. Strict security boundary: Block internal ops, metrics, and staff token minting
  if (BLOCKED_PATH_PREFIXES.some((prefix) => pathStr === prefix || pathStr.startsWith(prefix + "/"))) {
    return NextResponse.json(
      {
        type: "https://proofreturn.dev/problems/forbidden",
        title: "Forbidden",
        status: 403,
        detail: `Access to internal endpoint '/v1/${pathStr}' via public frontend proxy is prohibited.`,
      },
      { status: 403 }
    );
  }

  // 2. Validate against allowed demo endpoint prefixes
  if (!ALLOWED_PATH_PREFIXES.some((prefix) => pathStr === prefix || pathStr.startsWith(prefix + "/"))) {
    return NextResponse.json(
      {
        type: "https://proofreturn.dev/problems/not-found",
        title: "Not Found",
        status: 404,
        detail: `Endpoint '/v1/${pathStr}' is not proxied.`,
      },
      { status: 404 }
    );
  }

  const targetPath = `/v1/${pathStr}`;
  const url = new URL(req.url);
  const targetUrl = `${BACKEND_BASE}${targetPath}${url.search}`;

  const headers = new Headers();
  headers.set("Accept", "application/json");

  // 3. Principle of Least Privilege: Only forward or inject X-Demo-Bootstrap-Key
  // if the client explicitly provided it, or specifically for shopper-magic-link demo intake.
  // NEVER inject it for administrative or general calls.
  const clientBootstrapKey = req.headers.get("x-demo-bootstrap-key") || req.headers.get("X-Demo-Bootstrap-Key");
  if (clientBootstrapKey) {
    headers.set("X-Demo-Bootstrap-Key", clientBootstrapKey);
  } else if (pathStr === "auth/shopper-magic-link") {
    headers.set("X-Demo-Bootstrap-Key", BOOTSTRAP_KEY);
  }

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
