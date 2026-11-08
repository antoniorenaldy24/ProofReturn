"""Non-custodial PayPal Sandbox REST v2 client and startup environment guard (INV-07, TM-16, Section 24.1)."""

from __future__ import annotations

from typing import Any

import httpx

ALLOWED_SANDBOX_BASE_URLS: set[str] = {
    "https://api-m.sandbox.paypal.com",
    "https://api.sandbox.paypal.com",
}


def validate_paypal_sandbox_url(base_url: str) -> None:
    """Reject non-Sandbox PayPal URLs at startup (TM-16)."""
    normalized = base_url.rstrip("/")
    if normalized not in ALLOWED_SANDBOX_BASE_URLS:
        raise ValueError(
            f"TM-16 startup guard failed: PayPal base URL '{base_url}' is not a valid PayPal Sandbox endpoint."
        )


class PayPalSandboxClient:
    """Strictly non-custodial PayPal Sandbox client (INV-07: Orders v2, Captures, Refunds, Webhooks only; NO Payouts)."""

    def __init__(
        self,
        base_url: str = "https://api-m.sandbox.paypal.com",
        client_id: str | None = None,
        client_secret: str | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        validate_paypal_sandbox_url(base_url)
        self.base_url = base_url.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self.timeout_seconds = timeout_seconds

    @property
    def has_credentials(self) -> bool:
        """True if PayPal Sandbox client ID and client secret are both provided."""
        return bool(self._client_id and self._client_secret)

    def fetch_oauth_token(self) -> dict[str, Any]:
        """Exchange Sandbox client credentials for an OAuth2 access token without logging secrets."""
        if not self._client_id or not self._client_secret:
            raise ValueError("PayPal Sandbox client_id and client_secret are required for live OAuth.")
        url = f"{self.base_url}/v1/oauth2/token"
        with httpx.Client(timeout=self.timeout_seconds) as client:
            resp = client.post(
                url,
                auth=(self._client_id, self._client_secret),
                data={"grant_type": "client_credentials"},
                headers={"Accept": "application/json", "Accept-Language": "en_US"},
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "token_type": data.get("token_type", "Bearer"),
                "expires_in": data.get("expires_in", 0),
                "access_token_present": bool(data.get("access_token")),
                "_access_token": data.get("access_token", ""),
            }

    def create_order_live(
        self,
        *,
        custom_id: str,
        request_id: str,
        amount_minor: int,
        currency: str = "USD",
    ) -> dict[str, Any]:
        """Create a real Order v2 on PayPal Sandbox using OAuth2 and PayPal-Request-Id."""
        tok = self.fetch_oauth_token()
        access_token = tok["_access_token"]
        value_str = f"{amount_minor / 100:.2f}"
        url = f"{self.base_url}/v2/checkout/orders"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": request_id,
        }
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "custom_id": custom_id,
                    "amount": {
                        "currency_code": currency,
                        "value": value_str,
                    },
                }
            ],
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return {
                "id": data.get("id"),
                "status": data.get("status"),
                "links": data.get("links", []),
                "paypal_debug_id": resp.headers.get("paypal-debug-id", ""),
            }

    def create_order(
        self,
        *,
        custom_id: str,
        amount_minor: int,
        currency: str = "USD",
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a PayPal Order v2 (live if credentials configured, fail-closed otherwise; RV3-01)."""
        if not self.has_credentials:
            raise RuntimeError("PAYPAL_NOT_CONFIGURED: PayPal credentials not configured; live order creation cannot execute.")
        return self.create_order_live(
            custom_id=custom_id,
            request_id=request_id or custom_id,
            amount_minor=amount_minor,
            currency=currency,
        )

    def capture_order_live(
        self,
        *,
        paypal_order_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Capture an approved PayPal Order v2 via live PayPal Sandbox API (AUD-02)."""
        tok = self.fetch_oauth_token()
        access_token = tok["_access_token"]
        url = f"{self.base_url}/v2/checkout/orders/{paypal_order_id}/capture"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        if request_id:
            headers["PayPal-Request-Id"] = request_id

        with httpx.Client(timeout=self.timeout_seconds) as client:
            resp = client.post(url, headers=headers, json={})
            resp.raise_for_status()
            data = resp.json()
            capture_id = ""
            capture_status = data.get("status", "")
            pu = data.get("purchase_units", [])
            if pu:
                captures = pu[0].get("payments", {}).get("captures", [])
                if captures:
                    capture_id = captures[0].get("id", "")
                    capture_status = captures[0].get("status", capture_status)
            if not capture_id:
                raise ValueError("PayPal order capture response missing capture ID")
            return {
                "id": capture_id,
                "order_id": data.get("id", paypal_order_id),
                "status": capture_status,
                "paypal_debug_id": resp.headers.get("paypal-debug-id", ""),
            }

    def capture_order(
        self,
        *,
        paypal_order_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Capture an approved PayPal Order v2 (live if credentials configured, fail-closed otherwise; AUD-02, ARC-19)."""
        if not self.has_credentials:
            raise RuntimeError("PAYPAL_NOT_CONFIGURED: PayPal credentials not configured; live capture cannot execute.")
        return self.capture_order_live(paypal_order_id=paypal_order_id, request_id=request_id)

    def refund_capture_live(
        self,
        *,
        capture_id: str,
        request_id: str,
        amount_minor: int,
        currency: str = "USD",
        invoice_id: str | None = None,
        custom_id: str | None = None,
        note_to_payer: str | None = None,
    ) -> dict[str, Any]:
        """Execute a real partial/full capture refund via PayPal Sandbox API (INV-01, INV-03, AUD-02)."""
        tok = self.fetch_oauth_token()
        access_token = tok["_access_token"]
        value_str = f"{amount_minor / 100:.2f}"
        url = f"{self.base_url}/v2/payments/captures/{capture_id}/refund"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": request_id,
        }
        payload: dict[str, Any] = {
            "amount": {
                "currency_code": currency,
                "value": value_str,
            }
        }
        if invoice_id:
            payload["invoice_id"] = invoice_id
        if custom_id:
            payload["custom_id"] = custom_id
        if note_to_payer:
            payload["note_to_payer"] = note_to_payer

        with httpx.Client(timeout=self.timeout_seconds) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return {
                "id": data.get("id"),
                "capture_id": capture_id,
                "request_id": request_id,
                "status": data.get("status", ""),
                "amount_minor": amount_minor,
                "currency": currency,
                "invoice_id": invoice_id,
                "custom_id": custom_id,
                "paypal_debug_id": resp.headers.get("paypal-debug-id", ""),
            }

    def refund_capture(
        self,
        *,
        capture_id: str,
        request_id: str,
        amount_minor: int,
        currency: str = "USD",
        invoice_id: str | None = None,
        custom_id: str | None = None,
        note_to_payer: str | None = None,
    ) -> dict[str, Any]:
        """Issue a partial or full capture refund with mandatory PayPal-Request-Id (INV-01, INV-02, INV-03, AUD-02)."""
        if not self.has_credentials:
            raise RuntimeError("PAYPAL_NOT_CONFIGURED: PayPal credentials not configured; live refund cannot execute.")
        return self.refund_capture_live(
            capture_id=capture_id,
            request_id=request_id,
            amount_minor=amount_minor,
            currency=currency,
            invoice_id=invoice_id,
            custom_id=custom_id,
            note_to_payer=note_to_payer,
        )

    def get_refund_live(
        self,
        *,
        refund_id: str,
    ) -> dict[str, Any]:
        """Query a PayPal refund status via GET /v2/payments/refunds/{refund_id} (RV3-01, FX-07, FX-18)."""
        tok = self.fetch_oauth_token()
        access_token = tok["_access_token"]
        url = f"{self.base_url}/v2/payments/refunds/{refund_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return {
                "id": data.get("id"),
                "status": data.get("status", ""),
                "status_details": data.get("status_details"),
                "status_detail": (
                    data.get("status_details", {}).get("reason")
                    if isinstance(data.get("status_details"), dict)
                    else data.get("status_detail")
                ),
                "paypal_debug_id": resp.headers.get("paypal-debug-id", ""),
            }

    def get_refund(
        self,
        *,
        refund_id: str,
    ) -> dict[str, Any]:
        """Fetch refund status from PayPal Sandbox via GET /v2/payments/refunds/{id} (fail-closed without credentials)."""
        if not self.has_credentials:
            raise RuntimeError("PAYPAL_NOT_CONFIGURED: PayPal credentials not configured; live refund lookup cannot execute.")
        return self.get_refund_live(refund_id=refund_id)

    def get_capture_live(
        self,
        *,
        capture_id: str,
    ) -> dict[str, Any]:
        """Query a PayPal capture via GET /v2/payments/captures/{capture_id} (RV3-12)."""
        tok = self.fetch_oauth_token()
        access_token = tok["_access_token"]
        url = f"{self.base_url}/v2/payments/captures/{capture_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            refunds = data.get("refunds", [])
            # PayPal captures endpoint does not embed refunds directly; query parent order via rel: "up" link if present
            if not refunds:
                up_link = next((lnk.get("href") for lnk in data.get("links", []) if lnk.get("rel") == "up"), None)
                if up_link:
                    try:
                        ord_resp = client.get(up_link, headers=headers)
                        if ord_resp.status_code == 200:
                            ord_data = ord_resp.json()
                            pu = ord_data.get("purchase_units", [])
                            if pu:
                                order_refunds = pu[0].get("payments", {}).get("refunds", [])
                                if isinstance(order_refunds, list):
                                    refunds = [
                                        r for r in order_refunds
                                        if any(
                                            lnk.get("rel") == "up" and capture_id in str(lnk.get("href"))
                                            for lnk in r.get("links", [])
                                        ) or not r.get("links")
                                    ]
                    except Exception:
                        pass
            return {
                "id": data.get("id", capture_id),
                "status": data.get("status", ""),
                "refunds": refunds,
                "links": data.get("links", []),
                "paypal_debug_id": resp.headers.get("paypal-debug-id", ""),
            }

    def get_capture_refunds_live(
        self,
        *,
        capture_id: str,
    ) -> list[dict[str, Any]]:
        """Query refunds associated with a capture via GET /v2/payments/captures/{capture_id} (RV3-12)."""
        cap_data = self.get_capture_live(capture_id=capture_id)
        refunds = cap_data.get("refunds")
        return list(refunds) if isinstance(refunds, list) else []

    def verify_webhook_signature_live(
        self,
        *,
        transmission_id: str,
        transmission_time: str,
        cert_url: str,
        auth_algo: str,
        transmission_sig: str,
        webhook_id: str,
        webhook_event: dict[str, Any],
    ) -> bool:
        """Call PayPal Sandbox /v1/notifications/verify-webhook-signature to verify webhook authenticity (AUD-24)."""
        tok = self.fetch_oauth_token()
        access_token = tok["_access_token"]
        url = f"{self.base_url}/v1/notifications/verify-webhook-signature"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "transmission_id": transmission_id,
            "transmission_time": transmission_time,
            "cert_url": cert_url,
            "auth_algo": auth_algo,
            "transmission_sig": transmission_sig,
            "webhook_id": webhook_id,
            "webhook_event": webhook_event,
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                return False
            data = resp.json()
            return data.get("verification_status") == "SUCCESS"
