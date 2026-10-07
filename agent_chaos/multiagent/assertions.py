"""Deterministic blast-radius and coordination assertions for Multi-Agent Workflows."""

from __future__ import annotations

from typing import List, Optional
from agent_chaos.core.assertions import BlastRadiusViolation
from agent_chaos.multiagent.router import MultiAgentChaosHarness


def assert_max_handoff_hops(harness: MultiAgentChaosHarness, max_hops: int) -> None:
    """Assert that a multi-agent system did not enter an infinite ping-pong delegation loop."""
    total = harness.total_hops()
    if total > max_hops:
        raise BlastRadiusViolation(
            f"Multi-agent delegation loop detected! Workflow exceeded max hops limit: "
            f"{total} hops occurred (maximum allowed was {max_hops})."
        )


def assert_handoff_called(
    harness: MultiAgentChaosHarness,
    to_agent: str,
    from_agent: Optional[str] = None,
    times: Optional[int] = None,
) -> None:
    """Assert that a specific agent delegation occurred."""
    matching = [
        e for e in harness.handoff_events
        if e.to_agent == to_agent and (from_agent is None or e.from_agent == from_agent)
    ]
    count = len(matching)

    if times is not None and count != times:
        raise BlastRadiusViolation(
            f"Expected {times} handoffs to '{to_agent}', but recorded {count} handoffs."
        )

    if times is None and count == 0:
        raise BlastRadiusViolation(
            f"Expected at least 1 handoff to agent '{to_agent}', but it was never invoked."
        )


def assert_handoff_fallback(
    harness: MultiAgentChaosHarness,
    failed_agent: str,
    fallback_agent: str,
) -> None:
    """Assert that after a primary agent failed/timed out, the workflow successfully routed to a fallback agent."""
    failed_idx = None
    for idx, e in enumerate(harness.handoff_events):
        if e.to_agent == failed_agent and e.error is not None:
            failed_idx = idx
            break

    if failed_idx is None:
        raise BlastRadiusViolation(
            f"Cannot assert fallback: initial agent '{failed_agent}' did not record an error."
        )

    subsequent = harness.handoff_events[failed_idx + 1:]
    has_fallback = any(e.to_agent == fallback_agent for e in subsequent)

    if not has_fallback:
        raise BlastRadiusViolation(
            f"Multi-agent recovery failed: after agent '{failed_agent}' encountered an error, "
            f"workflow never routed to fallback agent '{fallback_agent}'."
        )


def assert_context_keys_preserved(
    harness: MultiAgentChaosHarness,
    required_keys: List[str],
    in_agent: Optional[str] = None,
) -> None:
    """Assert that critical context metadata was not dropped during handoffs."""
    events = (
        [e for e in harness.handoff_events if e.to_agent == in_agent]
        if in_agent
        else harness.handoff_events
    )

    for event in events:
        for k in required_keys:
            if k not in event.context:
                raise BlastRadiusViolation(
                    f"Context corruption detected: required key '{k}' was missing in handoff "
                    f"from '{event.from_agent}' to '{event.to_agent}'."
                )
