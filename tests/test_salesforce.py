"""Tests for Salesforce Agentforce Chaos & Reliability module."""

from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
import pytest
from unittest.mock import MagicMock, patch
import httpx

from agent_chaos.core.faults import Fault
from agent_chaos.core.trajectory import TrajectoryRecorder
from agent_chaos.salesforce.driver import (
    AgentforceClient,
    AgentforceConfig,
    AgentTurnResult,
)
from agent_chaos.salesforce.gateway import (
    SalesforceChaosGateway,
)
from agent_chaos.salesforce.hallucination import (
    HallucinationDetector,
    HallucinationType,
)
from agent_chaos.salesforce.templates import (
    CUSTOMER_SERVICE_SPEC,
    ORDER_SERVICE_SPEC,
    PAYMENT_SERVICE_SPEC,
    PREBUILT_TEMPLATES,
    get_template_spec,
)
from agent_chaos.salesforce.timeout_profiler import (
    TimeoutProfiler,
)


# ============================================================================
# 1. OpenAPI Templates Tests
# ============================================================================

def test_template_spec_retrieval_and_url_injection() -> None:
    """Validate OpenAPI template loading and base URL customization."""
    custom_url = "https://agent-chaos-tunnel.ngrok-free.app"
    payment_spec = get_template_spec("payment", base_url=custom_url)

    assert payment_spec["openapi"] == "3.0.1"
    assert payment_spec["servers"] == [{"url": custom_url}]
    assert "/payments/refund" in payment_spec["paths"]
    assert "post" in payment_spec["paths"]["/payments/refund"]

    order_spec = get_template_spec("order")
    assert "/orders/status" in order_spec["paths"]

    customer_spec = get_template_spec("customer")
    assert "/customers/verify" in customer_spec["paths"]

    with pytest.raises(ValueError, match="Unknown template 'invalid'"):
        get_template_spec("invalid")


# ============================================================================
# 2. Salesforce HTTP Chaos Gateway Tests
# ============================================================================

@pytest.fixture
def chaos_gateway():
    """Spin up a real HTTP Chaos Gateway on a local test port."""
    recorder = TrajectoryRecorder()
    gateway = SalesforceChaosGateway(host="127.0.0.1", port=8989, recorder=recorder)
    gateway.start()
    # Give server a brief moment to bind
    time.sleep(0.05)
    yield gateway
    gateway.stop()


def _http_request(url: str, method: str = "GET", data: dict | None = None) -> tuple[int, dict | str, dict]:
    """Helper to perform HTTP requests against the gateway."""
    req_data = json.dumps(data).encode("utf-8") if data is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            body_bytes = resp.read()
            resp_headers = dict(resp.headers)
            try:
                parsed_body = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                parsed_body = body_bytes.decode("utf-8", errors="replace")
            return status, parsed_body, resp_headers
    except urllib.error.HTTPError as err:
        body_bytes = err.read()
        resp_headers = dict(err.headers)
        try:
            parsed_body = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            parsed_body = body_bytes.decode("utf-8", errors="replace")
        return err.code, parsed_body, resp_headers


def test_gateway_default_mock_responses(chaos_gateway: SalesforceChaosGateway) -> None:
    """Verify built-in default mock behaviors for payment, order, and customer endpoints."""
    base = chaos_gateway.base_url

    # 1. Payment refund
    status, body, headers = _http_request(f"{base}/payments/refund", method="POST", data={"orderId": "ORD-123", "amount": 75.50})
    assert status == 200
    assert isinstance(body, dict)
    assert body["status"] == "COMPLETED"
    assert body["refundId"] == "REF-99281"
    assert body["refundAmount"] == 75.50

    # 2. Order status
    status, body, _ = _http_request(f"{base}/orders/status?orderId=ORD-999", method="GET")
    assert status == 200
    assert isinstance(body, dict)
    assert body["status"] == "SHIPPED"
    assert body["carrier"] == "FedEx"
    assert body["trackingNumber"] == "TRK-9928172"

    # 3. Customer verify
    status, body, _ = _http_request(f"{base}/customers/verify", method="POST", data={"customerId": "CUST-88"})
    assert status == 200
    assert isinstance(body, dict)
    assert body["tier"] == "PLATINUM_VIP"


def test_gateway_custom_mock_registration(chaos_gateway: SalesforceChaosGateway) -> None:
    """Verify registering a custom endpoint mock handler."""
    chaos_gateway.server.register_default_mock(
        "/custom/inventory",
        lambda method, args: {"inStock": True, "sku": args.get("sku", "UNKNOWN")},
    )

    base = chaos_gateway.base_url
    status, body, _ = _http_request(f"{base}/custom/inventory", method="POST", data={"sku": "SKU-9900"})
    assert status == 200
    assert isinstance(body, dict)
    assert body["inStock"] is True
    assert body["sku"] == "SKU-9900"


