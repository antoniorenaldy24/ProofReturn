"""Observability, Request Correlation, and Structured Logging Middleware (Section 34, NFR-08, AUD-37)."""

from __future__ import annotations

from collections import defaultdict
import logging
import re
import threading
import time
import uuid
from typing import Any, Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.api.errors import ErrorCode
from backend.observability.logger import scrub_sensitive_log
from backend.observability.metrics import MetricsRegistry, format_structured_log

logger = logging.getLogger("proofreturn.access")


def _get_metric_route_path(request: Request) -> str:
    """Resolve bounded template route path to prevent unbounded cardinality and ID leakage (RV-11, TM-15)."""
    route = request.scope.get("route")
    if route and hasattr(route, "path") and route.path:
        return str(route.path)
    # Bounded fallback: replace dynamic entity IDs with templated placeholders
    raw_path = request.url.path
    return re.sub(
        r"/(?:ret|ord|item|pass|koff|app|resale|staff|merch|user|pe|ev|link|subj)_[a-zA-Z0-9_\-]+",
        r"/{\g<0>_id}",
        raw_path,
    )


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Correlates HTTP requests with X-Request-Id, measures latency, scrubs logs, and updates metrics."""

    def __init__(self, app: Any, metrics: MetricsRegistry | None = None) -> None:
        super().__init__(app)
        self.metrics = metrics or MetricsRegistry()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start_time = time.perf_counter()

        # 1. Request ID and Trace ID (Section 34.1)
        req_id = request.headers.get("X-Request-Id") or f"req_{uuid.uuid4().hex[:12]}"
        trace_id = request.headers.get("X-Trace-Id") or f"trc_{uuid.uuid4().hex[:16]}"

        request.state.request_id = req_id
        request.state.trace_id = trace_id

        # 2. Process request
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            route_path = _get_metric_route_path(request)
            log_data = format_structured_log(
                level="ERROR",
                service="proofreturn-api",
                message=f"Unhandled error on {request.method} {request.url.path}: {exc}",
                request_id=req_id,
                trace_id=trace_id,
            )
            logger.error(scrub_sensitive_log(log_data))
            self.metrics.inc_counter(
                "http_requests_total",
                labels={"method": request.method, "path": route_path, "status": "500"},
            )
            self.metrics.observe_histogram(
                "http_request_duration_ms",
                duration_ms,
                labels={"method": request.method, "path": route_path},
            )
            raise

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        route_path = _get_metric_route_path(request)

        # 3. Add correlation headers to response
        response.headers["X-Request-Id"] = req_id
        response.headers["X-Trace-Id"] = trace_id

        # 4. Record metrics in registry
        status_str = str(response.status_code)
        self.metrics.inc_counter(
            "http_requests_total",
            labels={"method": request.method, "path": route_path, "status": status_str},
        )
        self.metrics.observe_histogram(
            "http_request_duration_ms",
            duration_ms,
            labels={"method": request.method, "path": route_path},
        )

        if response.status_code in {401, 403}:
            self.metrics.inc_counter(
                "auth_failures_total",
                labels={"status": status_str, "path": route_path},
            )
        elif response.status_code == 409:
            self.metrics.inc_counter(
                "state_conflicts_total",
                labels={"path": route_path},
            )

        # 5. Extract domain context fields (AUD-37, Section 34.1)
        return_id = getattr(request.state, "return_id", None)
        if not return_id:
            m_ret = re.search(r"/(ret_[a-zA-Z0-9_\-]+)", request.url.path)
            if m_ret:
                return_id = m_ret.group(1)

        decision_id = getattr(request.state, "decision_id", None)
        if not decision_id:
            m_dec = re.search(r"/(dec_[a-zA-Z0-9_\-]+)", request.url.path)
            if m_dec:
                decision_id = m_dec.group(1)

        paypal_debug_id = (
            getattr(request.state, "paypal_debug_id", None)
            or response.headers.get("Paypal-Debug-Id")
            or response.headers.get("paypal-debug-id")
        )

        # 6. Emit scrubbed structured JSON log with domain fields
        level = "WARN" if response.status_code >= 400 else "INFO"
        log_entry = format_structured_log(
            level=level,
            service="proofreturn-api",
            message=f"{request.method} {request.url.path} -> {response.status_code} in {duration_ms:.2f}ms",
            request_id=req_id,
            trace_id=trace_id,
            return_id=return_id,
            decision_id=decision_id,
            paypal_debug_id=paypal_debug_id,
        )
        scrubbed = scrub_sensitive_log(log_entry)
        if level == "WARN":
            logger.warning(scrubbed)
        else:
            logger.info(scrubbed)

        return response


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Token-bucket & sliding window rate limiter per IP / token with bounded TTL eviction (AUD-30, Section 28.1)."""

    def __init__(
        self,
        app: Any,
        requests_per_minute: int = 300,
        window_seconds: float = 60.0,
        max_keys: int = 10000,
        ttl_seconds: float = 300.0,
    ) -> None:
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self.ttl_seconds = ttl_seconds
        self._history: dict[str, list[float]] = {}
        self._last_active: dict[str, float] = {}
        self._lock = threading.Lock()

    def evict_idle_keys(self, now: float | None = None) -> int:
        """Evict keys whose last active timestamp is older than ttl_seconds or enforce max_keys bound."""
        current_time = time.time() if now is None else now
        cutoff = current_time - self.ttl_seconds
        evicted = 0
        with self._lock:
            # 1. TTL-based eviction of idle keys
            idle_keys = [k for k, last_t in self._last_active.items() if last_t < cutoff]
            for k in idle_keys:
                self._history.pop(k, None)
                self._last_active.pop(k, None)
                evicted += 1

            # 2. Capacity-based LRU eviction if max_keys exceeded
            if len(self._history) > self.max_keys:
                sorted_by_activity = sorted(self._last_active.items(), key=lambda item: item[1])
                excess = len(self._history) - self.max_keys
                for k, _ in sorted_by_activity[:excess]:
                    self._history.pop(k, None)
                    self._last_active.pop(k, None)
                    evicted += 1
        return evicted

    def _get_client_key(self, request: Request) -> str:
        # Rate limit key priority: Authorization token signature > Forwarded IP > Client host
        auth = request.headers.get("authorization")
        if auth and "Bearer " in auth:
            token = auth.removeprefix("Bearer ").strip()
            parts = token.split(".")
            if len(parts) == 3:
                return f"token:{parts[2][:16]}"
        ip = (
            request.headers.get("x-forwarded-for")
            or (request.client.host if request.client else "127.0.0.1")
        )
        return f"ip:{ip.split(',')[0].strip()}"

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Exclude probe and documentation paths from rate limiting
        if request.url.path in {"/v1/health", "/v1/ready", "/docs", "/openapi.json"}:
            return await call_next(request)

        key = self._get_client_key(request)
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            # Periodic or per-request TTL eviction of idle keys
            cutoff = now - self.ttl_seconds
            idle_keys = [k for k, last_t in self._last_active.items() if last_t < cutoff]
            for k in idle_keys:
                self._history.pop(k, None)
                self._last_active.pop(k, None)

            # Prune timestamps older than window
            timestamps = [t for t in self._history.get(key, []) if t > window_start]
            if len(timestamps) >= self.requests_per_minute:
                self._history[key] = timestamps
                self._last_active[key] = now
                retry_after = int(self.window_seconds - (now - timestamps[0])) + 1
                return JSONResponse(
                    status_code=429,
                    content={
                        "type": "urn:problem:rate_limit_exceeded",
                        "title": "Too Many Requests",
                        "status": 429,
                        "detail": f"Rate limit exceeded ({self.requests_per_minute} req/min). Retry after {retry_after}s.",
                        "code": ErrorCode.RATE_LIMIT_EXCEEDED,
                        "error_code": ErrorCode.RATE_LIMIT_EXCEEDED,
                        "instance": request.url.path,
                    },
                    headers={
                        "Retry-After": str(max(1, retry_after)),
                        "X-RateLimit-Limit": str(self.requests_per_minute),
                        "X-RateLimit-Remaining": "0",
                        "Content-Type": "application/problem+json",
                    },
                )
            timestamps.append(now)
            self._history[key] = timestamps
            self._last_active[key] = now
            remaining = self.requests_per_minute - len(timestamps)

            # Bound history size if exceeding max_keys
            if len(self._history) > self.max_keys:
                oldest_key = min(self._last_active, key=self._last_active.get)
                if oldest_key != key:
                    self._history.pop(oldest_key, None)
                    self._last_active.pop(oldest_key, None)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        return response


class RequestBodyLimitMiddleware(BaseHTTPMiddleware):
    """Enforces request body size limit to prevent Denial-of-Service memory exhaustion (AUD-30)."""

    def __init__(self, app: Any, max_body_bytes: int = 10 * 1024 * 1024) -> None:
        super().__init__(app)
        self.max_body_bytes = max_body_bytes

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        content_length_header = request.headers.get("content-length")
        if content_length_header:
            try:
                content_length = int(content_length_header)
                if content_length > self.max_body_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "type": "urn:problem:payload_too_large",
                            "title": "Payload Too Large",
                            "status": 413,
                            "detail": f"Request body size {content_length} bytes exceeds maximum limit of {self.max_body_bytes} bytes.",
                            "code": ErrorCode.PAYLOAD_TOO_LARGE,
                            "error_code": ErrorCode.PAYLOAD_TOO_LARGE,
                            "instance": request.url.path,
                        },
                        headers={"Content-Type": "application/problem+json"},
                    )
            except ValueError:
                pass

        return await call_next(request)

