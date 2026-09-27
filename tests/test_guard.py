"""Tests for RuntimeGuard, CircuitBreakers, RateLimiters, and Human-in-the-Loop gates."""

import time
import pytest
from agent_chaos.guard.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
)
from agent_chaos.guard.hitl import (
    HITLApprovalError,
    HITLDecision,
    HITLGate,
)
from agent_chaos.guard.rate_limiter import (
    RateLimitExceededError,
    SlidingWindowRateLimiter,
)
from agent_chaos.guard.runtime_guard import RuntimeGuard


def test_circuit_breaker_transitions():
    cb = CircuitBreaker(tool_name="stripe_charge", failure_threshold=2, recovery_timeout=0.1)
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute()

    # 1st failure: still closed
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute()

    # 2nd failure: trips to OPEN!
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert not cb.can_execute()

    # Wait for recovery timeout
    time.sleep(0.12)
    assert cb.can_execute()
    assert cb.state == CircuitState.HALF_OPEN

    # Success in HALF_OPEN resets to CLOSED
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


def test_sliding_window_rate_limiter():
    limiter = SlidingWindowRateLimiter(max_calls=3, window_seconds=0.2)
    assert limiter.check_and_record()
    assert limiter.check_and_record()
    assert limiter.check_and_record()

    # 4th call within 0.2s should be rejected
    assert not limiter.check_and_record()
    assert limiter.current_usage() == 3

    # Wait for window to expire
    time.sleep(0.25)
    assert limiter.check_and_record()
    assert limiter.current_usage() == 1


def test_hitl_approval_gate():
    gate = HITLGate()
    # Require approval only if amount > $500
    gate.add_policy("transfer", condition=lambda args: args.get("amount", 0) > 500)

    # Call with $100 -> skipped (auto-approved)
    assert gate.evaluate("transfer", {"amount": 100}) == HITLDecision.SKIPPED

    # Call with $1000 without handler -> REJECTED
    assert gate.evaluate("transfer", {"amount": 1000}) == HITLDecision.REJECTED

    # Call with approving handler -> APPROVED
    gate.set_approval_handler(lambda tool, args: True)
    assert gate.evaluate("transfer", {"amount": 1000}) == HITLDecision.APPROVED

    # Call with rejecting handler -> REJECTED
    gate.set_approval_handler(lambda tool, args: False)
    assert gate.evaluate("transfer", {"amount": 1000}) == HITLDecision.REJECTED


def test_runtime_guard_sync_wrapper():
    guard = RuntimeGuard()
    guard.configure_circuit_breaker("flaky_api", failure_threshold=2, recovery_timeout=0.1)

    calls = 0

    @guard.wrap_tool("flaky_api")
    def flaky_api():
        nonlocal calls
        calls += 1
        raise ConnectionResetError("Remote server disconnected")

    # Call 1: fails
    with pytest.raises(ConnectionResetError):
        flaky_api()
    assert calls == 1

    # Call 2: fails and trips breaker
    with pytest.raises(ConnectionResetError):
        flaky_api()
    assert calls == 2

    # Call 3: blocked by CircuitBreakerOpenError without calling inner function!
    with pytest.raises(CircuitBreakerOpenError):
        flaky_api()
    assert calls == 2  # Inner function was NOT called!


@pytest.mark.asyncio
async def test_runtime_guard_async_wrapper():
    guard = RuntimeGuard()
    guard.configure_rate_limit("async_query", max_calls=2, window_seconds=1.0)

    @guard.wrap_tool("async_query")
    async def async_query(q: str) -> str:
        return f"result for {q}"

    assert await async_query("q1") == "result for q1"
    assert await async_query("q2") == "result for q2"

    with pytest.raises(RateLimitExceededError):
        await async_query("q3")


def test_runtime_guard_hitl_protection():
    guard = RuntimeGuard()
    guard.configure_hitl("delete_user", condition=lambda args: True)
    # Handler rejects deletion
    guard.hitl_gate.set_approval_handler(lambda tool, args: False)

    @guard.wrap_tool("delete_user")
    def delete_user(uid: str):
        return f"deleted {uid}"

    with pytest.raises(HITLApprovalError) as exc_info:
        delete_user(uid="user_99")
    assert "Human approval rejected" in str(exc_info.value)