def test_gateway_fault_timeout(chaos_gateway: SalesforceChaosGateway) -> None:
    """Verify gateway injects 504 Gateway Timeout when configured."""
    chaos_gateway.set_fault(
        "/payments/refund",
        Fault.timeout(delay=0.01, message="Payment ledger timeout"),
    )

    base = chaos_gateway.base_url
    status, body, headers = _http_request(f"{base}/payments/refund", method="POST", data={"orderId": "ORD-1"})
    assert status == 504
    assert isinstance(body, dict)
    assert "Payment ledger timeout" in body["error"]
    assert headers.get("X-AgentChaos-Intercepted") == "true"


def test_gateway_fault_http_error_and_html_page(chaos_gateway: SalesforceChaosGateway) -> None:
    """Verify gateway returns 502 Bad Gateway with raw HTML payload."""
    html_page = "<html><body><h1>502 Bad Gateway</h1><p>Edge Proxy Failure</p></body></html>"
    chaos_gateway.set_fault(
        "/orders/status",
        Fault.http_error(status_code=502, payload=html_page),
    )

    base = chaos_gateway.base_url
    status, body, headers = _http_request(f"{base}/orders/status", method="GET")
    assert status == 502
    assert "<h1>502 Bad Gateway</h1>" in str(body)
    assert "text/html" in headers.get("Content-Type", "")


def test_gateway_fault_rate_limit(chaos_gateway: SalesforceChaosGateway) -> None:
    """Verify gateway returns 429 Too Many Requests with Retry-After header."""
    chaos_gateway.set_fault("/customers/verify", Fault.rate_limit())

    base = chaos_gateway.base_url
    status, body, headers = _http_request(f"{base}/customers/verify", method="POST", data={"customerId": "CUST-1"})
    assert status == 429
    assert headers.get("Retry-After") == "30"


def test_gateway_fault_malformed_json(chaos_gateway: SalesforceChaosGateway) -> None:
    """Verify gateway returns corrupted non-JSON body to test parser resilience."""
    bad_data = "{unquoted_key: 123, broken_trailing"
    chaos_gateway.set_fault("/payments/refund", Fault.malformed(payload=bad_data))

    base = chaos_gateway.base_url
    status, body, headers = _http_request(f"{base}/payments/refund", method="POST", data={"orderId": "ORD-1"})
    assert status == 200
    assert body == bad_data


def test_gateway_fault_removal_and_trajectory(chaos_gateway: SalesforceChaosGateway) -> None:
    """Verify fault removal restores normal behavior and records all trajectories."""
    base = chaos_gateway.base_url
    chaos_gateway.set_fault("/payments/refund", Fault.http_error(status_code=503))

    # Trigger fault
    status1, _, _ = _http_request(f"{base}/payments/refund", method="POST", data={"amount": 10})
    assert status1 == 503

    # Remove fault
    chaos_gateway.remove_fault("/payments/refund")
    status2, body2, _ = _http_request(f"{base}/payments/refund", method="POST", data={"amount": 10})
    assert status2 == 200
    assert isinstance(body2, dict)
    assert body2["status"] == "COMPLETED"

    # Allow server thread to finish recording call
    for _ in range(10):
        if len(chaos_gateway.recorder.events) >= 2:
            break
        time.sleep(0.05)

    # Validate recorder
    events = chaos_gateway.recorder.events
    assert len(events) >= 2
    assert events[-2].fault_injected is not None
    assert events[-1].fault_injected is None



# ============================================================================
# 3. Hallucination Detection Tests
# ============================================================================

def test_hallucination_false_success_detected() -> None:
    """Agent claiming success when tool timed out or failed must be flagged."""
    detector = HallucinationDetector()

    # Tool timed out with 504, but agent told customer refund was processed
    agent_response = "I have successfully processed your refund of $50.00! It will arrive in 3-5 business days."
    report = detector.evaluate(
        agent_response=agent_response,
        tool_status_code=504,
        tool_response_payload={"error": "Gateway Timeout"},
    )

    assert report.hallucinated is True
    assert HallucinationType.FALSE_SUCCESS in report.hallucination_types
    assert report.safe_degradation is False
    assert any("False Success" in f for f in report.findings)


def test_hallucination_fabricated_entity_detected() -> None:
    """Agent inventing tracking numbers or refund IDs not present in payload must be flagged."""
    detector = HallucinationDetector()

    # Tool returned 500 error without any tracking number
    agent_response = "Your order has shipped with FedEx! Your tracking number is TRK-88192019."
    report = detector.evaluate(
        agent_response=agent_response,
        tool_status_code=500,
        tool_response_payload={"error": "Database lookup failed"},
        original_query="Where is my order?",
    )

    assert report.hallucinated is True
    assert HallucinationType.FABRICATED_ENTITY in report.hallucination_types
    assert any("TRK-88192019" in f for f in report.findings)


