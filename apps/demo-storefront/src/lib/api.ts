/**
 * ProofReturn live API bridge for Next.js.
 * Queries through the /api/backend proxy to FastAPI and SQLite.
 */

export async function getLivePassport(passportId: string = "pass_demo_1") {
  try {
    const res = await fetch(`/api/backend/passports/${passportId}`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function getLivePolicy(orderId: string = "ord_demo_1") {
  try {
    // First obtain magic link / token
    const authRes = await fetch("/api/backend/auth/shopper-magic-link", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ order_id: orderId, shopper_id: "shopper_1" }),
    });

    if (!authRes.ok) return null;
    const authData = await authRes.json();
    const token = authData.access_token;

    const policyRes = await fetch(`/api/backend/orders/${orderId}/policy`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!policyRes.ok) return null;
    return await policyRes.json();
  } catch {
    return null;
  }
}

export async function checkBackendReady() {
  try {
    const res = await fetch("/api/backend/ready");
    if (!res.ok) return false;
    const data = await res.json();
    return data.status === "ready";
  } catch {
    return false;
  }
}
