"""Tests for Multi-Agent Handoff and Orchestration Chaos Engine."""

import pytest
from agent_chaos.core.assertions import BlastRadiusViolation
from agent_chaos.multiagent import (
    HandoffEvent,
    HandoffFault,
    HandoffFaultType,
    MultiAgentChaosHarness,
    assert_context_keys_preserved,
    assert_handoff_called,
    assert_handoff_fallback,
    assert_max_handoff_hops,
)


def test_clean_multiagent_handoff():
    harness = MultiAgentChaosHarness()

    res = harness.route_handoff(
        from_agent="supervisor",
        to_agent="billing_specialist",
        message="Please check invoice #400",
        context={"user_id": "U123", "role": "admin"},
        state={"session_active": True},
    )

    assert "billing_specialist" in res
    assert harness.total_hops() == 1
    assert_handoff_called(harness, to_agent="billing_specialist", times=1)
    assert_max_handoff_hops(harness, max_hops=3)
    assert_context_keys_preserved(harness, required_keys=["user_id", "role"])


def test_dropped_context_injection():
    harness = MultiAgentChaosHarness()
    # Strip user_id during delegation
    harness.set_handoff_fault(
        target_agent="billing_specialist",
        fault=HandoffFault.drop_context(strip_keys=["user_id"]),
    )

    harness.route_handoff(
        from_agent="supervisor",
        to_agent="billing_specialist",
        message="Process payment",
        context={"user_id": "U123", "role": "admin"},
    )

    events = harness.get_events_for_agent("billing_specialist")
    assert len(events) == 1
    assert "user_id" not in events[0].context
    assert "role" in events[0].context

    with pytest.raises(BlastRadiusViolation, match="Context corruption detected"):
        assert_context_keys_preserved(harness, required_keys=["user_id"])


def test_stale_state_injection():
    harness = MultiAgentChaosHarness()
    stale_snapshot = {"cart_items": 0, "total": 0.0}
    harness.set_handoff_fault(
        target_agent="checkout_agent",
        fault=HandoffFault.stale_state(stale_payload=stale_snapshot),
    )

    harness.route_handoff(
        from_agent="cart_agent",
        to_agent="checkout_agent",
        message="Proceed to checkout",
        state={"cart_items": 3, "total": 125.0},
    )

    events = harness.get_events_for_agent("checkout_agent")
    assert len(events) == 1
    assert events[0].state["cart_items"] == 0


def test_routing_timeout_and_fallback_assertion():
    harness = MultiAgentChaosHarness()
    # Inject routing timeout on primary refund agent
    harness.set_handoff_fault(
        target_agent="automated_refund_agent",
        fault=HandoffFault.routing_timeout(delay_seconds=3.0),
    )

    # Workflow tries automated_refund_agent, catches timeout, routes to human_escalation_agent
    try:
        harness.route_handoff(
            from_agent="supervisor",
            to_agent="automated_refund_agent",
            message="Refund $50",
        )
    except TimeoutError:
        # Supervisor catches timeout and initiates fallback
        harness.route_handoff(
            from_agent="supervisor",
            to_agent="human_escalation_agent",
            message="Fallback: manual refund review for $50",
        )

    assert harness.total_hops() == 2
    # Verify fallback assertion succeeds
    assert_handoff_fallback(
        harness,
        failed_agent="automated_refund_agent",
        fallback_agent="human_escalation_agent",
    )


def test_max_handoff_hops_loop_detection():
    harness = MultiAgentChaosHarness()

    # Simulate runaway ping-pong loop between two agents
    for _ in range(5):
        harness.route_handoff("agent_a", "agent_b", "Ping")
        harness.route_handoff("agent_b", "agent_a", "Pong")

    with pytest.raises(BlastRadiusViolation, match="Multi-agent delegation loop detected"):
        assert_max_handoff_hops(harness, max_hops=6)