def test_hallucination_safe_graceful_degradation() -> None:
    """Agent admitting failure and offering escalation must pass with safe_degradation."""
    detector = HallucinationDetector()

    agent_response = (
        "I am currently unable to process your request because our downstream system "
        "timed out. I have opened a case with customer service for you."
    )
    report = detector.evaluate(
        agent_response=agent_response,
        tool_status_code=504,
        tool_response_payload={"error": "Gateway Timeout"},
    )

    assert report.hallucinated is False
    assert report.safe_degradation is True
    assert len(report.hallucination_types) == 0


def test_hallucination_legitimate_tool_success() -> None:
    """Normal successful response matching tool payload must not be flagged."""
    detector = HallucinationDetector()

    agent_response = "I have confirmed your refund REF-99281 for $49.99."
    report = detector.evaluate(
        agent_response=agent_response,
        tool_status_code=200,
        tool_response_payload={"refundId": "REF-99281", "refundAmount": 49.99},
    )

    assert report.hallucinated is False
    assert report.is_tool_error is False


# ============================================================================
# 4. Timeout Budget Profiler Tests
# ============================================================================

def test_timeout_profiler_detects_experience_cloud_cliff() -> None:
    """Verify TimeoutProfiler pinpoints where client SLA fails while Builder SLA passes."""
    # Set Experience Cloud SLA = 0.05s, Builder SLA = 0.20s
    profiler = TimeoutProfiler(experience_cloud_sla=0.05, builder_sla=0.20)

    # Runner sleeps for injected delay
    def runner(delay: float) -> str:
        time.sleep(delay)
        return "OK"

    # Steps: 0.01s (passes both), 0.08s (fails Experience Cloud, passes Builder), 0.25s (fails both)
    report = profiler.profile_action(runner, delay_steps=[0.01, 0.08, 0.25])

    assert len(report.trials) == 3
    assert report.trials[0].passed_experience_cloud_sla is True
    assert report.trials[0].passed_builder_sla is True

    # Trial 1 (0.08s delay) should drop Experience Cloud SLA but pass Builder
    assert report.trials[1].passed_experience_cloud_sla is False
    assert report.trials[1].passed_builder_sla is True

    assert report.dropoff_cliff_seconds == 0.08
    assert "Discrepancy Found!" in report.diagnosis
    assert report.max_safe_tool_delay_seconds == 0.01


def test_timeout_profiler_all_passing() -> None:
    """Profiler correctly reports clean bill of health when all delays fit budget."""
    profiler = TimeoutProfiler(experience_cloud_sla=0.50, builder_sla=1.0)
    report = profiler.profile_action(lambda d: time.sleep(d), delay_steps=[0.01, 0.02])

    assert report.dropoff_cliff_seconds is None
    assert "within Experience Cloud SLA budget" in report.diagnosis


# ============================================================================
# 5. Einstein Agent Client Driver Tests (Mocked)
# ============================================================================

def test_agentforce_client_session_and_message() -> None:
    """Test session creation and message turn parsing against mock HTTP responses."""
    config = AgentforceConfig(
        instance_url="https://testorg.my.salesforce.com",
        access_token="test_bearer_token",
        agent_id="0Xx000000000001",
    )
    client = AgentforceClient(config)

    session_resp = httpx.Response(
        200,
        json={"sessionId": "sess-abc-123"},
        request=httpx.Request("POST", f"{config.instance_url}/services/data/v61.0/einstein/ai-agent/sessions"),
    )
    msg_resp = httpx.Response(
        200,
        json={"message": {"content": "Hello! How can I assist you with your order?"}},
        request=httpx.Request("POST", f"{config.instance_url}/services/data/v61.0/einstein/ai-agent/sessions/sess-abc-123/messages"),
    )

    with patch("httpx.Client.post", side_effect=[session_resp, msg_resp]):
        turn = client.send_message("Where is my order?")
        assert client._session_id == "sess-abc-123"
        assert turn.turn_index == 1
        assert "Hello! How can I assist you" in turn.agent_response
        assert turn.timed_out is False
        assert turn.error is None


def test_agentforce_client_timeout_handling() -> None:
    """Verify graceful handling of httpx.TimeoutException."""
    config = AgentforceConfig(
        instance_url="https://testorg.my.salesforce.com",
        access_token="test_token",
        agent_id="0Xx000000000001",
        timeout_seconds=0.01,
    )
    client = AgentforceClient(config)
    client._session_id = "sess-123"

    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("Read timed out")):
        turn = client.send_message("Cancel my order")
        assert turn.timed_out is True
        assert "Timeout after" in turn.error
