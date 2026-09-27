"""Tests for AgentChaos fault definitions and execution."""

import pytest
from agent_chaos.core.faults import Fault, FaultType, ToolHTTPError


def test_fault_factory_defaults():
    timeout_fault = Fault.timeout(delay=0.1, times=2)
    assert timeout_fault.fault_type == FaultType.TIMEOUT
    assert timeout_fault.times == 2
    assert timeout_fault.delay == 0.1

    http_fault = Fault.http_error(status_code=504, message="Gateway Timeout")
    assert http_fault.fault_type == FaultType.HTTP_ERROR
    assert http_fault.status_code == 504
    assert http_fault.message == "Gateway Timeout"

    rate_limit = Fault.rate_limit(retry_after=30)
    assert rate_limit.fault_type == FaultType.RATE_LIMIT
    assert rate_limit.status_code == 429

    poisoned = Fault.poisoned(payload="[MALICIOUS_PROMPT]")
    assert poisoned.fault_type == FaultType.POISONED_PAYLOAD
    assert poisoned.payload == "[MALICIOUS_PROMPT]"


def test_fault_sync_execution():
    http_fault = Fault.http_error(status_code=500, message="Database down")
    with pytest.raises(ToolHTTPError) as exc_info:
        http_fault.apply_sync()
    assert exc_info.value.status_code == 500
    assert "Database down" in str(exc_info.value)

    timeout_fault = Fault.timeout()
    with pytest.raises(TimeoutError):
        timeout_fault.apply_sync()

    malformed_fault = Fault.malformed(payload={"error": "corrupt"})
    res = malformed_fault.apply_sync()
    assert res == {"error": "corrupt"}


@pytest.mark.asyncio
async def test_fault_async_execution():
    http_fault = Fault.http_error(status_code=429, message="Rate limited")
    with pytest.raises(ToolHTTPError):
        await http_fault.apply_async()

    timeout_fault = Fault.timeout(delay=0.01)
    with pytest.raises(TimeoutError):
        await timeout_fault.apply_async()
