"""Deterministic blast-radius and contract assertions for AgentChaos."""

from __future__ import annotations

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
