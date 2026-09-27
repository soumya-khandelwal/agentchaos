"""Tests for tool interception, wrapping, and trajectory recording."""

import asyncio
import pytest
from agent_chaos.core.faults import Fault, ToolHTTPError
from agent_chaos.core.interceptor import ChaosHarness


def test_sync_tool_interception():
    harness = ChaosHarness()

    @harness.intercept()
    def get_user_balance(user_id: str) -> dict:
        return {"user_id": user_id, "balance": 100.0}

    # First call: normal execution
    res = get_user_balance("user_123")
    assert res == {"user_id": "user_123", "balance": 100.0}
    assert harness.recorder.total_calls("get_user_balance") == 1

    # Inject HTTP 500 fault
    harness.set_fault("get_user_balance", Fault.http_error(status_code=500))

    with pytest.raises(ToolHTTPError) as exc_info:
        get_user_balance("user_123")
    assert exc_info.value.status_code == 500
    assert harness.recorder.total_calls("get_user_balance") == 2
    assert harness.recorder.has_faulted("get_user_balance")


def test_intermittent_fault_recovery():
    """Test fault triggering once then succeeding (validates agent retry testing)."""
    harness = ChaosHarness()

    # Fault triggers only on the 1st call
    harness.set_fault("payment_api", Fault.http_error(status_code=504, times=1))

    @harness.intercept(tool_name="payment_api")
    def payment_api(amount: float) -> str:
        return f"Charged {amount}"

    # Call 1: should fail with 504
    with pytest.raises(ToolHTTPError):
        payment_api(amount=50.0)

    # Call 2: should succeed
    res = payment_api(amount=50.0)
    assert res == "Charged 50.0"
    assert harness.recorder.total_calls("payment_api") == 2


@pytest.mark.asyncio
async def test_async_tool_interception():
    harness = ChaosHarness()

    harness.set_fault("async_fetch", Fault.timeout(times=1))

    @harness.intercept(tool_name="async_fetch")
    async def async_fetch(url: str) -> str:
        await asyncio.sleep(0.01)
        return "data"

    with pytest.raises(TimeoutError):
        await async_fetch("https://api.example.com")

    # Second call succeeds
    res = await async_fetch("https://api.example.com")
    assert res == "data"
    assert harness.recorder.total_calls("async_fetch") == 2
