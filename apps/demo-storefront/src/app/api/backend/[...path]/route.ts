import { NextRequest, NextResponse } from "next/server";

const BACKEND_BASE = process.env.BACKEND_URL || "http://localhost:8000";
const BOOTSTRAP_KEY = process.env.DEMO_BOOTSTRAP_KEY || "";

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

  // 1. Strict anti-traversal validation: reject any dots, backslashes, or double-encoded characters (RV4-01)
  for (const seg of path) {
    if (
      seg === "." ||
      seg === ".." ||
      seg.includes("/") ||
      seg.includes("\\") ||
      seg.includes("%")
    ) {
      return NextResponse.json(
        {
          type: "https://proofreturn.dev/problems/forbidden",
          title: "Forbidden",
          status: 403,
          detail: "Path traversal or encoded separator sequence detected.",
        },
        { status: 403 }
      );
    }
    try {
      const decoded = decodeURIComponent(seg);
      if (decoded === "." || decoded === ".." || decoded.includes("/") || decoded.includes("\\")) {
        return NextResponse.json(
          {
            type: "https://proofreturn.dev/problems/forbidden",
            title: "Forbidden",
            status: 403,
            detail: "Path traversal sequence detected.",
          },
          { status: 403 }
        );
      }
    } catch {
      return NextResponse.json(
        {
          type: "https://proofreturn.dev/problems/bad-request",
          title: "Bad Request",
          status: 400,
          detail: "Malformed path encoding.",
        },
        { status: 400 }
      );
    }
  }

  // 2. Construct canonical target URL and inspect normalized pathname
  const cleanSubPath = path.map((s) => encodeURIComponent(s)).join("/");
  const target = new URL(`/v1/${cleanSubPath}`, BACKEND_BASE);
  const normalizedPath = target.pathname;

  // Ensure normalized path strictly stays under /v1/
  if (!normalizedPath.startsWith("/v1/")) {
    return NextResponse.json(
      {
        type: "https://proofreturn.dev/problems/forbidden",
        title: "Forbidden",
        status: 403,
        detail: "Path escape outside /v1/ boundary.",
      },
      { status: 403 }
    );
  }

  const relativePath = normalizedPath.slice("/v1/".length);

  // 3. Strict security boundary: Block internal ops, metrics, and staff token minting
  if (BLOCKED_PATH_PREFIXES.some((prefix) => relativePath === prefix || relativePath.startsWith(prefix + "/"))) {
    return NextResponse.json(
      {
        type: "https://proofreturn.dev/problems/forbidden",
        title: "Forbidden",
        status: 403,
        detail: `Access to internal endpoint '/v1/${relativePath}' via public frontend proxy is prohibited.`,
      },
      { status: 403 }
    );
  }

  // 4. Validate against allowed demo endpoint prefixes
  if (!ALLOWED_PATH_PREFIXES.some((prefix) => relativePath === prefix || relativePath.startsWith(prefix + "/"))) {
    return NextResponse.json(
      {
        type: "https://proofreturn.dev/problems/not-found",
        title: "Not Found",
        status: 404,
        detail: `Endpoint '/v1/${relativePath}' is not proxied.`,
      },
      { status: 404 }
    );
  }

  const searchParams = req.nextUrl?.search || "";
  const targetUrl = `${BACKEND_BASE}${normalizedPath}${searchParams}`;

  const headers = new Headers();
  headers.set("Accept", "application/json");

  // 5. Principle of Least Privilege: NEVER forward client-supplied X-Demo-Bootstrap-Key
  // Only inject server-configured BOOTSTRAP_KEY specifically for demo shopper magic links
  if (relativePath === "auth/shopper-magic-link" && BOOTSTRAP_KEY) {
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
export const PATCH = proxy;
export const DELETE = proxy;
