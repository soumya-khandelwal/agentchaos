"""HTTP Chaos Gateway for Salesforce External Services & Named Credentials."""

from __future__ import annotations

import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from agent_chaos.core.faults import Fault, FaultType
from agent_chaos.core.trajectory import TrajectoryRecorder

logger = logging.getLogger("agent_chaos.salesforce.gateway")


class SalesforceGatewayHandler(BaseHTTPRequestHandler):
    """Handles incoming Salesforce External Service callouts and injects chaos faults."""

    server: "SalesforceChaosServer"

    def do_GET(self) -> None:
        self._handle_request("GET")

    def do_POST(self) -> None:
        self._handle_request("POST")

    def do_PUT(self) -> None:
        self._handle_request("PUT")

    def do_DELETE(self) -> None:
        self._handle_request("DELETE")

    def _handle_request(self, method: str) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        # Read body if present
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b""
        body_dict: Dict[str, Any] = {}
        if body_bytes:
            try:
                body_dict = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                body_dict = {"raw_body": body_bytes.decode("utf-8", errors="replace")}

        # Merge query params and body for argument inspection
        arguments = dict(body_dict)
        for k, v in query_params.items():
            arguments[k] = v[0] if len(v) == 1 else v

        start_time = time.perf_counter()
        fault = self.server.get_fault_for_path(path)

        injected_fault_type = None
        status_code = 200
        response_body: bytes = b""
        content_type = "application/json"

        # Check if fault is configured and should trigger
        if fault:
            count = self.server.increment_invocation(path)
            if fault.should_trigger(count, arguments):
                injected_fault_type = fault.fault_type
                if fault.delay > 0:
                    time.sleep(fault.delay)

                if fault.fault_type == FaultType.TIMEOUT:
                    status_code = 504
                    response_body = json.dumps({
                        "error": fault.message or "Gateway Timeout: Downstream core service unreachable",
                        "status": 504,
                    }).encode("utf-8")

                elif fault.fault_type == FaultType.HTTP_ERROR:
                    status_code = fault.status_code
                    # If status is 502, test HTML page instead of JSON if payload specifies html
                    if fault.status_code == 502 and isinstance(fault.payload, str) and "<html" in fault.payload:
                        content_type = "text/html"
                        response_body = fault.payload.encode("utf-8")
                    else:
                        response_body = json.dumps(
                            fault.payload or {"error": fault.message, "status": fault.status_code}
                        ).encode("utf-8")

                elif fault.fault_type == FaultType.RATE_LIMIT:
                    status_code = 429
                    self.send_response(429)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Retry-After", "30")
                    self.end_headers()
                    resp_data = json.dumps({"error": "Rate limit exceeded", "retryAfter": 30}).encode("utf-8")
                    self.wfile.write(resp_data)
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    self.server.recorder.record_call(
                        tool_name=path,
                        arguments=arguments,
                        duration_ms=duration_ms,
                        fault_injected=fault.fault_type,
                        result={"status": 429},
                    )
                    return

                elif fault.fault_type == FaultType.MALFORMED_DATA:
                    status_code = 200
                    # Return corrupted / broken JSON text
                    if isinstance(fault.payload, str):
                        response_body = fault.payload.encode("utf-8")
                    else:
                        # Missing required keys or invalid schema
                        response_body = json.dumps(fault.payload or {"corrupted": True}).encode("utf-8")

                elif fault.fault_type == FaultType.POISONED_PAYLOAD:
                    status_code = 200
                    response_body = json.dumps({
                        "status": "COMPLETED",
                        "description": str(fault.payload),
                    }).encode("utf-8")

        # If not faulted, return default mock response for path
        if injected_fault_type is None:
            default_resp = self.server.get_default_response(path, method, arguments)
            status_code = 200
            response_body = json.dumps(default_resp).encode("utf-8")

        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(response_body)))
        self.send_header("X-AgentChaos-Intercepted", "true" if injected_fault_type else "false")
        self.end_headers()
        self.wfile.write(response_body)

        duration_ms = (time.perf_counter() - start_time) * 1000
        self.server.recorder.record_call(
            tool_name=path,
            arguments=arguments,
            duration_ms=duration_ms,
            fault_injected=injected_fault_type,
            result={"status": status_code, "body": response_body.decode("utf-8", errors="replace")[:200]},
        )

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy standard HTTP logs during tests
        pass


class SalesforceChaosServer(HTTPServer):
    """Custom HTTPServer maintaining fault rules and trajectory recordings for Salesforce."""

    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        recorder: Optional[TrajectoryRecorder] = None,
    ):
        super().__init__(server_address, SalesforceGatewayHandler)
        self.recorder = recorder or TrajectoryRecorder()
        self.faults: Dict[str, Fault] = {}
        self.invocations: Dict[str, int] = {}
        self.default_mocks: Dict[str, Callable[[str, Dict[str, Any]], Dict[str, Any]]] = {}

    def set_fault(self, path: str, fault: Fault) -> None:
        self.faults[path] = fault
        self.invocations[path] = 0

    def remove_fault(self, path: str) -> None:
        self.faults.pop(path, None)
        self.invocations.pop(path, None)

    def get_fault_for_path(self, path: str) -> Optional[Fault]:
        return self.faults.get(path)

    def increment_invocation(self, path: str) -> int:
        self.invocations[path] = self.invocations.get(path, 0) + 1
        return self.invocations[path]

    def register_default_mock(self, path: str, mock_fn: Callable[[str, Dict[str, Any]], Dict[str, Any]]) -> None:
        self.default_mocks[path] = mock_fn

    def get_default_response(self, path: str, method: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if path in self.default_mocks:
            return self.default_mocks[path](method, args)

        # Standard built-in mocks
        if "/payments/refund" in path:
            return {
                "refundId": "REF-99281",
                "status": "COMPLETED",
                "refundAmount": args.get("amount", 50.0),
                "timestamp": "2026-09-27T12:00:00Z",
            }
        elif "/orders/status" in path:
            return {
                "orderId": args.get("orderId", "ORD-101"),
                "status": "SHIPPED",
                "carrier": "FedEx",
                "trackingNumber": "TRK-9928172",
                "estimatedDelivery": "2026-10-02",
            }
        elif "/customers/verify" in path:
            return {
                "customerId": args.get("customerId", "CUST-001"),
                "tier": "PLATINUM_VIP",
                "maxDiscretionaryCredit": 250.0,
            }
        return {"status": "SUCCESS", "path": path}


class SalesforceChaosGateway:
    """Manages the lifecycle and fault routing for the Salesforce HTTP Chaos Gateway."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        recorder: Optional[TrajectoryRecorder] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.recorder = recorder or TrajectoryRecorder()
        self.server: Optional[SalesforceChaosServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the HTTP server on a background daemon thread."""
        self.server = SalesforceChaosServer((self.host, self.port), recorder=self.recorder)
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Shut down the HTTP server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None

    def set_fault(self, path: str, fault: Fault) -> None:
        assert self.server is not None, "Gateway must be started before setting faults"
        self.server.set_fault(path, fault)

    def remove_fault(self, path: str) -> None:
        assert self.server is not None
        self.server.remove_fault(path)

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"
