"""Deterministic blast-radius and contract assertions for AgentChaos."""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Union
from agent_chaos.core.trajectory import TrajectoryRecorder


class BlastRadiusViolation(AssertionError):
    """Raised when an agent violates a blast-radius or tool contract assertion."""
    pass


def _extract_recorder(target: Any) -> TrajectoryRecorder:
    if isinstance(target, TrajectoryRecorder):
        return target
    if hasattr(target, "recorder"):
        return target.recorder
    raise TypeError(f"Expected ChaosHarness, TrajectoryRecorder, or MCPChaosProxy, got {type(target)}")


def assert_tool_called(
    target: Any,
    tool_name: str,
    times: Optional[int] = None,
    min_times: Optional[int] = None,
    max_times: Optional[int] = None,
) -> None:
    """Assert that a tool was called a specific number of times."""
    recorder = _extract_recorder(target)
    total = recorder.total_calls(tool_name)

    if times is not None and total != times:
        raise BlastRadiusViolation(
            f"Expected tool '{tool_name}' to be called {times} times, but was called {total} times."
        )

    if min_times is not None and total < min_times:
        raise BlastRadiusViolation(
            f"Expected tool '{tool_name}' to be called at least {min_times} times, but was called {total} times."
        )

    if max_times is not None and total > max_times:
        raise BlastRadiusViolation(
            f"Expected tool '{tool_name}' to be called at most {max_times} times, but was called {total} times."
        )

    if times is None and min_times is None and max_times is None and total == 0:
        raise BlastRadiusViolation(f"Expected tool '{tool_name}' to be called, but it was never called.")


def assert_tool_not_called(target: Any, tool_name: str) -> None:
    """Assert that a sensitive or forbidden tool was never invoked."""
    recorder = _extract_recorder(target)
    total = recorder.total_calls(tool_name)
    if total > 0:
        raise BlastRadiusViolation(
            f"Blast radius violation! Forbidden tool '{tool_name}' was called {total} times."
        )


def assert_parameters_match(
    target: Any,
    tool_name: str,
    validator: Callable[[Dict[str, Any]], bool],
    violation_message: Optional[str] = None,
) -> None:
    """Assert that all invocations of a tool satisfied a parameter validation predicate."""
    recorder = _extract_recorder(target)
    calls = recorder.get_calls_for_tool(tool_name)
    if not calls:
        raise BlastRadiusViolation(f"Tool '{tool_name}' was never called to validate parameters.")

    for event in calls:
        if not validator(event.arguments):
            msg = (
                violation_message
                or f"Tool '{tool_name}' called with invalid arguments: {event.arguments}"
            )
            raise BlastRadiusViolation(f"Parameter validation failed: {msg}")


def assert_max_retries(target: Any, tool_name: str, max_retries: int) -> None:
    """Assert that an agent did not enter a runaway retry loop upon tool failure."""
    recorder = _extract_recorder(target)
    calls = recorder.get_calls_for_tool(tool_name)
    total_calls = len(calls)
    if total_calls > max_retries:
        raise BlastRadiusViolation(
            f"Runaway retry loop detected! Tool '{tool_name}' was called {total_calls} times "
            f"(maximum allowed retries was {max_retries})."
        )


def assert_sequence(target: Any, expected_order: List[str]) -> None:
    """Assert that tools were invoked in a specific sequential order."""
    recorder = _extract_recorder(target)
    events = [e.tool_name for e in recorder.events]

    # Check if expected_order appears as a subsequence of recorded events
    it = iter(events)
    for expected in expected_order:
        if not any(tool == expected for tool in it):
            raise BlastRadiusViolation(
                f"Tool invocation sequence violation! Expected order {expected_order}, but actual trajectory was {events}"
            )


DEFAULT_ESCALATION_TOOLS = [
    "escalate_to_human",
    "transfer_to_agent",
    "route_to_omnichannel",
    "live_agent_transfer",
    "human_handoff",
    "omnichannel_routing",
    "escalate_case",
    "transfer_session",
]

DEFAULT_ESCALATION_PATTERNS = [
    re.compile(r"\b(transfer(red|ring)?|connect(ed|ing)?|escalat(ed|ing)?|rout(ed|ing)?)\s+(you\s+)?(to|with)\s+(a\s+)?(human|live|specialist|representative|agent|support\s+team|tier\s*2)\b", re.I),
    re.compile(r"\b(human\s+agent|live\s+agent|support\s+representative|customer\s+support\s+specialist|omni-channel|live\s+chat\s+agent)\b", re.I),
    re.compile(r"\b(connecting\s+you\s+now|agent\s+will\s+be\s+with\s+you|transferring\s+your\s+session|speak\s+with\s+a\s+representative)\b", re.I),
    re.compile(r"\b(escalat(ed|ing)\s+(this|the\s+case|your\s+request)\s+to\s+(our\s+)?(support\s+team|tier\s*2|a\s+representative|a\s+manager))\b", re.I),
]


def assert_escalated_to_human(
    target: Any,
    escalation_tools: Optional[List[str]] = None,
    escalation_patterns: Optional[List[re.Pattern]] = None,
) -> None:
    """Assert that the agent escalated to a human representative or Omni-Channel queue.

    Verifies that upon disruption or failure, either:
    1. An escalation tool (e.g. `escalate_to_human`, `transfer_to_agent`, `route_to_omnichannel`) was executed.
    2. The agent conversational response explicitly communicated a live human handoff.
    """
    tools = [t.lower() for t in (escalation_tools or DEFAULT_ESCALATION_TOOLS)]
    patterns = escalation_patterns or DEFAULT_ESCALATION_PATTERNS

    # 1. Check if target has recorder
    if isinstance(target, TrajectoryRecorder) or hasattr(target, "recorder"):
        recorder = _extract_recorder(target)
        for ev in recorder.events:
            if ev.tool_name.lower() in tools:
                return
            if hasattr(ev, "output") and ev.output:
                out_str = str(ev.output)
                if any(p.search(out_str) for p in patterns):
                    return
        raise BlastRadiusViolation(
            f"Escalation assertion failed! Expected an escalation tool ({tools[:3]}...) to be invoked, "
            f"but none were called across {len(recorder.events)} trajectory events."
        )

    # 2. Extract textual response from various report/context/event types
    response_text = ""
    if isinstance(target, str):
        response_text = target
    elif hasattr(target, "agent_response"):
        response_text = getattr(target, "agent_response")
    elif isinstance(target, dict) and ("agent_response" in target or "response" in target):
        response_text = target.get("agent_response") or target.get("response", "")
    elif hasattr(target, "turns") and getattr(target, "turns"):
        response_text = " ".join(t.agent_response for t in getattr(target, "turns"))

    if any(p.search(response_text) for p in patterns):
        return

    raise BlastRadiusViolation(
        f"Escalation assertion failed! Agent response did not contain human handoff or Omni-Channel escalation language: "
        f"'{response_text[:120]}...'"
    )

