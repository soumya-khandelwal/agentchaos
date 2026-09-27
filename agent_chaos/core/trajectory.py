"""Trajectory recording and event storage for agent tool invocations."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from agent_chaos.core.faults import FaultType


class ToolCallEvent(BaseModel):
    """Represents a single intercepted tool invocation event."""
    tool_name: str
    call_index: int
    global_index: int
    arguments: Dict[str, Any]
    timestamp: float = Field(default_factory=time.time)
    fault_injected: Optional[FaultType] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: float = 0.0


class TrajectoryRecorder:
    """Thread-safe and async-safe in-memory recorder for agent tool trajectories."""

    def __init__(self) -> None:
        self.events: List[ToolCallEvent] = []
        self._tool_counts: Dict[str, int] = {}

    def record_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        duration_ms: float = 0.0,
        fault_injected: Optional[FaultType] = None,
        result: Optional[Any] = None,
        error: Optional[str] = None,
    ) -> ToolCallEvent:
        """Record an event into the trajectory."""
        self._tool_counts[tool_name] = self._tool_counts.get(tool_name, 0) + 1
        call_index = self._tool_counts[tool_name]
        global_index = len(self.events) + 1

        event = ToolCallEvent(
            tool_name=tool_name,
            call_index=call_index,
            global_index=global_index,
            arguments=arguments,
            fault_injected=fault_injected,
            result=result,
            error=error,
            duration_ms=duration_ms,
        )
        self.events.append(event)
        return event

    def get_calls_for_tool(self, tool_name: str) -> List[ToolCallEvent]:
        """Return all events for a specific tool name."""
        return [e for e in self.events if e.tool_name == tool_name]

    def total_calls(self, tool_name: Optional[str] = None) -> int:
        """Return total call count globally or for a specific tool."""
        if tool_name:
            return self._tool_counts.get(tool_name, 0)
        return len(self.events)

    def has_faulted(self, tool_name: Optional[str] = None) -> bool:
        """Check if any fault was injected into the trajectory."""
        calls = self.get_calls_for_tool(tool_name) if tool_name else self.events
        return any(e.fault_injected is not None for e in calls)

    def last_event(self) -> Optional[ToolCallEvent]:
        """Return the most recent event, if any."""
        return self.events[-1] if self.events else None

    def reset(self) -> None:
        """Reset all recorded events and counters."""
        self.events.clear()
        self._tool_counts.clear()
