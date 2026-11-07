"""MCP Server exposing bounded agent return tools while enforcing physical evidence boundaries (INV-12, FR-45..47)."""

from __future__ import annotations

from collections import deque
from typing import Any

from backend.auth.tokens import AuthenticationError, verify_token


class ProofReturnMcpServer:
    """Implements the Section 28.4 MCP server tool surface for shopping assistants."""

    def __init__(self) -> None:
        self.audit_log: deque[dict[str, Any]] = deque(maxlen=10000)
        self._returns: dict[str, dict[str, Any]] = {}
        self._counter = 0

    def _parse_and_verify_agent_token(
        self,
        token: str,
        required_scope: str,
        expected_order_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            principal = verify_token(token)
        except AuthenticationError as exc:
            raise PermissionError(f"Agent token authentication failed: {exc}") from exc

        if principal.type != "agent":
            raise PermissionError("Token is not an agent token.")
        if expected_order_id is not None and principal.order_id != expected_order_id:
            raise LookupError("Order out of scope for this agent token (AZ-02).")
        if required_scope not in principal.scopes:
            raise PermissionError(f"Agent token missing required scope: {required_scope}")
        return {
            "order_id": principal.order_id,
            "scopes": principal.scopes,
            "agent_id": principal.sub,
        }

    def _log_action(self, tool: str, agent_id: str, target_id: str) -> None:
        self.audit_log.append(
            {
                "tool": tool,
                "actor": "agent",
                "agent_id": agent_id,
                "target_id": target_id,
            }
        )

    def get_return_policy(self, *, order_id: str, token: str) -> dict[str, Any]:
        """MCP tool: get_return_policy (FR-45)."""
        ctx = self._parse_and_verify_agent_token(token, "read_policy", expected_order_id=order_id)
        self._log_action("get_return_policy", ctx["agent_id"], order_id)
        return {
            "order_id": order_id,
            "policy_version": "pol_electronics_us_v1",
            "return_window_days": 30,
            "curve": {"A": 1.0, "B": 0.95, "C": 0.80, "D": 0.50},
        }

    def get_passport(self, *, passport_id: str, token: str) -> dict[str, Any]:
        """MCP tool: get_passport (public fields only per FR-43)."""
        ctx = self._parse_and_verify_agent_token(token, "read_policy")
        self._log_action("get_passport", ctx["agent_id"], passport_id)
        return {
            "passport_id": passport_id,
            "tier": "FULL",
            "origin_grade": "A",
            "signature_valid": True,
        }

    def start_return(self, *, order_id: str, declaration: dict[str, Any], token: str) -> dict[str, Any]:
        """MCP tool: start_return (submits structured declaration with actor=agent per FR-47)."""
        ctx = self._parse_and_verify_agent_token(token, "declare", expected_order_id=order_id)
        self._counter += 1
        ret_id = f"ret_agent_{self._counter:03d}"
        self._returns[ret_id] = {
            "return_id": ret_id,
            "order_id": order_id,
            "declaration": declaration,
            "state": "DECLARED",
            "keep_offer_status": "OFFERED",
        }
        self._log_action("start_return", ctx["agent_id"], ret_id)
        return {
            "return_id": ret_id,
            "order_id": order_id,
            "state": "DECLARED",
            "actor": "agent",
            "human_step_required": "SHOPPER_MUST_CAPTURE_LIVE_EVIDENCE",
        }

    def get_evidence_challenge(self, *, return_id: str, token: str) -> dict[str, Any]:
        """MCP tool: get_evidence_challenge — forbidden for agent tokens per INV-12 / AZ-03."""
        raise PermissionError("INV-12: AI agents cannot obtain physical evidence challenges.")

    def submit_evidence(self, *, return_id: str, token: str) -> dict[str, Any]:
        """MCP tool: submit_evidence — forbidden for agent tokens per INV-12 / AZ-03."""
        raise PermissionError("INV-12: AI agents cannot upload or attest physical evidence.")

    def get_keep_offer(self, *, return_id: str, token: str) -> dict[str, Any]:
        """MCP tool: get_keep_offer — returns single posted offer without internal caps (INV-06, FR-46)."""
        ret = self._returns.get(return_id)
        if not ret:
            raise LookupError("Unknown return_id")
        ctx = self._parse_and_verify_agent_token(token, "keep_offer", expected_order_id=ret["order_id"])
        self._log_action("get_keep_offer", ctx["agent_id"], return_id)
        return {
            "offer_id": f"ko_{return_id}",
            "return_id": return_id,
            "eligible": True,
            "amount_minor": 9100,
            "currency": "USD",
            "status": ret["keep_offer_status"],
            "expires_at": "2026-11-01T00:00:00Z",
            "allowed_actions": ["accept", "decline"],
        }

    def respond_keep_offer(self, *, return_id: str, action: str, token: str) -> dict[str, Any]:
        """MCP tool: respond_keep_offer — accepts only 'accept' or 'decline' (FR-46, FR-78)."""
        ret = self._returns.get(return_id)
        if not ret:
            raise LookupError("Unknown return_id")
        ctx = self._parse_and_verify_agent_token(token, "keep_offer", expected_order_id=ret["order_id"])
        if action not in {"accept", "decline"}:
            raise ValueError("KEEP_OFFER_ACTION_INVALID: only 'accept' or 'decline' are permitted.")
        ret["keep_offer_status"] = "ACCEPTED" if action == "accept" else "DECLINED"
        self._log_action("respond_keep_offer", ctx["agent_id"], return_id)
        return {
            "return_id": return_id,
            "status": ret["keep_offer_status"],
            "actor": "agent",
        }

    def get_return_status(self, *, return_id: str, token: str) -> dict[str, Any]:
        """MCP tool: get_return_status."""
        ret = self._returns.get(return_id)
        if not ret:
            raise LookupError("Unknown return_id")
        ctx = self._parse_and_verify_agent_token(token, "read_policy", expected_order_id=ret["order_id"])
        self._log_action("get_return_status", ctx["agent_id"], return_id)
        return {
            "return_id": return_id,
            "state": ret["state"],
            "keep_offer_status": ret["keep_offer_status"],
        }
