"""Tests for deterministic blast-radius and contract assertions."""

import pytest
from agent_chaos.core.assertions import (
    BlastRadiusViolation,
    assert_max_retries,
    assert_parameters_match,
    assert_sequence,
    assert_tool_called,
    assert_tool_not_called,
)
from agent_chaos.core.faults import Fault
from agent_chaos.core.interceptor import ChaosHarness


def test_assert_tool_called_and_not_called():
    harness = ChaosHarness()

    @harness.intercept()
    def check_eligibility(user_id: str):
        return True

    @harness.intercept()
    def delete_account(user_id: str):
        return "deleted"

    check_eligibility("user_1")

    # Assertions
    assert_tool_called(harness, "check_eligibility", times=1)
    assert_tool_not_called(harness, "delete_account")

    # Violation triggers
    with pytest.raises(BlastRadiusViolation):
        assert_tool_called(harness, "check_eligibility", times=2)

    with pytest.raises(BlastRadiusViolation):
        assert_tool_not_called(harness, "check_eligibility")


def test_assert_parameters_match():
    harness = ChaosHarness()

    @harness.intercept()
    def refund_order(order_id: str, amount: float):
        return "success"

    refund_order("ORD-101", 250.0)

    # Policy: refunds must be <= $500
    assert_parameters_match(
        harness,
        "refund_order",
        lambda args: args.get("amount", 0) <= 500,
        violation_message="Refund amount exceeded maximum policy of $500",
    )

    # Violation check: policy <= $100 fails
    with pytest.raises(BlastRadiusViolation) as exc_info:
        assert_parameters_match(
            harness,
            "refund_order",
            lambda args: args.get("amount", 0) <= 100,
        )
    assert "Parameter validation failed" in str(exc_info.value)


def test_assert_max_retries():
    harness = ChaosHarness()

    @harness.intercept()
    def flaky_api():
        return "ok"

    flaky_api()
    flaky_api()
    flaky_api()

    # Allowed up to 3 calls
    assert_max_retries(harness, "flaky_api", max_retries=3)

    # Violation: capped at 2 calls
    with pytest.raises(BlastRadiusViolation) as exc_info:
        assert_max_retries(harness, "flaky_api", max_retries=2)
    assert "Runaway retry loop detected" in str(exc_info.value)


def test_assert_sequence():
    harness = ChaosHarness()

    @harness.intercept()
    def authenticate():
        return True

    @harness.intercept()
    def authorize():
        return True

    @harness.intercept()
    def execute():
        return True

    authenticate()
    authorize()
    execute()

    assert_sequence(harness, ["authenticate", "authorize", "execute"])

    with pytest.raises(BlastRadiusViolation):
        assert_sequence(harness, ["authorize", "authenticate"])
